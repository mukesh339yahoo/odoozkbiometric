# -*- coding: utf-8 -*-
# Part of Ridhira Technologies. See LICENSE file for full copyright and licensing details.

{
    'name': 'Ridhira Odoo 20 ZK Biometric device Integration',
    'version': '20.0.1.0.0',
    'summary': 'Next-Gen ZKTeco Biometric Device Integration with Direct Network Polling & Cloud ADMS Push Protocol for Odoo 20 HR Attendance',
    'sequence': 25,
    'description': """
Ridhira Odoo 20 ZK Biometric Device Integration
================================================
Next-generation enterprise biometric attendance solution for Odoo 20.

Key Advantages over standard modules (such as hr_zk_attendance):
--------------------------------------------------------------
* **Dual Connectivity**:
    - **Direct Network Polling**: Fast TCP/IP (port 4370) and UDP with custom timeouts and comm keys.
    - **Cloud ADMS / Push Server**: Built-in ICLK server (/iclock/cdata) allows biometric devices in remote branches worldwide to push punches in real time over HTTP/HTTPS with ZERO port-forwarding or static IP required!
    - **Universal REST Webhook API**: Secure JSON punch ingestion for IoT hubs, edge proxies, and mobile clocks.
* **Full Raw Punch Audit Trail (zk.attendance.log)**:
    - Never lose a punch. All scans are audited with timestamp, punch type (check-in/out, breaks), verify mode (finger, face, RFID, password), device serial, and processing state.
* **Intelligent Attendance Pairing Engine**:
    - Smart pairing avoids missing checkouts and overnight shift corruption.
    - Configurable duplicate punch suppression (e.g. ignores accidental double-taps within 5 minutes).
    - Max shift duration protection against runaway open attendances.
* **Bidirectional Employee & User Sync**:
    - Upload employees (Name, Badge, Password, Privilege) to biometric devices directly from Odoo.
    - Download and auto-map device users to Odoo employees by Badge ID, PIN, or Work Email.
* **Remote Device Telemetry & Control**:
    - Live Online/Offline status, firmware, serial number, log count, user count.
    - Remote restart, clock synchronization, device sound beep, clear logs with safety checks.
* **Multi-Company & Multi-Location**:
    - Complete company isolation and gate-specific directional punch rules (Entry Only, Exit Only, Bidirectional).
* **Zero-Crash Resilience**:
    - Gracefully handles pyzk dependency without blocking Odoo server startup. ADMS push works even without pyzk!
    """,
    'author': 'Ridhira Technologies, Pune, India',
    'support': 'ridhiratech@gmail.com',
    'website': 'https://ridhira.desigoogly.com',
    'category': 'Human Resources/Attendances',
    'depends': ['base', 'hr', 'hr_attendance'],
    'data': [
        'security/zk_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'wizard/zk_sync_wizard_views.xml',
        'wizard/zk_upload_user_wizard_views.xml',
        'views/zk_machine_views.xml',
        'views/zk_machine_user_views.xml',
        'views/zk_attendance_log_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_attendance_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_views.xml',
    ],
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
    ],
    'license': 'OPL-1',
    'installable': True,
    'application': True,
    'auto_install': False,
}
