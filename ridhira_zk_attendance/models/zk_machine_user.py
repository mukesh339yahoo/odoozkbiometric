# -*- coding: utf-8 -*-
# Part of Ridhira Technologies. See LICENSE file for full copyright and licensing details.

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ZkMachineUser(models.Model):
    _name = 'zk.machine.user'
    _description = 'Biometric Device User Mapping'
    _order = 'device_id, device_user_id'

    name = fields.Char(string='Name on Device', required=True)
    device_user_id = fields.Char(string='Device User ID / PIN', required=True, index=True)
    device_id = fields.Many2one('zk.machine', string='Biometric Device', required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one('hr.employee', string='Linked Odoo Employee', index=True,
                                  domain="[('company_id', '=', company_id)]")
    
    badge_number = fields.Char(string='RFID Card / Badge Number')
    privilege = fields.Selection([
        ('0', 'Standard User'),
        ('14', 'Super Administrator'),
        ('2', 'Manager'),
    ], string='Device Privilege', default='0', required=True)

    password = fields.Char(string='Device PIN Password')
    enabled = fields.Boolean(string='Enabled on Device', default=True)
    company_id = fields.Many2one('res.company', string='Company', related='device_id.company_id', store=True, readonly=True)
    last_sync = fields.Datetime(string='Last Synchronized', readonly=True)

    _sql_constraints = [
        ('unique_device_user_id_per_device', 'unique(device_id, device_user_id)',
         'The Device User ID / PIN must be unique per biometric device!')
    ]

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            if not self.name or self.name.startswith("User "):
                self.name = self.employee_id.name
            if self.employee_id.barcode and not self.badge_number:
                self.badge_number = self.employee_id.barcode

    def action_upload_to_device(self):
        """ Uploads or updates this user profile onto the physical biometric device. """
        self.ensure_one()
        device = self.device_id
        if device.protocol == 'adms':
            # Queue ADMS command
            cmd = f"DATA UPDATE USERINFO PIN={self.device_user_id}\tName={self.name}\tPri={self.privilege}\tPasswd={self.password or ''}\tCard={self.badge_number or ''}"
            device.queue_adms_command(cmd)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("ADMS Command Queued"),
                    'message': _("User upload command queued for ADMS device %s.") % device.name,
                    'type': 'info',
                }
            }

        zk = device._get_zk_instance()
        conn = None
        try:
            conn = zk.connect()
            conn.disable_device()
            
            # Convert user_id to int if numeric
            uid_num = int(self.device_user_id) if self.device_user_id.isdigit() else 1
            card_val = int(self.badge_number) if (self.badge_number and self.badge_number.isdigit()) else 0
            priv_val = int(self.privilege or 0)

            conn.set_user(
                uid=uid_num,
                name=self.name or '',
                privilege=priv_val,
                password=self.password or '',
                group_id='',
                user_id=self.device_user_id,
                card=card_val
            )
            conn.enable_device()
            self.write({'last_sync': fields.Datetime.now()})

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("User Uploaded!"),
                    'message': _("User '%s' (ID: %s) uploaded to %s.") % (self.name, self.device_user_id, device.name),
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(_("Failed to upload user to %s: %s") % (device.name, str(e)))
        finally:
            if conn:
                try:
                    conn.enable_device()
                    conn.disconnect()
                except Exception:
                    pass

    def action_delete_from_device(self):
        """ Deletes this user from physical biometric device. """
        self.ensure_one()
        device = self.device_id
        if device.protocol == 'adms':
            cmd = f"DATA DELETE USERINFO PIN={self.device_user_id}"
            device.queue_adms_command(cmd)
            self.unlink()
            return

        zk = device._get_zk_instance()
        conn = None
        try:
            conn = zk.connect()
            conn.disable_device()
            uid_num = int(self.device_user_id) if self.device_user_id.isdigit() else 1
            conn.delete_user(uid=uid_num, user_id=self.device_user_id)
            conn.enable_device()
            self.unlink()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("User Deleted"),
                    'message': _("User deleted from device and Odoo mapping removed."),
                    'type': 'warning',
                }
            }
        except Exception as e:
            raise UserError(_("Failed to delete user from %s: %s") % (device.name, str(e)))
        finally:
            if conn:
                try:
                    conn.enable_device()
                    conn.disconnect()
                except Exception:
                    pass
