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


import requests
import config

def test_connection():
    url = f"{config.N8N_BASE_URL}/api/v1/active-workflows" # Using a safe endpoint to check auth
    # Note: /active-workflows might not exist, checking /workflows instead with limit
    url = f"{config.N8N_BASE_URL}/api/v1/workflows?limit=1"
    
    print(f"Testing connection to: {url}")
    
    try:
        response = requests.get(url, headers=config.get_headers())
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("SUCCESS: Connection established and authenticated.")
            print(f"Response snippet: {response.text[:200]}")
        elif response.status_code == 401:
            print("FAILURE: Unauthorized. API Key may be invalid.")
        else:
            print(f"FAILURE: Unexpected status code. {response.text}")
            
    except Exception as e:
        print(f"ERROR: Could not connect. {e}")

if __name__ == "__main__":
    test_connection()
# V3 AUTO-HEAL ACTIVE
