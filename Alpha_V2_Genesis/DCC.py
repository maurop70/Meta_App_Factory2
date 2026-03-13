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
import json
import requests
import sys

def check_data_consistency():
    print("\n[DCC] --- ALPHA ARCHITECT: DATA CONSISTENCY CHECK --- [DCC]")
    
    # Portability Fix: Use directory of the script as the base
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "Alpha_Data")
    
    # 1. Check Portfolio Integrity
    p_path = os.path.join(data_dir, "portfolio.json")
    print(f"\n[Files] Checking Portfolio: {p_path}")
    if os.path.exists(p_path):
        try:
            with open(p_path, 'r') as f:
                p_data = json.load(f)
            
            # Integrity Logic: If it's a list and has 'event_name', it's CORRUPTED (misplaced macro data)
            if isinstance(p_data, list) and len(p_data) > 0:
                if isinstance(p_data[0], dict) and ('event_name' in p_data[0] or 'event' in p_data[0]):
                    print("[!!] STATUS: CORRUPTED (Macro Data found in Portfolio)")
                else:
                    print("[OK] STATUS: OK (List Format)")
            elif isinstance(p_data, dict):
                if 'short_put_strike' in p_data:
                    print("[OK] STATUS: OK (Position Object)")
                else:
                    print("[??] STATUS: UNKNOWN SCHEMA")
            else:
                 print("[??] STATUS: EMPTY OR INVALID")
        except Exception as e:
            print(f"[ERR] STATUS: ERROR ({e})")
    else:
        print("[ERR] STATUS: MISSING")

    # 2. Check Upcoming Events
    e_path = os.path.join(data_dir, "upcoming_events.json")
    print(f"\n[Files] Checking Events: {e_path}")
    if os.path.exists(e_path):
        try:
            with open(e_path, 'r') as f:
                e_data = json.load(f)
            count = len(e_data) if isinstance(e_data, list) else 1
            print(f"[OK] STATUS: OK ({count} Events Loaded)")
        except:
            print("[ERR] STATUS: BROKEN JSON")
    else:
        print("[ERR] STATUS: MISSING")

    # 3. Check Analyst Memo
    m_path = os.path.join(script_dir, "market_memo.md")
    print(f"\n[Files] Checking Memo: {m_path}")
    if os.path.exists(m_path):
        size = os.path.getsize(m_path)
        if size > 100:
             print(f"[OK] STATUS: OK ({size} bytes)")
        else:
             print("[!!] STATUS: TOO SHORT")
    else:
        print("[ERR] STATUS: MISSING")

    # 4. Check API Connection
    print("\n[Net] Checking API (Port 5005)")
    try:
        # Avoid full analysis, just check root
        resp = requests.get("http://localhost:5005/", timeout=5)
        if resp.status_code == 200:
            print(f"[OK] STATUS: SERVER ONLINE ({resp.json().get('system')})")
        else:
            print(f"[ERR] STATUS: SERVER ERROR ({resp.status_code})")
    except:
        print("[ERR] STATUS: SERVER UNREACHABLE")

    print("\n--- DCC COMPLETE ---\n")

if __name__ == "__main__":
    check_data_consistency()
# V3 AUTO-HEAL ACTIVE
