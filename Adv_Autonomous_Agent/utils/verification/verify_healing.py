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

# Set up paths to import bridge
BRIDGE_PATH = r"c:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Meta_App_Factory\Adv_Autonomous_Agent"
sys.path.append(BRIDGE_PATH)

import bridge

print(f"Current Webhook URL: {bridge.WEBHOOK_URL}")
print("\n--- TEST: Running Sentry Level 2 Healing Protocol ---")

# Run the protocol
# It should find the workflow and potentially update the URL (or keep it if it matches the ID logic)
# Note: Our current URL is the simplified one. The logic updates to the ID-based one.
# So we expect it to say "RE-ALIGNING SATELLITES" and update the URL.

try:
    healed = bridge._healing_protocol()
    print(f"\nHealing Result: {healed}")
    print(f"New Webhook URL: {bridge.WEBHOOK_URL}")
except Exception as e:
    print(f"Test Failed: {e}")
# V3 AUTO-HEAL ACTIVE
