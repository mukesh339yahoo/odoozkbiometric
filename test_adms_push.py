#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZKTeco Cloud ADMS Push Protocol Simulator
Simulates a physical ZKTeco biometric terminal sending real-time punch logs to Odoo over HTTP.
"""

import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime

ODOO_URL = "http://localhost:8069"
DEVICE_SN = "ZKTEST98765432"
TEST_USER_ID = "101"


def test_handshake():
    url = f"{ODOO_URL}/iclock/cdata?SN={DEVICE_SN}&options=all&language=83"
    print(f"[*] Step 1: Sending ADMS device initialization GET request to {url}...")
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=5) as response:
            body = response.read().decode('utf-8')
            print(f"[+] Handshake Response (Status {response.status}):\n{body.strip()}")
            return True
    except Exception as e:
        print(f"[-] Handshake failed: {e}")
        return False


def test_push_punch(user_id=TEST_USER_ID, status=0):
    url = f"{ODOO_URL}/iclock/cdata?SN={DEVICE_SN}&table=ATTLOG"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # ZK ADMS punch payload line: PIN \t TIMESTAMP \t STATUS \t VERIFY \t WORKCODE
    # Status: 0=Check-in, 1=Check-out
    payload = f"{user_id}\t{now_str}\t{status}\t1\t0\t0\t0\n"
    print(f"[*] Step 2: Pushing attendance punch (User: {user_id}, Time: {now_str}, Status: {status})...")
    try:
        data = payload.encode('utf-8')
        req = urllib.request.Request(url, data=data, method='POST', headers={'Content-Type': 'text/plain'})
        with urllib.request.urlopen(req, timeout=5) as response:
            body = response.read().decode('utf-8')
            print(f"[+] Punch Push Response (Status {response.status}): {body.strip()}")
            return True
    except Exception as e:
        print(f"[-] Punch push failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print(" Ridhira ZKTeco Biometric ADMS Simulator")
    print("=" * 60)
    if test_handshake():
        time.sleep(1)
        test_push_punch(TEST_USER_ID, status=0)  # Check-in
        time.sleep(2)
        test_push_punch(TEST_USER_ID, status=1)  # Check-out
        print("\n[✔] Simulation test finished successfully!")
    else:
        print("\n[!] Ensure your Odoo instance is running on http://localhost:8069.")
