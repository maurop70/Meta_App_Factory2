"""
Overwatch Sentinel Stress Test Harness
======================================
Validates the three-phase Sentinel Rules of Engagement:
1. Loop Intercept (3 errors in 120s) -> Snap-Back
2. Hallucination Detection -> Snap-Back
3. No-Bypass Zone Override (Financial/Security) -> Escalation
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta

# Add parent dir to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, FACTORY_DIR)

from nerve_center_v2 import NerveCenterV2

def run_stress_test():
    print(f"\n{'═'*60}")
    print(f"  🛰️  OVERWATCH SENTINEL: STRESS TEST HARNESS")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*60}\n")

    nc = NerveCenterV2()
    
    # --- TEST 1: Infinite Loop Detection (Safe Bypass) ---
    print("[TEST 1/4] Infinite Loop Detection (Safe Bypass)")
    loop_error = "Recursive logic failure in deliberation chain"
    loop_logs = []
    # Inject 3 identical logs in the last 60 seconds
    for i in range(3):
        loop_logs.append({
            "timestamp": (datetime.now() - timedelta(seconds=10*i)).isoformat(),
            "app_name": "MarketingAgent",
            "error": loop_error
        })
    
    # Write to telemetry file temporarily
    with open(nc.telemetry_path, "w", encoding="utf-8") as f:
        json.dump(loop_logs, f, indent=2)
    
    report = nc.scan_and_heal()
    actions = report.get("audit_trail", [])
    loop_intercepted = any(a["diagnosis_id"] == "INFINITE_LOOP" and a["action_taken"] == "sentinel_snap_back" for a in actions)
    
    if loop_intercepted:
        print("  ✅ PASS: Infinite Loop intercepted and Snap-Back triggered.")
    else:
        print("  ❌ FAIL: Loop detection failed.")

    # --- TEST 2: Financial No-Bypass Zone (Escalation) ---
    print("\n[TEST 2/4] Financial No-Bypass Zone (Escalation)")
    fin_failure = [{
        "id": "STRESS_FIN_001",
        "status": "error",
        "workflowData": {"name": "CFO_Agent", "id": "trading_v3"},
        "data": {"resultData": {"error": {"message": "Inconsistent delta calculation in options strategy"}, "lastNodeExecuted": "Trade Logic"}}
    }]
    
    report = nc.scan_and_heal(injected_failures=fin_failure)
    actions = report.get("audit_trail", [])
    escalated = any(a["action_taken"] == "sentinel_escalate" for a in actions)
    
    if escalated:
        print("  ✅ PASS: Financial sensitivity detected. Forced Escalation Protocol.")
    else:
        print("  ❌ FAIL: Financial data allowed snap-back (security breach).")

    # --- TEST 3: Security No-Bypass Zone (Escalation) ---
    print("\n[TEST 3/4] Security No-Bypass Zone (Escalation)")
    sec_failure = [{
        "id": "STRESS_SEC_001",
        "status": "error",
        "workflowData": {"name": "NetworkAgent", "id": "net_v1"},
        "data": {"resultData": {"error": {"message": "Anomalous Zero-Trust token rotation failure"}, "lastNodeExecuted": "Auth Provider"}}
    }]
    
    report = nc.scan_and_heal(injected_failures=sec_failure)
    actions = report.get("audit_trail", [])
    escalated = any(a["action_taken"] == "sentinel_escalate" for a in actions)
    
    if escalated:
        print("  ✅ PASS: Security domain protected. Process isolated and escalated.")
    else:
        print("  ❌ FAIL: Security domain allowed snap-back.")

    # --- TEST 4: Hallucination Detection (Safe Bypass) ---
    print("\n[TEST 4/4] Hallucination Detection (Safe Bypass)")
    hal_failure = [{
        "id": "STRESS_HAL_001",
        "status": "error",
        "workflowData": {"name": "ContentAgent", "id": "gen_v1"},
        "data": {"resultData": {"error": {"message": "Hallucination marker detected: agent referenced non-existent market index"}, "lastNodeExecuted": "Draft Gen"}}
    }]
    
    report = nc.scan_and_heal(injected_failures=hal_failure)
    actions = report.get("audit_trail", [])
    hal_healed = any(a["diagnosis_id"] == "HALLUCINATION_DETECTED" and a["action_taken"] == "sentinel_snap_back" for a in actions)
    
    if hal_healed:
        print("  ✅ PASS: Hallucination detected and Snap-Back triggered.")
    else:
        print("  ❌ FAIL: Hallucination detection failed.")

    # --- TEST 5: V3 Hardening Hook (Promotion to 0.9) ---
    print("\n[TEST 5/5] V3 Hardening Hook (Promotion to 0.9)")
    hard_failure = [{
        "id": "STRESS_HARD_001",
        "status": "error",
        "workflowData": {"name": "OptimizationAgent", "id": "opt_v1"},
        "data": {"resultData": {"error": {"message": "GEN_001: Recurring hallucination in optimization kernel"}, "lastNodeExecuted": "Kernel compute"}}
    }]
    
    # We need to simulate multiple successful cycles to reach 0.9 confidence
    # (Starting at 0.4, +0.15 per success -> 0.4, 0.55, 0.70, 0.85, 1.00)
    print("  🚀 Simulating rapid promotion cycle...")
    for i in range(5):
        # scan_and_heal will call act() and learn_from_action() internally.
        # Since sentinel_snap_back always returns True, it will PROMOTE confidence automatically.
        nc.scan_and_heal(injected_failures=hard_failure)
            
    # Check if hardening task was queued
    bridge_path = os.path.join(FACTORY_DIR, "hardening_queue.json")
    if os.path.exists(bridge_path):
        with open(bridge_path, "r", encoding="utf-8") as f:
            queue = json.load(f)
            hardened = any(q["target_app"] == "OptimizationAgent" for q in queue)
            if hardened:
                print("  ✅ PASS: V3 Hardening Hook triggered. Task dispatched to Phantom QA.")
            else:
                print("  ❌ FAIL: Hardening task not found in queue.")
    else:
        print("  ❌ FAIL: hardening_queue.json missing.")

    print(f"\n{'═'*60}")
    print("  STRESS TEST COMPLETE")
    print(f"{'═'*60}\n")

if __name__ == "__main__":
    # Ensure telemetry file is restored/cleaned up after test
    original_logs = []
    telemetry_path = os.path.join(FACTORY_DIR, "auto_heal_log.json")
    if os.path.exists(telemetry_path):
        with open(telemetry_path, "r", encoding="utf-8") as f:
            original_logs = json.load(f)
            
    try:
        run_stress_test()
    finally:
        with open(telemetry_path, "w", encoding="utf-8") as f:
            json.dump(original_logs, f, indent=2)
