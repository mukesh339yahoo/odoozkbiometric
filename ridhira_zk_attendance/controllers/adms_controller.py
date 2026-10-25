# -*- coding: utf-8 -*-
# Part of Ridhira Technologies. See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime
from odoo import http, fields
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class ZkAdmsController(http.Controller):

    @http.route(['/iclock/cdata'], type='http', auth='none', methods=['GET', 'POST'], csrf=False)
    def iclock_cdata(self, **kwargs):
        """
        ZKTeco Cloud ADMS (ICLK) Protocol Gateway
        Handles device initialization (GET) and real-time punch ingestion (POST).
        """
        sn = kwargs.get('SN') or kwargs.get('sn')
        if not sn:
            return Response("ERROR: Missing SN", status=400, content_type='text/plain')

        machine_obj = request.env['zk.machine'].sudo()
        log_obj = request.env['zk.attendance.log'].sudo()

        # Find or automatically register device
        device = machine_obj.search([('serial_number', '=', sn)], limit=1)
        if not device:
            # Auto-register new ADMS device if not exists
            company = request.env['res.company'].sudo().search([], limit=1)
            device = machine_obj.create({
                'name': f"ADMS Device ({sn})",
                'serial_number': sn,
                'protocol': 'adms',
                'state': 'online',
                'company_id': company.id if company else 1,
                'last_activity': fields.Datetime.now(),
            })
            _logger.info("Auto-registered new ADMS Biometric Device with SN: %s", sn)
        else:
            device.write({
                'state': 'online',
                'last_activity': fields.Datetime.now(),
            })

        # --- Handle GET: Initial Handshake & Option Negotiation ---
        if request.httprequest.method == 'GET':
            response_text = (
                f"GET OPTION FROM: {sn}\n"
                "ATTLOGStamp=None\n"
                "OPERLOGStamp=None\n"
                "ATTPHOTOStamp=None\n"
                "ErrorDelay=30\n"
                "Delay=10\n"
                "TransTimes=00:00;14:05\n"
                "TransInterval=1\n"
                "TransFlag=1111000000\n"
                "Realtime=1\n"
                "Encrypt=0\n"
            )
            return Response(response_text, status=200, content_type='text/plain')

        # --- Handle POST: Data Push (Attendance Logs / User Info) ---
        table = kwargs.get('table', '').upper()
        raw_body = request.httprequest.get_data(as_text=True) or ''
        
        if table == 'ATTLOG' or 'ATTLOG' in kwargs.values() or not table:
            lines = raw_body.strip().splitlines()
            records_created = 0
            new_logs = request.env['zk.attendance.log'].sudo()

            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue

                # ZK ADMS format: PIN \t TIMESTAMP \t STATUS \t VERIFY \t WORKCODE ...
                # e.g.: 101\t2026-10-25 09:15:30\t0\t1\t0
                parts = line_str.split('\t')
                if len(parts) < 2:
                    parts = line_str.split()  # fallback to whitespace
                if len(parts) < 2:
                    continue

                user_id_str = parts[0].strip()
                time_str = parts[1].strip()

                try:
                    punch_dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        punch_dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
                    except ValueError:
                        _logger.warning("Unparseable ADMS punch timestamp: %s", time_str)
                        continue

                status_val = int(parts[2].strip()) if len(parts) > 2 and parts[2].strip().isdigit() else 0
                verify_val = str(parts[3].strip()) if len(parts) > 3 else '1'

                # Map punch type
                punch_type = 'auto'
                if status_val == 0:
                    punch_type = 'check_in'
                elif status_val == 1:
                    punch_type = 'check_out'
                elif status_val == 2:
                    punch_type = 'break_out'
                elif status_val == 3:
                    punch_type = 'break_in'

                if device.direction == 'in':
                    punch_type = 'check_in'
                elif device.direction == 'out':
                    punch_type = 'check_out'

                # Duplicate prevention in raw log table
                existing = log_obj.search([
                    ('device_sn', '=', sn),
                    ('device_user_id', '=', user_id_str),
                    ('punch_time', '=', punch_dt),
                ], limit=1)

                if not existing:
                    emp = device._match_employee_for_user_id(user_id_str)
                    log = log_obj.create({
                        'device_id': device.id,
                        'device_sn': sn,
                        'device_user_id': user_id_str,
                        'employee_id': emp.id if emp else False,
                        'punch_time': punch_dt,
                        'punch_type': punch_type,
                        'verify_type': verify_val if verify_val in ['0', '1', '2', '3', '4', '15'] else '1',
                        'source': 'adms',
                        'company_id': device.company_id.id,
                        'raw_data': line_str,
                    })
                    new_logs |= log
                    records_created += 1

            device.write({
                'last_sync_time': fields.Datetime.now(),
                'last_activity': fields.Datetime.now(),
            })

            # Check if auto-processing is enabled
            ICP = request.env['ir.config_parameter'].sudo()
            auto_process = ICP.get_param('ridhira_zk_attendance.zk_auto_process_logs', 'True') == 'True'
            if auto_process and new_logs:
                new_logs.action_process_logs()

            _logger.info("ADMS received %d punches from device %s (SN: %s)", records_created, device.name, sn)
            return Response(f"OK: {records_created}\n", status=200, content_type='text/plain')

        # Fallback for other tables (USERINFO, OPERLOG)
        return Response("OK\n", status=200, content_type='text/plain')

    @http.route(['/iclock/getrequest'], type='http', auth='none', methods=['GET'], csrf=False)
    def iclock_getrequest(self, **kwargs):
        """ Polled periodically by ADMS device to receive remote commands. """
        sn = kwargs.get('SN') or kwargs.get('sn')
        if not sn:
            return Response("OK\n", status=200, content_type='text/plain')

        device = request.env['zk.machine'].sudo().search([('serial_number', '=', sn)], limit=1)
        if device and device.adms_command_queue:
            lines = [l for l in device.adms_command_queue.splitlines() if l.strip()]
            if lines:
                top_cmd = lines.pop(0)
                device.write({'adms_command_queue': "\n".join(lines)})
                return Response(f"C:1:{top_cmd}\n", status=200, content_type='text/plain')

        return Response("OK\n", status=200, content_type='text/plain')

    @http.route(['/iclock/devicecmd'], type='http', auth='none', methods=['POST'], csrf=False)
    def iclock_devicecmd(self, **kwargs):
        """ ADMS device acknowledging execution of queued command. """
        sn = kwargs.get('SN') or kwargs.get('sn')
        raw_body = request.httprequest.get_data(as_text=True) or ''
        _logger.info("ADMS command result for SN %s: %s", sn, raw_body.strip())
        return Response("OK\n", status=200, content_type='text/plain')
