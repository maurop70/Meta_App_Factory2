# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", ".."))
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


import sys
import os
import time
import json

# Set up paths to import sentry_telemetry
SKILLS_PATH = r"c:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\skills"
sys.path.append(SKILLS_PATH)

from sentry_telemetry.observer import SentryObserver

print("--- TELEMETRY TEST: Start ---")

# 1. Start Observer (Short timeout for test)
observer = SentryObserver("TEST_APP", failure_threshold=2.0)
observer.start()

# 2. Simulate Healthy App (3 seconds)
for i in range(3):
    print(f"Main Thread: Work {i}")
    observer.tick({"iteration": i, "status": "HEALTHY"})
    time.sleep(0.5)
    
print("\n--- TELEMETRY TEST: Simulating Freezing (Silent Failure) ---")
print("Main Thread: FROZEN (Sleeping for 4s - Should trigger Alert after 2s)")
time.sleep(4)

# 3. Check Result
print("\n--- TELEMETRY TEST: Checking Results ---")
print(f"Observer Status: {observer.get_status()}")

cache_file = os.path.join(os.getcwd(), ".sentry_cache.json")
if os.path.exists(cache_file):
    with open(cache_file, "r") as f:
        data = json.load(f)
        print("Snapshot Found:")
        print(json.dumps(data, indent=2))
else:
    print("TEST FAILED: No Snapshot found.")

observer.stop()
time.sleep(1) # Cleanup
print("--- TELEMETRY TEST: End ---")
# V3 AUTO-HEAL ACTIVE
