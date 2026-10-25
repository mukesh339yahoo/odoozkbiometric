#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Direct TCP / UDP Connection Tester for ZKTeco Biometric Devices.
Validates socket reachability, device handshake, and pyzk protocol communication.
"""

import sys
import socket

def test_tcp_ping(ip, port=4370, timeout=3):
    print(f"[*] Testing raw TCP socket to {ip}:{port} (timeout={timeout}s)...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, int(port)))
        s.close()
        print(f"[+] TCP Port {port} is reachable on {ip}!")
        return True
    except Exception as e:
        print(f"[-] Cannot reach TCP port {port} on {ip}: {e}")
        return False

def test_zk_library(ip, port=4370):
    try:
        from zk import ZK
    except ImportError:
        print("[-] 'pyzk' is not installed. Run: pip install pyzk")
        return False

    print(f"[*] Connecting via pyzk to {ip}:{port}...")
    zk = ZK(ip, port=int(port), timeout=5, password=0, force_udp=False, ommit_ping=False)
    conn = None
    try:
        conn = zk.connect()
        sn = conn.get_serialnumber()
        firmware = conn.get_firmware_version()
        platform = conn.get_platform()
        users = conn.get_users()
        print(f"[+] Connected successfully!")
        print(f"    - Serial Number : {sn}")
        print(f"    - Firmware      : {firmware}")
        print(f"    - Platform      : {platform}")
        print(f"    - Users Count   : {len(users) if users else 0}")
        return True
    except Exception as e:
        print(f"[-] pyzk connection failed: {e}")
        return False
    finally:
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_tcp_connection.py <DEVICE_IP> [PORT]")
        print("Example: python test_tcp_connection.py 192.168.1.201 4370")
        sys.exit(1)

    device_ip = sys.argv[1]
    device_port = int(sys.argv[2]) if len(sys.argv) > 2 else 4370

    if test_tcp_ping(device_ip, device_port):
        test_zk_library(device_ip, device_port)
