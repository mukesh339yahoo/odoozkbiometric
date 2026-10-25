# Ridhira Odoo 20 ZK Biometric Device Integration

Enterprise Biometric Device Attendance Integration (Direct TCP/UDP & Cloud ADMS Push Protocol) for Odoo 20 HR Attendance.

Developed by **Ridhira Technologies, Pune, India**  
Website: [https://ridhira.desigoogly.com](https://ridhira.desigoogly.com)  
Support: [ridhiratech@gmail.com](mailto:ridhiratech@gmail.com)  
WhatsApp: [+91 8208411979](https://api.whatsapp.com/send/?phone=918208411979) | Telegram: [@ridhiratech](https://t.me/ridhiratech)

---

## 🚀 Why Ridhira Biometric Integration is Superior to `hr_zk_attendance`

Standard community modules such as `hr_zk_attendance` suffer from critical limitations in production environments:
1. **Network Firewall / NAT Limitations:** `hr_zk_attendance` only supports local network TCP polling. If your Odoo is hosted on cloud (AWS, Odoo.sh, DigitalOcean) and your physical machines are in remote branch offices, direct TCP cannot reach devices without complex VPNs or static public IPs.
   - **Ridhira Solution:** Supports **Cloud ADMS / ICLK Push Protocol** where the biometric device connects outward to Odoo over HTTP/HTTPS in real time! Zero port-forwarding or public IP required on client sites.
2. **Missing Raw Punch Audit Trail:** Basic modules attempt to write directly to `hr.attendance`. If an employee taps twice or clocks out without clocking in, logs are lost or corrupted.
   - **Ridhira Solution:** Dedicated `zk.attendance.log` audit trail preserving every scan, verify mode (face, finger, badge, password), timestamp, device serial, and raw payload.
3. **Duplicate Punch Suppression:**
   - **Ridhira Solution:** Intelligent filter suppresses accidental double-taps within a configurable window (e.g. 5 minutes).
4. **Shift Boundary Protection:**
   - **Ridhira Solution:** Configurable maximum shift duration auto-closes forgotten checkouts and handles overnight shifts cleanly.
5. **Zero-Crash Resilience:**
   - **Ridhira Solution:** If `pyzk` is missing from the server, Odoo does NOT crash on startup. The module loads gracefully, alerts the admin, and allows Cloud ADMS Push to operate 100% independently without pyzk.

---

## 🛠️ Key Features

* **Dual Protocol Architecture:**
  * **Cloud ADMS (ICLK Push):** `/iclock/cdata`, `/iclock/getrequest`, `/iclock/devicecmd`
  * **Direct TCP/UDP Network Polling:** High-speed polling on port 4370 with password authentication (`comm_key`).
  * **Universal REST API:** Submit JSON punches from custom IoT hubs or edge proxies (`/api/biometric/punch`).
* **Hardware Controls & Telemetry:**
  * Test connection, clock synchronization, device reboot, speaker test beep, and safe log clearing.
  * Live status tracking (Online / Offline / Draft) with visual Kanban dashboard.
* **Bidirectional User Sync:**
  * Upload employees (Name, Badge ID, Privilege, Password) directly from Odoo to devices.
  * Download device users and auto-match to Odoo `hr.employee` records.
* **Directional Gate Rules:**
  * Assign terminals as Entry Only (Forces Check-In), Exit Only (Forces Check-Out), or Bidirectional.
* **Automated Background Schedulers:**
  * Periodic automated log download (every 15 minutes).
  * Automated background log processing.
  * Automated old raw log retention cleanup.

---

## 📦 Directory Structure

```
odoozkbiometric/
├── README.md
├── test_adms_push.py                     # Simulator for Cloud ADMS push testing
├── test_tcp_connection.py                 # Network & socket tester
└── ridhira_zk_attendance/                # Main Odoo 20 Addon
    ├── __init__.py
    ├── __manifest__.py
    ├── controllers/
    │   ├── __init__.py
    │   ├── adms_controller.py            # ZK ADMS / ICLK Push handler
    │   └── api_controller.py             # REST API Webhook handler
    ├── models/
    │   ├── __init__.py
    │   ├── zk_machine.py                 # Biometric device model
    │   ├── zk_machine_user.py            # Enrolled user mapping
    │   ├── zk_attendance_log.py          # Raw punch audit trail
    │   ├── hr_employee.py                # Employee extensions
    │   ├── hr_attendance.py              # Attendance model extensions
    │   └── res_config_settings.py        # System parameters
    ├── wizard/
    │   ├── __init__.py
    │   ├── zk_sync_wizard.py             # Manual bulk sync wizard
    │   ├── zk_sync_wizard_views.xml
    │   ├── zk_upload_user_wizard.py      # Employee device enrollment wizard
    │   └── zk_upload_user_wizard_views.xml
    ├── views/
    │   ├── zk_machine_views.xml          # Device kanban, list, form
    │   ├── zk_machine_user_views.xml     # User mapping views
    │   ├── zk_attendance_log_views.xml   # Raw punch logs & pivot
    │   ├── hr_employee_views.xml         # Employee form integration
    │   ├── hr_attendance_views.xml       # Attendance list & form tracking
    │   ├── res_config_settings_views.xml # Biometric settings
    │   └── menu_views.xml                # Menu structure under HR Attendance
    ├── data/
    │   ├── ir_sequence_data.xml          # Sequence numbers
    │   └── ir_cron_data.xml              # Scheduled cron jobs
    ├── security/
    │   ├── zk_security.xml               # Security groups & multi-company rules
    │   └── ir.model.access.csv           # Model permissions
    └── static/
        └── description/
            ├── index.html                # App store description page with QR codes
            ├── icon.png                  # App icon
            ├── banner.png                # App banner
            ├── whatsapp_qr.png           # WhatsApp support QR
            └── telegram_qr.png           # Telegram support QR
```

---

## ⚡ Installation & Quick Start

1. **Place the module in your Odoo custom addons directory:**
   ```bash
   git clone https://github.com/mukesh339yahoo/odoozkbiometric.git
   ```
2. **Install optional Python dependency (for direct TCP polling):**
   ```bash
   pip install pyzk
   ```
   *(Note: Cloud ADMS mode works natively without pyzk!)*
3. **Activate Developer Mode in Odoo** (Settings > General Settings).
4. Go to **Apps**, click **Update Apps List**, and search for **Ridhira Odoo 20 ZK Biometric device Integration**.
5. Click **Install**.

---

## 📞 Support & Setup Assistance

* **Website:** [https://ridhira.desigoogly.com](https://ridhira.desigoogly.com)
* **WhatsApp Support:** [+91 8208411979](https://api.whatsapp.com/send/?phone=918208411979)
* **Telegram Support:** [@ridhiratech](https://t.me/ridhiratech)
* **Email:** [ridhiratech@gmail.com](mailto:ridhiratech@gmail.com)
