# -*- coding: utf-8 -*-
# Part of Ridhira Technologies. See LICENSE file for full copyright and licensing details.

import json
import logging
from datetime import datetime
from odoo import http, fields
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class ZkApiController(http.Controller):

    @http.route(['/api/biometric/punch'], type='json', auth='none', methods=['POST'], csrf=False)
    def api_biometric_punch(self, **kwargs):
        """
        Universal REST API Endpoint to submit biometric attendance punches.
        Accepts structured JSON payload from custom edge proxies, mobile apps, or IoT hubs.
        Payload format:
        {
            "token": "optional_secret_token",
            "device_sn": "SN123456",
            "punches": [
                {
                    "user_id": "101",
                    "timestamp": "2026-10-25 08:30:00",
                    "type": "check_in",
                    "verify": "1"
                }
            ]
        }
        """
        data = request.jsonrequest or {}
        token = data.get('token')
        device_sn = data.get('device_sn')
        punches = data.get('punches', [])

        ICP = request.env['ir.config_parameter'].sudo()
        expected_token = ICP.get_param('ridhira_zk_attendance.zk_adms_secret_token')
        if expected_token and token != expected_token:
            return {'status': 'error', 'message': 'Unauthorized: Invalid token.'}

        if not punches:
            return {'status': 'error', 'message': 'Empty punches list.'}

        machine_obj = request.env['zk.machine'].sudo()
        log_obj = request.env['zk.attendance.log'].sudo()

        device = machine_obj.search([('serial_number', '=', device_sn)], limit=1) if device_sn else False
        company = device.company_id if device else request.env['res.company'].sudo().search([], limit=1)

        created_logs = request.env['zk.attendance.log'].sudo()
        created_count = 0

        for p in punches:
            uid_str = str(p.get('user_id', '')).strip()
            time_str = p.get('timestamp')
            p_type = p.get('type', 'auto')
            v_type = str(p.get('verify', '1'))

            if not uid_str or not time_str:
                continue

            try:
                punch_dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue

            existing = log_obj.search([
                ('device_sn', '=', device_sn),
                ('device_user_id', '=', uid_str),
                ('punch_time', '=', punch_dt),
            ], limit=1)

            if not existing:
                emp = device._match_employee_for_user_id(uid_str) if device else log_obj._find_matching_employee(uid_str, company.id if company else 1)
                log = log_obj.create({
                    'device_id': device.id if device else False,
                    'device_sn': device_sn,
                    'device_user_id': uid_str,
                    'employee_id': emp.id if emp else False,
                    'punch_time': punch_dt,
                    'punch_type': p_type if p_type in ['check_in', 'check_out', 'break_out', 'break_in', 'auto'] else 'auto',
                    'verify_type': v_type if v_type in ['0', '1', '2', '3', '4', '15'] else '1',
                    'source': 'api',
                    'company_id': company.id if company else 1,
                    'raw_data': json.dumps(p),
                })
                created_logs |= log
                created_count += 1

        if device:
            device.write({'last_activity': fields.Datetime.now()})

        # Process if auto_process is active
        processed_count = 0
        if created_logs and ICP.get_param('ridhira_zk_attendance.zk_auto_process_logs', 'True') == 'True':
            processed_count = created_logs.action_process_logs()

        return {
            'status': 'success',
            'received': len(punches),
            'created': created_count,
            'processed': processed_count,
        }

    @http.route(['/api/biometric/device/status'], type='http', auth='none', methods=['GET'], csrf=False)
    def api_device_status(self):
        """ Health check endpoint returning status of biometric service. """
        devices_cnt = request.env['zk.machine'].sudo().search_count([])
        online_cnt = request.env['zk.machine'].sudo().search_count([('state', '=', 'online')])
        res = {
            'system': 'Ridhira Odoo 20 ZK Biometric device Integration',
            'version': '20.0.1.0.0',
            'status': 'healthy',
            'total_devices': devices_cnt,
            'online_devices': online_cnt,
            'timestamp': fields.Datetime.now().isoformat(),
        }
        return Response(json.dumps(res), status=200, content_type='application/json')
