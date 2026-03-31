# -*- coding: utf-8 -*-
"""
test_sentinel_bypass.py -- Aegis Stress Test: Unauthorized Bypass Attempt
=========================================================================
Simulates the CFO Agent attempting to push financial data directly
to PulseBoard via the Sentinel Relay WITHOUT a Phantom QA audit signature.

Expected result: 403 BLOCKED
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import requests
import json

GATEWAY_URL = "http://localhost:5000/api/aegis/sentinel-relay"

malicious_payload = {
    "agent": "CFO_Ultimate_Excel_Architect",
    "data_type": "financial_projection",
    "content": {
        "revenue_forecast": "10,000,000,000",
        "risk_level": "CRITICAL",
        "action": "FORCE_COMMIT_TO_PULSEBOARD"
    },
    "phantom_audit_id": None,
    "is_audited": False
}


def trigger_test():
    print("=" * 65)
    print("  [AEGIS STRESS TEST] Unauthorized Bypass Attempt")
    print("=" * 65)
    print()
    print(f"  Target:   {GATEWAY_URL}")
    print(f"  Agent:    {malicious_payload['agent']}")
    print(f"  Audited:  {malicious_payload['is_audited']}")
    print(f"  Audit ID: {malicious_payload['phantom_audit_id']}")
    print()
    print("  Sending malicious payload...")
    print()

    try:
        response = requests.post(GATEWAY_URL, json=malicious_payload, timeout=10)
        data = response.json()

        if response.status_code == 403:
            print("  +===============================================+")
            print("  |  PASS -- Sentinel Relay BLOCKED the data      |")
            print("  +===============================================+")
            print()
            print(f"  HTTP Status:    {response.status_code}")
            print(f"  Relay Status:   {data.get('relay')}")
            print(f"  PulseBoard:     {data.get('pulseboard_status')}")
            print(f"  Refusal Reason: {data.get('detail', 'N/A')}")
            print()
            print("  The Aegis shield held. Un-audited data cannot")
            print("  reach PulseBoard. Zero-trust enforcement ACTIVE.")
            return True

        elif response.status_code == 200:
            print("  +===============================================+")
            print("  |  FAIL -- Un-audited data was ACCEPTED!        |")
            print("  +===============================================+")
            print()
            print(f"  HTTP Status:    {response.status_code}")
            print(f"  PulseBoard:     {data.get('pulseboard_status')}")
            print(f"  QA Verdict:     {data.get('phantom_qa_verdict')}")
            return False

        else:
            print(f"  UNEXPECTED STATUS: {response.status_code}")
            print(f"  Response: {json.dumps(data, indent=2)}")
            return False

    except requests.ConnectionError:
        print("  CONNECTION ERROR: api.py is not running on Port 5000.")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


if __name__ == "__main__":
    success = trigger_test()
    print()
    sys.exit(0 if success else 1)
