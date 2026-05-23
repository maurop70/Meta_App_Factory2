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


# specific factory configuration for this sub-app
FACTORY_CONFIG = {
    "module_name": "Claude_N8N_Automation_Bridge",
    "version": "1.0.0",
    "type": "integration_module",
    "base_path": "Meta_App_Factory/Claude_N8N_Automation_Bridge",
    "components": [
        "supervisor.py",
        "n8n_workflow_schema.json"
    ],
    "dependencies": {
        "utils": ["claude_relay.py", "debugger.py"],
        "services": ["CLAUDE_CODE_SERVICE", "DEBUG_SERVICE_SENTRY"]
    },
    "env_vars": [
        "SENTRY_DSN",
        "SENTRY_AUTH_TOKEN"
    ]
}

def get_config():
    return FACTORY_CONFIG
# V3 AUTO-HEAL ACTIVE
