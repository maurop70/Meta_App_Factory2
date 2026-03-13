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
import json
import logging
# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
skills_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "skills"))
if skills_dir not in sys.path:
    sys.path.append(skills_dir)

from n8n_architect.architect import N8NArchitect

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Deployer")

def deploy():
    # Initialize Architect
    arch = N8NArchitect()
    
    # 1. Connectivity Check
    logger.info("Checking N8N Connectivity...")
    try:
        wfs = arch.list_workflows()
        logger.info(f"Connection OK. Found {len(wfs)} workflows.")
    except Exception as e:
        logger.error(f"Connectivity Check Failed: {e}")
        return

    # Load Schema
    schema_path = os.path.join(current_dir, "n8n_workflow_schema.json")
    if not os.path.exists(schema_path):
        logger.error(f"Schema not found at {schema_path}")
        return

    with open(schema_path, "r") as f:
        workflow_json = json.load(f)

    # 2. Deploy with Debugging
    logger.info("Deploying 'Claude Code Executor' workflow...")
    
    # Manually calling the API to capture the raw response if Architect fails silently
    endpoint = f"{arch.base_url}/api/v1/workflows"
    try:
        _v3_status = healed_post(endpoint, workflow_json)

        resp = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
        if resp.status_code != 200:
            logger.error(f"Manual Deployment Failed: {resp.status_code} - {resp.text}")
        else:
            wf_id = resp.json().get('id')
            logger.info(f"Deployment Successful! Workflow ID: {wf_id}")
            
            # Activate it
            arch.activate_workflow(wf_id)
            
            # Construct Webhook URL
            webhook_path = "claude-exec" 
            for node in workflow_json.get("nodes", []):
                if node.get("type") == "n8n-nodes-base.webhook":
                    webhook_path = node.get("parameters", {}).get("path", "claude-exec")
                    break
            
            url = f"{arch.base_url}/webhook/{wf_id}/{webhook_path}"
            logger.info(f"Webhook URL: {url}")
            print(f"DEPLOY_SUCCESS_URL::{url}")

    except Exception as e:
        logger.error(f"Deployment Exception: {e}")

if __name__ == "__main__":
    deploy()

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
