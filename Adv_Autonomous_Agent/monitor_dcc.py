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


import sys
import os
import time
import json
from datetime import datetime

# Path Configuration
# Assumes script is run from project root or utils
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if "utils" in PROJECT_DIR.lower():
    PROJECT_DIR = os.path.dirname(PROJECT_DIR)
    
CACHE_FILE = os.path.join(PROJECT_DIR, ".Gemini_state", ".sentry_cache.json")

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def load_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        else:
            return []
    except Exception as e:
        return ["ERROR: " + str(e)]

if __name__ == "__main__":
    clear_screen()
    print(f"--- DCC CONTEXT MONITOR [Interval: 10s] ---")
    print(f"Watching: {CACHE_FILE}\n")
    print("Press Ctrl+C to stop.\n")
    
    try:
        while True:
            timestamp = datetime.now().strftime("%H:%M:%S")
            data = load_cache()
            
            # Repaint
            clear_screen()
            print(f"==========================================")
            print(f"   DCC COMMAND CENTER MONITOR  |  {timestamp}")
            print(f"==========================================")
            
            if isinstance(data, list):
                if not data:
                    print("  (Status: IDLE / No Context)")
                else:
                    print(f"  Status: ACTIVE ({len(data)} Items in Context Memory)")
                    print("-" * 42)
                    for i, item in enumerate(data):
                        # Clean up formatting for display
                        preview = item.replace('\n', ' ')
                        preview = (preview[:80] + '...') if len(preview) > 80 else preview
                        print(f"  {i+1}. {preview}")
            else:
                 print(f"  Status: UNKNOWN FORMAT ({type(data)})")

            print("-" * 42)
            print("\nUpdating in 10s...")
            
            time.sleep(10)

    except KeyboardInterrupt:
        print("\nMonitor Stopped.")
# V3 AUTO-HEAL ACTIVE
