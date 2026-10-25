# -*- coding: utf-8 -*-
# Part of Ridhira Technologies. See LICENSE file for full copyright and licensing details.

import logging
import socket
from datetime import datetime, timedelta
import pytz

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

try:
    from zk import ZK, const
    HAS_PYZK = True
except ImportError:
    HAS_PYZK = False
    ZK = None
    const = None


class ZkMachine(models.Model):
    _name = 'zk.machine'
    _description = 'Biometric Attendance Device'
    _order = 'name asc'
    _inherit = ['mail.thread', 'mail.activity.mixin'] if 'mail.thread' in models.Model._inherit_cache else []

    name = fields.Char(string='Device Name', required=True, tracking=True)
    device_code = fields.Char(string='Device Code', readonly=True, copy=False, default=lambda self: self.env['ir.sequence'].next_by_code('zk.machine') or 'DEV/NEW')
    device_ip = fields.Char(string='Device IP / Host', default='192.168.1.201', tracking=True)
    port = fields.Integer(string='Port', default=4370, required=True)
    protocol = fields.Selection([
        ('tcp', 'Direct TCP/IP Polling'),
        ('udp', 'Direct UDP Polling'),
        ('adms', 'Cloud ADMS Push Server (ICLK)'),
    ], string='Protocol Mode', default='tcp', required=True, tracking=True,
       help="TCP/UDP initiates direct connection from Odoo to the device.\n"
            "Cloud ADMS Push allows the device to push punches to Odoo over HTTP/HTTPS (Ideal for remote offices without static IP).")
    
    comm_key = fields.Integer(string='Communication Password / Key', default=0,
                             help='Password configured on the device (default is 0 if not set).')
    timeout = fields.Integer(string='Connection Timeout (sec)', default=5)
    serial_number = fields.Char(string='Serial Number (SN)', index=True, tracking=True,
                                help='Required for Cloud ADMS Push matching.')
    device_model = fields.Char(string='Device Model', readonly=True)
    firmware_version = fields.Char(string='Firmware Version', readonly=True)
    platform = fields.Char(string='Hardware Platform', readonly=True)
    mac_address = fields.Char(string='MAC Address', readonly=True)
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)
    location = fields.Char(string='Physical Location', placeholder='e.g., Main Entrance Turnstile')
    direction = fields.Selection([
        ('both', 'Bidirectional (Auto In / Out)'),
        ('in', 'Entry Only (Forces Check-In)'),
        ('out', 'Exit Only (Forces Check-Out)'),
    ], string='Direction Rule', default='both', required=True,
       help="Defines whether punches from this machine should force Check-in, Check-out, or alternate automatically.")

    state = fields.Selection([
        ('draft', 'New'),
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('error', 'Error'),
    ], string='Status', default='draft', tracking=True)

    last_sync_time = fields.Datetime(string='Last Attendance Sync', readonly=True)
    last_activity = fields.Datetime(string='Last Heartbeat / Activity', readonly=True)
    
    user_count = fields.Integer(string='Device Users', readonly=True)
    attendance_count = fields.Integer(string='Device Attendance Records', readonly=True)
    fingerprint_count = fields.Integer(string='Fingerprint Templates', readonly=True)
    face_count = fields.Integer(string='Face Templates', readonly=True)
    
    auto_sync = fields.Boolean(string='Auto Sync via Cron', default=True,
                               help='Include this device in automated periodic background synchronization.')
    clear_logs_after_download = fields.Boolean(string='Clear Device Memory After Sync', default=False,
                                              help='Caution: Deletes downloaded punches from the physical device memory to prevent device storage overflow.')
    
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes & Setup Instructions')

    # Relationships
    machine_user_ids = fields.One2many('zk.machine.user', 'device_id', string='Enrolled Device Users')
    attendance_log_ids = fields.One2many('zk.attendance.log', 'device_id', string='Raw Attendance Logs')
    
    log_count = fields.Integer(string='Total Raw Logs', compute='_compute_log_counts')
    pending_log_count = fields.Integer(string='Pending Logs', compute='_compute_log_counts')
    machine_user_count = fields.Integer(string='User Count', compute='_compute_user_count')
    
    is_pyzk_available = fields.Boolean(string='PyZK Library Available', compute='_compute_pyzk_available')
    adms_server_url = fields.Char(string='Cloud ADMS Server URL', compute='_compute_adms_server_url')
    adms_command_queue = fields.Text(string='Queued ADMS Commands', copy=False,
                                     help='Newline-separated commands waiting to be polled by the ADMS terminal.')

    def _compute_pyzk_available(self):
        for rec in self:
            rec.is_pyzk_available = HAS_PYZK

    def _compute_adms_server_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
        for rec in self:
            rec.adms_server_url = f"{base_url}/iclock/cdata"

    def _compute_log_counts(self):
        log_obj = self.env['zk.attendance.log']
        for rec in self:
            rec.log_count = log_obj.search_count([('device_id', '=', rec.id)])
            rec.pending_log_count = log_obj.search_count([('device_id', '=', rec.id), ('state', '=', 'draft')])

    def _compute_user_count(self):
        user_obj = self.env['zk.machine.user']
        for rec in self:
            rec.machine_user_count = user_obj.search_count([('device_id', '=', rec.id)])

    def _get_zk_instance(self):
        self.ensure_one()
        if not HAS_PYZK:
            raise UserError(_(
                "The Python 'pyzk' library is not installed in your Odoo Python environment.\n\n"
                "To enable Direct TCP/UDP communication, install it via:\n"
                "    pip install pyzk\n\n"
                "Note: You can still use the Cloud ADMS Push Protocol without installing pyzk!"
            ))
        if not self.device_ip:
            raise UserError(_("Please configure the Device IP or Hostname."))

        force_udp = (self.protocol == 'udp')
        return ZK(
            self.device_ip,
            port=self.port or 4370,
            timeout=self.timeout or 5,
            password=self.comm_key or 0,
            force_udp=force_udp,
            ommit_ping=False
        )

    def _check_tcp_reachability(self, timeout=2):
        self.ensure_one()
        if self.protocol == 'adms':
            return True
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((self.device_ip, int(self.port or 4370)))
            s.close()
            return True
        except Exception:
            return False

    def action_test_connection(self):
        """ Tests device connectivity and retrieves device specifications. """
        self.ensure_one()
        if self.protocol == 'adms':
            if self.last_activity and (fields.Datetime.now() - self.last_activity) < timedelta(minutes=10):
                self.write({'state': 'online'})
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _("ADMS Device Online"),
                        'message': _("Device %s is active and connected via Cloud ADMS Push.") % self.name,
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _("ADMS Awaiting Connection"),
                        'message': _("Configure this device's Cloud Server / ADMS URL to: %s\nDevice SN: %s") % (self.adms_server_url, self.serial_number or 'Configure SN'),
                        'type': 'warning',
                        'sticky': True,
                    }
                }

        zk = self._get_zk_instance()
        conn = None
        try:
            conn = zk.connect()
            sn = conn.get_serialnumber() or self.serial_number
            firmware = conn.get_firmware_version() or self.firmware_version
            platform = conn.get_platform() or self.platform
            mac = conn.get_mac() or self.mac_address

            # Attempt to read counts safely
            users = conn.get_users()
            user_cnt = len(users) if users else 0
            
            vals = {
                'state': 'online',
                'serial_number': sn or self.serial_number,
                'firmware_version': firmware,
                'platform': platform,
                'mac_address': mac,
                'user_count': user_cnt,
                'last_activity': fields.Datetime.now(),
            }
            self.write(vals)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Connection Successful!"),
                    'message': _("Connected to %s! Serial: %s | Firmware: %s | Users: %d") % (self.name, sn, firmware, user_cnt),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            self.write({'state': 'offline'})
            _logger.warning("Biometric device test failed for %s: %s", self.name, str(e))
            raise UserError(_("Connection failed to %s (%s:%s):\n\n%s") % (self.name, self.device_ip, self.port, str(e)))
        finally:
            if conn:
                try:
                    conn.disconnect()
                except Exception:
                    pass

    def action_download_attendance(self, auto_process=True):
        """ Downloads all attendance punches from physical device into raw logs. """
        self.ensure_one()
        if self.protocol == 'adms':
            raise UserError(_("This device is configured for Cloud ADMS Push. It sends punches to Odoo automatically in real-time!"))

        zk = self._get_zk_instance()
        conn = None
        downloaded = 0
        new_logs = self.env['zk.attendance.log']
        log_obj = self.env['zk.attendance.log']

        try:
            conn = zk.connect()
            conn.disable_device()
            attendances = conn.get_attendance()

            if attendances:
                for att in attendances:
                    # att attributes: user_id, timestamp, status, punch
                    user_id_str = str(att.user_id).strip()
                    # Convert device local timestamp to naive UTC datetime
                    punch_dt = att.timestamp
                    if isinstance(punch_dt, str):
                        punch_dt = datetime.strptime(punch_dt, '%Y-%m-%d %H:%M:%S')

                    # Check for duplicate raw log already in database
                    existing = log_obj.search([
                        ('device_id', '=', self.id),
                        ('device_user_id', '=', user_id_str),
                        ('punch_time', '=', punch_dt),
                    ], limit=1)

                    if not existing:
                        # Map punch status (0: Check-In, 1: Check-Out, 2: Break-Out, 3: Break-In, etc.)
                        punch_type = 'auto'
                        status_val = getattr(att, 'status', 0)
                        if status_val == 0:
                            punch_type = 'check_in'
                        elif status_val == 1:
                            punch_type = 'check_out'
                        elif status_val == 2:
                            punch_type = 'break_out'
                        elif status_val == 3:
                            punch_type = 'break_in'

                        # Override if machine has strict direction rule
                        if self.direction == 'in':
                            punch_type = 'check_in'
                        elif self.direction == 'out':
                            punch_type = 'check_out'

                        # Match employee
                        emp = self._match_employee_for_user_id(user_id_str)

                        log = log_obj.create({
                            'device_id': self.id,
                            'device_sn': self.serial_number,
                            'device_user_id': user_id_str,
                            'employee_id': emp.id if emp else False,
                            'punch_time': punch_dt,
                            'punch_type': punch_type,
                            'verify_type': str(getattr(att, 'punch', '0')),
                            'source': 'tcp',
                            'company_id': self.company_id.id,
                            'raw_data': f"user_id={user_id_str}; timestamp={punch_dt}; status={status_val}; punch={getattr(att, 'punch', 0)}",
                        })
                        new_logs |= log
                        downloaded += 1

                if self.clear_logs_after_download:
                    conn.clear_attendance()
                    _logger.info("Cleared attendance log memory on device %s after download.", self.name)

            conn.enable_device()
            self.write({
                'state': 'online',
                'last_sync_time': fields.Datetime.now(),
                'last_activity': fields.Datetime.now(),
            })

            # Auto-process pending logs into hr.attendance
            processed_count = 0
            if auto_process and new_logs:
                processed_count = new_logs.action_process_logs()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Sync Completed!"),
                    'message': _("Downloaded %d new punch logs. Processed %d attendances.") % (downloaded, processed_count),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            self.write({'state': 'offline'})
            _logger.error("Error downloading attendance from %s: %s", self.name, str(e))
            raise UserError(_("Failed to download attendance logs from %s: %s") % (self.name, str(e)))
        finally:
            if conn:
                try:
                    conn.enable_device()
                    conn.disconnect()
                except Exception:
                    pass

    def action_download_users(self):
        """ Downloads user profiles from device and auto-maps them to Odoo employees. """
        self.ensure_one()
        if self.protocol == 'adms':
            raise UserError(_("For ADMS devices, user profiles are pushed or managed via Cloud push commands."))

        zk = self._get_zk_instance()
        conn = None
        user_obj = self.env['zk.machine.user']
        created_count = 0
        updated_count = 0

        try:
            conn = zk.connect()
            conn.disable_device()
            users = conn.get_users()

            if users:
                for u in users:
                    uid_str = str(u.user_id).strip()
                    existing_user = user_obj.search([
                        ('device_id', '=', self.id),
                        ('device_user_id', '=', uid_str),
                    ], limit=1)

                    card_num = str(getattr(u, 'card', '')).strip()
                    priv = str(getattr(u, 'privilege', 0))
                    emp = self._match_employee_for_user_id(uid_str, card_num)

                    vals = {
                        'name': u.name or f"User {uid_str}",
                        'device_id': self.id,
                        'device_user_id': uid_str,
                        'badge_number': card_num,
                        'privilege': priv if priv in ['0', '14', '2'] else '0',
                        'employee_id': emp.id if emp else False,
                        'last_sync': fields.Datetime.now(),
                    }

                    if existing_user:
                        existing_user.write(vals)
                        updated_count += 1
                    else:
                        user_obj.create(vals)
                        created_count += 1

            conn.enable_device()
            self.write({
                'user_count': len(users) if users else 0,
                'last_activity': fields.Datetime.now(),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("User Sync Complete"),
                    'message': _("Synchronized %d users from device (%d new, %d updated).") % (created_count + updated_count, created_count, updated_count),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error("Failed downloading users from %s: %s", self.name, str(e))
            raise UserError(_("Failed to download users: %s") % str(e))
        finally:
            if conn:
                try:
                    conn.enable_device()
                    conn.disconnect()
                except Exception:
                    pass

    def action_sync_device_time(self):
        """ Syncs physical device clock with server time. """
        self.ensure_one()
        if self.protocol == 'adms':
            self.queue_adms_command("CHECK")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("ADMS Command Queued"),
                    'message': _("Time check command queued for ADMS device %s.") % self.name,
                    'type': 'info',
                }
            }

        zk = self._get_zk_instance()
        conn = None
        try:
            conn = zk.connect()
            now_dt = datetime.now()
            conn.set_time(now_dt)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Clock Synchronized!"),
                    'message': _("Device clock successfully synchronized to: %s") % now_dt.strftime('%Y-%m-%d %H:%M:%S'),
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(_("Failed to sync clock: %s") % str(e))
        finally:
            if conn:
                try:
                    conn.disconnect()
                except Exception:
                    pass

    def action_restart_device(self):
        """ Remotely reboots the biometric device. """
        self.ensure_one()
        if self.protocol == 'adms':
            self.queue_adms_command("REBOOT")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Reboot Queued"),
                    'message': _("Reboot command queued for ADMS terminal %s.") % self.name,
                    'type': 'info',
                }
            }

        zk = self._get_zk_instance()
        conn = None
        try:
            conn = zk.connect()
            conn.restart()
            self.write({'state': 'offline'})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Device Rebooting"),
                    'message': _("Reboot signal sent to %s.") % self.name,
                    'type': 'warning',
                }
            }
        except Exception as e:
            raise UserError(_("Failed to restart device: %s") % str(e))
        finally:
            if conn:
                try:
                    conn.disconnect()
                except Exception:
                    pass

    def action_clear_device_logs(self):
        """ Clears all attendance records from physical machine memory. """
        self.ensure_one()
        if self.protocol == 'adms':
            self.queue_adms_command("CLEAR LOG")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Command Queued"),
                    'message': _("Clear log command queued for ADMS terminal %s.") % self.name,
                    'type': 'info',
                }
            }

        zk = self._get_zk_instance()
        conn = None
        try:
            conn = zk.connect()
            conn.clear_attendance()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Device Memory Cleared"),
                    'message': _("Attendance punches have been wiped from physical device memory."),
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(_("Failed to clear device logs: %s") % str(e))
        finally:
            if conn:
                try:
                    conn.disconnect()
                except Exception:
                    pass

    def action_beep(self):
        """ Tests audio speaker / voice on physical device. """
        self.ensure_one()
        if self.protocol == 'adms':
            return
        zk = self._get_zk_instance()
        conn = None
        try:
            conn = zk.connect()
            conn.test_voice()
        except Exception as e:
            raise UserError(_("Failed to send test voice: %s") % str(e))
        finally:
            if conn:
                try:
                    conn.disconnect()
                except Exception:
                    pass

    def queue_adms_command(self, cmd_text):
        """ Enqueues an ADMS command to be sent on next /iclock/getrequest polling. """
        self.ensure_one()
        existing = (self.adms_command_queue or "").strip()
        lines = [l for l in existing.splitlines() if l.strip()]
        lines.append(cmd_text.strip())
        self.sudo().write({'adms_command_queue': "\n".join(lines)})

    def _match_employee_for_user_id(self, user_id_str, card_number=None):
        """ Intelligently matches a device user ID or badge to an Odoo hr.employee. """
        emp_obj = self.env['hr.employee']
        
        # 1. Exact match on zk_user_id
        emp = emp_obj.search([('zk_user_id', '=', user_id_str), ('company_id', '=', self.company_id.id)], limit=1)
        if emp:
            return emp
            
        # 2. Match on barcode (Badge ID)
        emp = emp_obj.search([('barcode', '=', user_id_str), ('company_id', '=', self.company_id.id)], limit=1)
        if emp:
            return emp

        # 3. Match on PIN
        emp = emp_obj.search([('pin', '=', user_id_str), ('company_id', '=', self.company_id.id)], limit=1)
        if emp:
            return emp

        # 4. Match on identification_id
        emp = emp_obj.search([('identification_id', '=', user_id_str), ('company_id', '=', self.company_id.id)], limit=1)
        if emp:
            return emp

        # 5. Match by card number if provided
        if card_number and card_number != '0':
            emp = emp_obj.search([('barcode', '=', card_number), ('company_id', '=', self.company_id.id)], limit=1)
            if emp:
                return emp

        return False

    def action_view_attendance_logs(self):
        self.ensure_one()
        return {
            'name': _("Raw Logs - %s") % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'zk.attendance.log',
            'view_mode': 'list,form,pivot',
            'domain': [('device_id', '=', self.id)],
            'context': {'default_device_id': self.id},
        }

    def action_view_machine_users(self):
        self.ensure_one()
        return {
            'name': _("Users on Device - %s") % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'zk.machine.user',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.id)],
            'context': {'default_device_id': self.id},
        }

    @api.model
    def _cron_sync_all_devices(self):
        """ Automated scheduled cron to pull attendance logs from active devices. """
        devices = self.search([
            ('auto_sync', '=', True),
            ('active', '=', True),
            ('protocol', 'in', ['tcp', 'udp']),
        ])
        _logger.info("Biometric Device Cron: Synchronizing %d direct network devices...", len(devices))
        for dev in devices:
            try:
                dev.action_download_attendance(auto_process=True)
            except Exception as e:
                _logger.warning("Cron sync failed for device %s (%s): %s", dev.name, dev.device_ip, str(e))
