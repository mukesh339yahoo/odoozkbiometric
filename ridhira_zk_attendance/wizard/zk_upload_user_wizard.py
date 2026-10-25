# -*- coding: utf-8 -*-
# Part of Ridhira Technologies. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ZkUploadUserWizard(models.TransientModel):
    _name = 'zk.upload.user.wizard'
    _description = 'Upload Employees to Biometric Devices Wizard'

    employee_ids = fields.Many2many('hr.employee', string='Employees to Upload', required=True)
    device_ids = fields.Many2many('zk.machine', string='Target Biometric Devices', required=True,
                                  default=lambda self: self.env['zk.machine'].search([('active', '=', True)]))
    privilege = fields.Selection([
        ('0', 'Standard User'),
        ('14', 'Super Administrator'),
        ('2', 'Manager'),
    ], string='Device Privilege', default='0', required=True)

    def action_upload(self):
        self.ensure_one()
        user_obj = self.env['zk.machine.user']
        uploaded_cnt = 0
        errors = []

        for emp in self.employee_ids:
            # Determine device PIN / User ID: prefer zk_user_id, then barcode, then ID
            user_id_val = emp.zk_user_id or emp.barcode or str(emp.id)
            if not emp.zk_user_id:
                emp.sudo().write({'zk_user_id': user_id_val})

            for dev in self.device_ids:
                # Find or create zk.machine.user
                m_user = user_obj.search([
                    ('device_id', '=', dev.id),
                    ('device_user_id', '=', user_id_val)
                ], limit=1)

                vals = {
                    'name': emp.name,
                    'device_id': dev.id,
                    'device_user_id': user_id_val,
                    'employee_id': emp.id,
                    'badge_number': emp.barcode or '',
                    'privilege': self.privilege,
                }
                if m_user:
                    m_user.write(vals)
                else:
                    m_user = user_obj.create(vals)

                try:
                    m_user.action_upload_to_device()
                    uploaded_cnt += 1
                except Exception as e:
                    errors.append(f"{emp.name} -> {dev.name}: {str(e)}")

        msg = _("Successfully enrolled/updated %d user assignments on selected devices.") % uploaded_cnt
        if errors:
            msg += "\n\nWarnings/Errors:\n" + "\n".join(errors)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Upload Complete"),
                'message': msg,
                'type': 'success' if not errors else 'warning',
                'sticky': bool(errors),
            }
        }
