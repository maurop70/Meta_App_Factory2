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
import threading

sys.stdout.reconfigure(encoding='utf-8')

# Setup Paths to mimic Adv_Autonomous_Agent environment
BASE_DIR = r"c:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Meta_App_Factory\Adv_Autonomous_Agent"
SKILLS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "skills"))
sys.path.append(SKILLS_DIR)

try:
    from sentry_telemetry.observer import SentryObserver
    print("✅ SentryObserver Module Loaded Successfully")
except ImportError as e:
    print(f"❌ Failed to load SentryObserver: {e}")
    sys.exit(1)

def run_dcc_test():
    print("--- STARTING DCC (SENTRY) VERIFICATION FOR ADV_AGENT ---")
    
    # Initialize Observer
    observer = SentryObserver("Adv_Autonomous_Agent", heartbeat_interval=1.0, failure_threshold=3.0)
    observer.start()
    print("✅ Sentry Observer Thread Started")
    
    # Simulate Heartbeats (Healthy)
    for i in range(3):
        time.sleep(1)
        observer.tick({"status": "healthy", "tick": i})
        status = observer.get_status()
        print(f"[{i+1}/3] Heartbeat Sent. Sentry Status: {status}")
        
    # Simulate "Busy" State (No Heartbeat for 2 seconds - Should remain ACTIVE/WARNING)
    print("--- SIMULATING HEAVY LOAD (2s Pause) ---")
    time.sleep(2)
    observer.tick({"status": "recovering"})
    print(f"[Results] Status after pause: {observer.get_status()}")

    # Simulate CRITICAL Failure (No Heartbeat for 4 seconds > 3s threshold)
    print("--- SIMULATING CRASH (4s Pause) ---")
    time.sleep(4)
    status = observer.get_status()
    print(f"[Results] Status after crash simulation: {status}")
    
    if status == "CRITICAL":
        print("✅ SILENT FAILURE DETECTED CORRECTLY")
    else:
        print("❌ FAILED TO DETECT SILENT FAILURE")

    # Access the shared cache to prove persistence
    cache_path = os.path.join(BASE_DIR, ".sentry_cache.json")
    if os.path.exists(cache_path):
        print(f"✅ Telemetry Cache Found at: {cache_path}")
    else:
        print("⚠️ No Telemetry Cache Found (might be first run)")

    observer.running = False
    print("--- DCC VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    run_dcc_test()
# V3 AUTO-HEAL ACTIVE
