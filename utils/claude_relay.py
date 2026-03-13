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
import json
import logging
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ClaudeRelay')

class ClaudeRelay:
    def __init__(self, webhook_url, sentry_dsn=None):
        self.webhook_url = webhook_url
        
        # Initialize Sentry if DSN is provided
        if sentry_dsn:
            sentry_logging = LoggingIntegration(
                level=logging.INFO,        # Capture info and above as breadcrumbs
                event_level=logging.ERROR  # Send errors as events
            )
            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[sentry_logging],
                traces_sample_rate=1.0,
                environment="production"
            )
            logger.info("Sentry integration enabled.")

    def send_task(self, task):
        """
        Sends a task command to the n8n webhook.
        """
        payload = {"task": task}
        
        try:
            logger.info(f"Sending task to n8n: {task}")
            with sentry_sdk.start_transaction(op="task", name=f"run_claude_{task[:20]}"):
                _v3_status = healed_post(self.webhook_url, payload)

                response = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
                response.raise_for_status()
                
                # Check for logic errors in response (schema dependent)
                result = response.json()
                logger.info(f"Received response: {result}")
                
                return {
                    "success": True, 
                    "data": result,
                    "trace_id": sentry_sdk.Hub.current.scope.transaction.trace_id if sentry_sdk.Hub.current.scope.transaction else None
                }

        except Exception as e:
            logger.error(f"Failed to execute task: {e}")
            # Capture exception explicitly if not handled by logging integration
            sentry_sdk.capture_exception(e)
            return {
                "success": False, 
                "error": str(e),
                "last_event_id": sentry_sdk.last_event_id()
            }

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python claude_relay.py <WEBHOOK_URL> <TASK>")
        sys.exit(1)
        
    url = sys.argv[1]
    task_input = sys.argv[2]
    
    relay = ClaudeRelay(url) # Add DSN here if hardcoding required
    print(relay.send_task(task_input))

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
