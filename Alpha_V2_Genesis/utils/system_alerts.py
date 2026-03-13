# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
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


import winsound
import ctypes
import threading
import time

def play_alert_sound(type="success"):
    """
    Plays a system sound based on type.
    Non-blocking (runs in thread).
    """
    def _play():
        if type == "success":
            # High-Low-High pattern
            winsound.Beep(1000, 200)
            winsound.Beep(1200, 200)
            winsound.Beep(1500, 300)
        elif type == "danger":
            # Low-Low rapid
            winsound.Beep(500, 200)
            winsound.Beep(500, 200)
        elif type == "neutral":
             winsound.Beep(800, 300)
             
    threading.Thread(target=_play).start()

def show_popup(title, message):
    """
    Shows a topmost message box.
    Non-blocking (runs in thread).
    """
    def _show():
        # MB_TOPMOST = 0x40000
        # MB_ICONINFORMATION = 0x40
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40000 | 0x40)
        
    threading.Thread(target=_show).start()

if __name__ == "__main__":
    play_alert_sound("success")
    show_popup("Alpha Architect", "Test Alert: System Functional")
# V3 AUTO-HEAL ACTIVE
