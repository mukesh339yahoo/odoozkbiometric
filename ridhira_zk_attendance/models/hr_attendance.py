# -*- coding: utf-8 -*-
# Part of Ridhira Technologies. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    zk_device_id = fields.Many2one('zk.machine', string='Biometric Terminal', ondelete='set null',
                                   help='Biometric machine from which this attendance was recorded.')
    zk_checkin_log_id = fields.Many2one('zk.attendance.log', string='Check-in Raw Log', ondelete='set null')
    zk_checkout_log_id = fields.Many2one('zk.attendance.log', string='Check-out Raw Log', ondelete='set null')
    is_biometric = fields.Boolean(string='Biometric Punch', compute='_compute_is_biometric', store=True)

    @api.depends('zk_device_id', 'zk_checkin_log_id', 'zk_checkout_log_id')
    def _compute_is_biometric(self):
        for att in self:
            att.is_biometric = bool(att.zk_device_id or att.zk_checkin_log_id or att.zk_checkout_log_id)
