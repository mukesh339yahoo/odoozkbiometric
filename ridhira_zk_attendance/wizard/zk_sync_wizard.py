# -*- coding: utf-8 -*-
# Part of Ridhira Technologies. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ZkSyncWizard(models.TransientModel):
    _name = 'zk.sync.wizard'
    _description = 'Biometric Device Manual Sync Wizard'

    device_ids = fields.Many2many('zk.machine', string='Target Devices', required=True,
                                  default=lambda self: self.env['zk.machine'].search([('active', '=', True)]))
    operation = fields.Selection([
        ('download_attendance', 'Download Attendance Logs & Process'),
        ('process_pending', 'Process All Pending Raw Logs in Odoo'),
        ('download_users', 'Download Users from Devices'),
        ('sync_time', 'Synchronize Device Clocks with Server'),
    ], string='Sync Operation', default='download_attendance', required=True)

    clear_device_logs = fields.Boolean(string='Clear Device Memory After Download', default=False,
                                       help='Deletes downloaded punch logs from device to free hardware storage.')

    def action_execute_sync(self):
        self.ensure_one()
        if not self.device_ids and self.operation != 'process_pending':
            raise UserError(_("Please select at least one biometric device."))

        msg_list = []
        if self.operation == 'download_attendance':
            total_logs = 0
            for dev in self.device_ids:
                if dev.protocol in ['tcp', 'udp']:
                    try:
                        res = dev.action_download_attendance(auto_process=True)
                        msg_list.append(f"{dev.name}: Success")
                    except Exception as e:
                        msg_list.append(f"{dev.name}: Error - {str(e)}")
            summary = "\n".join(msg_list)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Download Completed"),
                    'message': summary or _("Attendance download finished."),
                    'type': 'success',
                    'sticky': False,
                }
            }

        elif self.operation == 'process_pending':
            pending = self.env['zk.attendance.log'].search([('state', '=', 'draft')])
            cnt = pending.action_process_logs()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Processing Completed"),
                    'message': _("Processed %d raw logs into hr.attendance records.") % cnt,
                    'type': 'success',
                }
            }

        elif self.operation == 'download_users':
            for dev in self.device_ids:
                if dev.protocol in ['tcp', 'udp']:
                    try:
                        dev.action_download_users()
                        msg_list.append(f"{dev.name}: Users downloaded")
                    except Exception as e:
                        msg_list.append(f"{dev.name}: Error - {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("User Sync Finished"),
                    'message': "\n".join(msg_list),
                    'type': 'info',
                }
            }

        elif self.operation == 'sync_time':
            for dev in self.device_ids:
                try:
                    dev.action_sync_device_time()
                    msg_list.append(f"{dev.name}: Time synced")
                except Exception as e:
                    msg_list.append(f"{dev.name}: Error - {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Clock Sync Finished"),
                    'message': "\n".join(msg_list),
                    'type': 'success',
                }
            }
