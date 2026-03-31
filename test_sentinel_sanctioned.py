# -*- coding: utf-8 -*-
"""
test_sentinel_sanctioned.py -- Aegis Sanctioned Relay Test
==========================================================
Simulates the CORRECT path: CFO financial data that has been
pre-audited by Phantom QA with a valid audit_id and is_audited=True.

Expected result: 200 with pre-flight PASSED
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import requests
import json
from datetime import datetime, timezone

GATEWAY_URL = "http://localhost:5000/api/aegis/sentinel-relay"

sanctioned_payload = {
    "agent": "CFO_Ultimate_Excel_Architect",
    "data_type": "financial_projection",
    "content": {
        "revenue_forecast": "2,500,000",
        "risk_level": "MODERATE",
        "action": "STANDARD_PULSEBOARD_UPDATE",
        "quarter": "Q2-2026"
    },
    "phantom_audit_id": "PQA-AUDIT-2026-0330-001",
    "is_audited": True,
    "audited_at": datetime.now(timezone.utc).isoformat(),
    "auditor": "Phantom_QA_Elite"
}


def trigger_test():
    print("=" * 65)
    print("  [AEGIS SANCTIONED TEST] Authorized Relay Path")
    print("=" * 65)
    print()
    print(f"  Target:   {GATEWAY_URL}")
    print(f"  Agent:    {sanctioned_payload['agent']}")
    print(f"  Audited:  {sanctioned_payload['is_audited']}")
    print(f"  Audit ID: {sanctioned_payload['phantom_audit_id']}")
    print()
    print("  Sending sanctioned payload...")
    print()

    try:
        response = requests.post(GATEWAY_URL, json=sanctioned_payload, timeout=15)
        data = response.json()

        if response.status_code == 403:
            print("  +===============================================+")
            print("  |  FAIL -- Sanctioned data was REJECTED!        |")
            print("  +===============================================+")
            print()
            print(f"  HTTP Status: {response.status_code}")
            print(f"  Detail:      {data.get('detail')}")
            return False

        elif response.status_code == 200:
            pulseboard = data.get("pulseboard_status", "?")
            qa_verdict = data.get("phantom_qa_verdict", {})
            qa_status = qa_verdict.get("status", "?")

            print("  +===============================================+")
            print("  |  PASS -- Pre-flight gate accepted data        |")
            print("  +===============================================+")
            print()
            print(f"  HTTP Status:     {response.status_code}")
            print(f"  Relay Status:    {data.get('relay')}")
            print(f"  QA Verdict:      {qa_status}")
            print(f"  PulseBoard:      {pulseboard}")
            print()

            if pulseboard == "COMMITTED":
                print("  Full sanctioned path COMPLETE.")
                print("  Data successfully committed to PulseBoard.")
            elif pulseboard == "BLOCKED":
                print("  Pre-flight passed but QA verdict blocked commit.")
                print(f"  QA Status: {qa_status}")
                if qa_status == "UNREACHABLE":
                    print("  Phantom QA Elite is offline -- data held in quarantine.")
                    print("  This is expected if Port 5030 is not running.")
            return True

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
