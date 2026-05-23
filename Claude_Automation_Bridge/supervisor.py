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
import os
import sentry_sdk
from dotenv import load_dotenv

# Add parent directory to sys.path to import utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.claude_relay import ClaudeRelay
from utils.debugger import SentryDebugger

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Supervisor')

class Supervisor:
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()
        
        self.load_config()
        self.setup_sentry()
        
        # Resolve Claude Webhook URL
        claude_service = self.config['services']['CLAUDE_CODE_SERVICE']
        webhook_url_key = claude_service.get('url_env_key')
        self.webhook_url = os.getenv(webhook_url_key) if webhook_url_key else claude_service.get('url')
        
        if not self.webhook_url or "YOUR_" in self.webhook_url:
            logger.error(f"Claude Webhook URL not found. Check {webhook_url_key} in .env")
            # We proceed but expect failure if called
            
        self.relay = ClaudeRelay(self.webhook_url, self.sentry_dsn)
        self.debugger = SentryDebugger(auth_token=os.getenv("SENTRY_AUTH_TOKEN"))

    def load_config(self):
        try:
            # Load registry from parent directory
            registry_path = os.path.join(os.path.dirname(__file__), '..', 'registry.json')
            with open(registry_path, 'r') as f:
                self.config = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load registry.json: {e}")
            sys.exit(1)

    def setup_sentry(self):
        service_config = self.config.get('services', {}).get('DEBUG_SERVICE_SENTRY', {})
        dsn_key = service_config.get('dsn_env_key')
        self.sentry_dsn = os.getenv(dsn_key) if dsn_key else service_config.get('dsn')
        
        if self.sentry_dsn and 'YOUR_SENTRY_DSN' not in self.sentry_dsn:
            sentry_sdk.init(dsn=self.sentry_dsn, traces_sample_rate=1.0)
        else:
            logger.warning("Sentry DSN not configured or invalid.")

    def parse_permission_request(self, output):
        """
        Parses the output for permission requests.
        Returns the command to verify if found, else None.
        """
        if output and ("Permission Request" in output or "Do you want to run" in output):
            lines = output.split('\n')
            for line in lines:
                if "CMD:" in line: 
                    return line.split("CMD:")[1].strip()
        return None

    def execute_task(self, task):
        logger.info(f"Supervisor starting task: {task}")
        
        # 1. First Attempt
        result = self.relay.send_task(task)
        
        if result.get('success'):
            output = result['data'].get('body', {}).get('stdout', '')
            
            # 2. Check for Permissions
            command_request = self.parse_permission_request(output)
            if command_request:
                # In an autonomous loop, we might need a policy. 
                # Here we default to interactive or 'deny' if no user present.
                print(f"Claude Permission Request: {command_request}")
                # For now, just log it. Real implementation needs an interactive loop or policy.
                return result
            return result
        
        else:
            # 3. Feedback Loop
            logger.error("Task failed. Initiating feedback loop.")
            
            issue_id = result.get('last_event_id')
            if issue_id:
                issue_summary = self.debugger.get_issue_summary(issue_id)
                logger.info(f"Retrieved Sentry Issue Summary: {issue_summary}")
                
                retry_task = f"PREVIOUS FAILED with error: {issue_summary}. RETRYING TASK: {task}"
                logger.info("Retrying task with debug context...")
                return self.relay.send_task(retry_task)
            
            return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python supervisor.py <TASK_STRING>")
        sys.exit(1)
        
    supervisor = Supervisor()
    supervisor.execute_task(sys.argv[1])
# V3 AUTO-HEAL ACTIVE
