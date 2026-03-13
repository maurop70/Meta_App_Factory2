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


class MacroAgent:
    def __init__(self):
        pass

    def analyze_calendar(self, n8n_events=None):
        """
        Returns macro risk analysis. 
        If n8n_events is provided (even if empty list), uses that real-time data.
        Otherwise, defaults to a safe/empty state.
        """
        if n8n_events is not None:
            # We have real data (or a confirmed empty list)
            risk = "LOW"
            if isinstance(n8n_events, list):
                for e in n8n_events:
                    if e.get('impact') == 'HIGH' and e.get('days_until', 99) <= 3:
                        risk = "HIGH"
                    elif e.get('impact') == 'MED' and e.get('days_until', 99) <= 1 and risk != "HIGH":
                         risk = "MEDIUM"
                
                high_impact = [e.get('event') for e in n8n_events if e.get('impact') == 'HIGH']
                description = f"Analysis based on {len(n8n_events)} upcoming events."
                if high_impact:
                    description += f" HIGH IMPACT: {', '.join(high_impact)}"
            else:
                description = "Macro data format invalid."
            
            return {
                "risk_level": risk,
                "events": n8n_events,
                "details": description
            }

        # Fallback: No Data (Don't show wrong data)
        return {
            "risk_level": "LOW",
            "events": [],
            "details": "No specific high-impact events detected in current scan."
        }
# V3 AUTO-HEAL ACTIVE
