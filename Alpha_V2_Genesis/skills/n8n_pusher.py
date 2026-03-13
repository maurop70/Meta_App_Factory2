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
import json
import logging

# Configuration
# Webhook URL for the "Alpha Phase 3 Logic (Push Mode)" workflow
# In production, this matches the path 'alpha-decision' configured in the Webhook Node.
N8N_WEBHOOK_URL = "https://humanresource.app.n8n.cloud/webhook/alpha-decision"

logger = logging.getLogger("n8n_pusher")

def push_decision(decision_data):
    """
    Pushes the decision payload to the n8n webhook.
    """
    try:
        # BUDGET GUARD: Limit N8N executions to Mon-Tue, 9am-4pm
        import datetime
        now = datetime.datetime.now()
        is_window = (now.weekday() < 2) and (9 <= now.hour < 16)
        
        if not is_window:
            logger.info("Outside N8N Window (Mon-Tue, 9am-4pm). Skipping decision push.")
            return True # Return true to avoid error loops
            
        # Extract relevant fields for the Mauro Gate check
        payload = {
            "verdict": decision_data.get('loki_proposal', {}).get('strategy', 'UNKNOWN'),
            "rationale": decision_data.get('loki_proposal', {}).get('rationale', ''),
            "hold_value": decision_data.get('expert_opinions', {}).get('defense', {}).get('financials', {}).get('debit_close', 0.0),
            "roll_value": decision_data.get('expert_opinions', {}).get('defense', {}).get('financials', {}).get('credit_open', 0.0),
            "mmm": decision_data.get('expert_opinions', {}).get('new_trade', {}).get('mmm', 0.0),
            "timestamp": decision_data.get('market_snapshot', {}).get('timestamp', 0)
        }
        
        logger.info(f"Pushing decision to n8n: {N8N_WEBHOOK_URL}")
        _v3_status = healed_post(N8N_WEBHOOK_URL, payload)

        response = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
        
        if response.status_code == 200:
            logger.info("Successfully pushed to n8n.")
            return True
        else:
            logger.error(f"Failed to push to n8n. Status: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error pushing to n8n: {e}")
        return False

if __name__ == "__main__":
    # Test Payload
    test_data = {
        "loki_proposal": {"strategy": "TEST_HOLD", "rationale": "Testing Push"},
        "expert_opinions": {
            "defense": {
                "financials": {"debit_close": 1.54, "credit_open": 1.22}
            }
        }
    }
    push_decision(test_data)

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
