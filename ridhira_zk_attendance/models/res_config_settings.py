# -*- coding: utf-8 -*-
# Part of Ridhira Technologies. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    zk_duplicate_threshold_minutes = fields.Integer(
        string='Duplicate Punch Filter Window (Minutes)',
        default=5,
        config_parameter='ridhira_zk_attendance.zk_duplicate_threshold_minutes',
        help='Suppresses multiple accidental punches from the same employee within this time window.'
    )

    zk_max_shift_hours = fields.Integer(
        string='Maximum Shift Duration (Hours)',
        default=16,
        config_parameter='ridhira_zk_attendance.zk_max_shift_hours',
        help='If an employee did not punch out, automatically closes open attendance after this duration.'
    )

    zk_auto_process_logs = fields.Boolean(
        string='Auto-Process Punches Instantly',
        default=True,
        config_parameter='ridhira_zk_attendance.zk_auto_process_logs',
        help='Automatically converts raw biometric punches to hr.attendance records upon download or push.'
    )

    zk_log_retention_days = fields.Integer(
        string='Raw Log Retention (Days)',
        default=90,
        config_parameter='ridhira_zk_attendance.zk_log_retention_days',
        help='Days to retain processed raw biometric punch logs before automated cleanup. Set 0 to keep forever.'
    )

    zk_adms_secret_token = fields.Char(
        string='Cloud ADMS / REST API Security Token',
        config_parameter='ridhira_zk_attendance.zk_adms_secret_token',
        help='Optional security token required for REST API punch submissions.'
    )
