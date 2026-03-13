# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

from auto_heal import healed_post, auto_heal, diagnose

def _v3_preflight():
    """V3: Ping Resonance_Watchdog_V3 before execution."""
    if not _V3_AVAILABLE:
        return True
    try:
        import json as _j
        _cfg_path = _os.path.join(_FACTORY_DIR, "resilience_config.json")
        if not _os.path.exists(_cfg_path):
            return True
        with open(_cfg_path) as _f:
            _cfg = _j.load(_f)
        _url = _cfg.get("cloud_health", {}).get("watchdog_url", "")
        if not _url:
            return True
        import requests as _rq
        _r = _rq.get(_url, timeout=5)
        return _r.status_code == 200
    except Exception:
        return False


import os
import sys
import json
import time

# Ensure we can import bridge.py
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

import bridge

def run_test():
    print("--- [TEST] Starting Agent Memory Verification ---")
    
    # Use a unique project name for the test to avoid polluting actual project memory
    test_project = "Memory_Test_Bench"
    
    # 1. Starter Prompt
    print(f"\n[STEP 1] Sending Starter Prompt...")
    starter_prompt = "--- MEMORY TEST START (https://humanresource.app.n8n.cloud/webhook/elite-council) ---"
    payload = {
        "prompt": starter_prompt,
        "project_name": test_project,
        "clean_slate": True # Ensure we start fresh
    }
    resp1 = bridge.call_app(payload)
    print(f"Response 1: {resp1[:100]}...")

    # 2. Inject Secret
    print(f"\n[STEP 2] Injecting Secret...")
    secret_prompt = 'The secret project code is "ALBATROSS-2026". Please remember this code for the next turn.'
    payload = {
        "prompt": secret_prompt,
        "project_name": test_project
    }
    resp2 = bridge.call_app(payload)
    print(f"Response 2: {resp2[:100]}...")

    # 3. Retrieve Secret
    print(f"\n[STEP 3] Retrieving Secret...")
    retrieval_prompt = "What is the secret project code I just gave you?"
    payload = {
        "prompt": retrieval_prompt,
        "project_name": test_project
    }
    resp3 = bridge.call_app(payload)
    print(f"\n--- [FINAL RESULT] ---")
    print(f"Agent Response: {resp3}")
    
    if "ALBATROSS-2026" in resp3:
        print("\n[SUCCESS] Memory Verification Passed!")
    else:
        print("\n[FAIL] Memory Verification Failed. Agent did not recall the secret.")

if __name__ == "__main__":
    run_test()
# V3 AUTO-HEAL ACTIVE
