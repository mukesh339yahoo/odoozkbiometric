# -*- coding: utf-8 -*-
# Part of Ridhira Technologies. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    zk_user_id = fields.Char(string='Biometric Device User ID / PIN', copy=False, index=True,
                             help='The exact User ID / PIN configured on the biometric devices for this employee.')
    zk_machine_user_ids = fields.One2many('zk.machine.user', 'employee_id', string='Enrolled Biometric Devices')
    zk_attendance_log_ids = fields.One2many('zk.attendance.log', 'employee_id', string='Biometric Raw Logs')
    zk_attendance_log_count = fields.Integer(string='Biometric Logs Count', compute='_compute_zk_log_count')

    def _compute_zk_log_count(self):
        log_obj = self.env['zk.attendance.log']
        for emp in self:
            emp.zk_attendance_log_count = log_obj.search_count([('employee_id', '=', emp.id)])

    def action_view_zk_logs(self):
        self.ensure_one()
        return {
            'name': _("Raw Biometric Logs - %s") % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'zk.attendance.log',
            'view_mode': 'list,form,pivot',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def action_open_upload_wizard(self):
        self.ensure_one()
        return {
            'name': _("Upload Employee to Biometric Devices"),
            'type': 'ir.actions.act_window',
            'res_model': 'zk.upload.user.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_employee_ids': [(6, 0, [self.id])],
            }
        }
