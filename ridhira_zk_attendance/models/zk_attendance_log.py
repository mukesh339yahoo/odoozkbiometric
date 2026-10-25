# -*- coding: utf-8 -*-
# Part of Ridhira Technologies. See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ZkAttendanceLog(models.Model):
    _name = 'zk.attendance.log'
    _description = 'Biometric Raw Punch Log'
    _order = 'punch_time desc, id desc'

    name = fields.Char(string='Log Reference', required=True, readonly=True, default=lambda self: self.env['ir.sequence'].next_by_code('zk.attendance.log') or 'BIO/LOG')
    device_id = fields.Many2one('zk.machine', string='Biometric Device', ondelete='set null', index=True)
    device_sn = fields.Char(string='Device Serial No', index=True)
    device_user_id = fields.Char(string='Device User ID / PIN', required=True, index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', index=True)
    punch_time = fields.Datetime(string='Punch Time (UTC)', required=True, index=True)
    
    punch_type = fields.Selection([
        ('check_in', 'Check-In'),
        ('check_out', 'Check-Out'),
        ('break_out', 'Break-Out'),
        ('break_in', 'Break-In'),
        ('auto', 'Auto-Detect'),
    ], string='Punch Type', default='auto', required=True)

    verify_type = fields.Selection([
        ('0', 'Password / Other'),
        ('1', 'Fingerprint'),
        ('2', 'PIN / Password'),
        ('3', 'RFID / Card'),
        ('4', 'Face Recognition'),
        ('15', 'Palm Recognition'),
    ], string='Verification Mode', default='1')

    state = fields.Selection([
        ('draft', 'Pending'),
        ('processed', 'Processed'),
        ('duplicate', 'Duplicate / Ignored'),
        ('error', 'Error / Unmatched'),
    ], string='Processing State', default='draft', index=True, tracking=True)

    attendance_id = fields.Many2one('hr.attendance', string='Generated Attendance', ondelete='set null', readonly=True)
    error_message = fields.Text(string='Processing Notes / Error', readonly=True)
    raw_data = fields.Text(string='Raw Payload', readonly=True)
    
    source = fields.Selection([
        ('tcp', 'Direct Network Pull'),
        ('adms', 'Cloud ADMS Push'),
        ('api', 'REST Webhook'),
        ('manual', 'Manual Entry'),
    ], string='Ingestion Source', default='tcp', required=True)

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'BIO/LOG':
                vals['name'] = self.env['ir.sequence'].next_by_code('zk.attendance.log') or 'BIO/LOG'
            # Attempt auto-matching employee if not provided
            if not vals.get('employee_id') and vals.get('device_user_id'):
                dev_id = vals.get('device_id')
                comp_id = vals.get('company_id') or self.env.company.id
                emp = self._find_matching_employee(vals.get('device_user_id'), comp_id, dev_id)
                if emp:
                    vals['employee_id'] = emp.id
        return super(ZkAttendanceLog, self).create(vals_list)

    @api.model
    def _find_matching_employee(self, user_id_str, company_id, device_id=None):
        emp_obj = self.env['hr.employee']
        user_id_str = str(user_id_str).strip()
        
        # 1. First check if mapped explicitly in zk.machine.user
        if device_id:
            m_user = self.env['zk.machine.user'].search([
                ('device_id', '=', device_id),
                ('device_user_id', '=', user_id_str),
                ('employee_id', '!=', False)
            ], limit=1)
            if m_user:
                return m_user.employee_id

        # 2. Match zk_user_id
        emp = emp_obj.search([('zk_user_id', '=', user_id_str), ('company_id', '=', company_id)], limit=1)
        if emp:
            return emp

        # 3. Match barcode
        emp = emp_obj.search([('barcode', '=', user_id_str), ('company_id', '=', company_id)], limit=1)
        if emp:
            return emp

        # 4. Match PIN
        emp = emp_obj.search([('pin', '=', user_id_str), ('company_id', '=', company_id)], limit=1)
        if emp:
            return emp

        # 5. Match Identification ID
        emp = emp_obj.search([('identification_id', '=', user_id_str), ('company_id', '=', company_id)], limit=1)
        if emp:
            return emp

        return False

    def action_match_employee(self):
        """ Re-attempts employee matching for selected logs. """
        for log in self:
            emp = self._find_matching_employee(log.device_user_id, log.company_id.id, log.device_id.id if log.device_id else None)
            if emp:
                log.write({'employee_id': emp.id, 'error_message': False, 'state': 'draft'})
            else:
                log.write({
                    'state': 'error',
                    'error_message': _("No matching employee found with User ID / Badge '%s'") % log.device_user_id
                })

    def action_process_logs(self):
        """
        Processes pending raw punch logs into hr.attendance records.
        Employs intelligent pairing, duplicate suppression, and shift boundary validation.
        """
        pending_logs = self.filtered(lambda l: l.state in ['draft', 'error'])
        if not pending_logs:
            return 0

        # Retrieve system configuration parameters
        ICP = self.env['ir.config_parameter'].sudo()
        dup_threshold_min = int(ICP.get_param('ridhira_zk_attendance.zk_duplicate_threshold_minutes', 5))
        max_shift_hours = int(ICP.get_param('ridhira_zk_attendance.zk_max_shift_hours', 16))

        # Sort logs chronologically by punch time
        sorted_logs = pending_logs.sorted(key=lambda l: l.punch_time)
        attendance_obj = self.env['hr.attendance']
        processed_count = 0

        # Group by employee
        employees = sorted_logs.mapped('employee_id')
        unmatched_logs = sorted_logs.filtered(lambda l: not l.employee_id)

        # Flag unmatched logs as error
        for u_log in unmatched_logs:
            emp = self._find_matching_employee(u_log.device_user_id, u_log.company_id.id, u_log.device_id.id if u_log.device_id else None)
            if emp:
                u_log.write({'employee_id': emp.id})
                employees |= emp
            else:
                u_log.write({
                    'state': 'error',
                    'error_message': _("Unmatched Punch: No employee mapped to Device User ID '%s'") % u_log.device_user_id
                })

        for emp in employees:
            emp_logs = sorted_logs.filtered(lambda l: l.employee_id == emp)
            
            for log in emp_logs:
                # 1. Check for Duplicate Punch within threshold window
                recent_punch = self.search([
                    ('employee_id', '=', emp.id),
                    ('id', '!=', log.id),
                    ('state', 'in', ['processed', 'draft']),
                    ('punch_time', '>=', log.punch_time - timedelta(minutes=dup_threshold_min)),
                    ('punch_time', '<=', log.punch_time + timedelta(minutes=dup_threshold_min)),
                ], limit=1)

                if recent_punch and recent_punch.punch_time != log.punch_time:
                    log.write({
                        'state': 'duplicate',
                        'error_message': _("Ignored duplicate punch within %d minutes of punch at %s") % (dup_threshold_min, recent_punch.punch_time),
                    })
                    continue

                # 2. Check direction rules from device or punch type
                direction = log.punch_type
                if log.device_id:
                    if log.device_id.direction == 'in':
                        direction = 'check_in'
                    elif log.device_id.direction == 'out':
                        direction = 'check_out'

                # 3. Look for existing open attendance for employee
                open_attendance = attendance_obj.search([
                    ('employee_id', '=', emp.id),
                    ('check_out', '=', False),
                ], order='check_in desc', limit=1)

                # Process according to direction / pairing
                if direction == 'check_in':
                    if open_attendance:
                        # Open attendance already exists
                        hours_open = (log.punch_time - open_attendance.check_in).total_seconds() / 3600.0
                        if hours_open > max_shift_hours:
                            # Auto-close runaway previous shift at max shift limit
                            auto_close_dt = open_attendance.check_in + timedelta(hours=max_shift_hours)
                            open_attendance.write({
                                'check_out': auto_close_dt,
                            })
                            # Now create fresh check-in
                            att = attendance_obj.create({
                                'employee_id': emp.id,
                                'check_in': log.punch_time,
                                'zk_device_id': log.device_id.id if log.device_id else False,
                                'zk_checkin_log_id': log.id,
                            })
                            log.write({'state': 'processed', 'attendance_id': att.id, 'error_message': False})
                            processed_count += 1
                        else:
                            # Punching in again while already checked in; treat as redundant or close and open
                            log.write({
                                'state': 'duplicate',
                                'error_message': _("Employee already checked in at %s.") % open_attendance.check_in,
                            })
                    else:
                        att = attendance_obj.create({
                            'employee_id': emp.id,
                            'check_in': log.punch_time,
                            'zk_device_id': log.device_id.id if log.device_id else False,
                            'zk_checkin_log_id': log.id,
                        })
                        log.write({'state': 'processed', 'attendance_id': att.id, 'error_message': False})
                        processed_count += 1

                elif direction == 'check_out':
                    if open_attendance:
                        if log.punch_time >= open_attendance.check_in:
                            open_attendance.write({
                                'check_out': log.punch_time,
                                'zk_checkout_log_id': log.id,
                            })
                            log.write({'state': 'processed', 'attendance_id': open_attendance.id, 'error_message': False})
                            processed_count += 1
                        else:
                            log.write({
                                'state': 'error',
                                'error_message': _("Checkout time (%s) is before checkin time (%s).") % (log.punch_time, open_attendance.check_in)
                            })
                    else:
                        # Checkout without prior checkin: Create single attendance record
                        att = attendance_obj.create({
                            'employee_id': emp.id,
                            'check_in': log.punch_time,
                            'check_out': log.punch_time,
                            'zk_device_id': log.device_id.id if log.device_id else False,
                            'zk_checkout_log_id': log.id,
                        })
                        log.write({
                            'state': 'processed',
                            'attendance_id': att.id,
                            'error_message': _("Missing prior Check-In. Closed at checkout timestamp.")
                        })
                        processed_count += 1

                else:
                    # Auto-Detect Mode: Toggles Check-In vs Check-Out based on active state
                    if open_attendance:
                        hours_open = (log.punch_time - open_attendance.check_in).total_seconds() / 3600.0
                        if hours_open > max_shift_hours:
                            # Auto-close expired shift
                            auto_close_dt = open_attendance.check_in + timedelta(hours=max_shift_hours)
                            open_attendance.write({'check_out': auto_close_dt})
                            # Create new check-in
                            att = attendance_obj.create({
                                'employee_id': emp.id,
                                'check_in': log.punch_time,
                                'zk_device_id': log.device_id.id if log.device_id else False,
                                'zk_checkin_log_id': log.id,
                            })
                            log.write({'state': 'processed', 'attendance_id': att.id, 'error_message': False})
                            processed_count += 1
                        elif log.punch_time > open_attendance.check_in:
                            # Close open attendance as check-out
                            open_attendance.write({
                                'check_out': log.punch_time,
                                'zk_checkout_log_id': log.id,
                            })
                            log.write({'state': 'processed', 'attendance_id': open_attendance.id, 'error_message': False})
                            processed_count += 1
                        else:
                            log.write({
                                'state': 'error',
                                'error_message': _("Punch timestamp is earlier than current check-in.")
                            })
                    else:
                        # No open attendance, create new check-in
                        att = attendance_obj.create({
                            'employee_id': emp.id,
                            'check_in': log.punch_time,
                            'zk_device_id': log.device_id.id if log.device_id else False,
                            'zk_checkin_log_id': log.id,
                        })
                        log.write({'state': 'processed', 'attendance_id': att.id, 'error_message': False})
                        processed_count += 1

        return processed_count

    def action_reprocess(self):
        """ Resets logs to draft and re-runs processing. """
        self.write({'state': 'draft', 'error_message': False})
        return self.action_process_logs()

    def action_mark_duplicate(self):
        """ Manually marks logs as duplicate. """
        self.write({'state': 'duplicate', 'error_message': _("Manually marked as duplicate.")})

    @api.model
    def _cron_process_pending_logs(self):
        """ Scheduled cron to process any draft punch logs. """
        pending = self.search([('state', '=', 'draft')], limit=500)
        if pending:
            _logger.info("Biometric Device Cron: Processing %d pending punch logs...", len(pending))
            pending.action_process_logs()

    @api.model
    def _cron_cleanup_old_logs(self):
        """ Scheduled cron to prune processed logs older than retention period. """
        ICP = self.env['ir.config_parameter'].sudo()
        retention_days = int(ICP.get_param('ridhira_zk_attendance.zk_log_retention_days', 90))
        if retention_days > 0:
            cutoff = fields.Datetime.now() - timedelta(days=retention_days)
            old_logs = self.search([
                ('state', 'in', ['processed', 'duplicate']),
                ('punch_time', '<', cutoff)
            ])
            if old_logs:
                _logger.info("Biometric Device Cron: Pruning %d raw punch logs older than %d days.", len(old_logs), retention_days)
                old_logs.unlink()
