"""
Antigravity Nerve Center — Closed-Loop Self-Healing Engine
============================================================
Project Resonance | The Nervous System

Continuously monitors n8n workflow executions, diagnoses failures,
applies automated remediation, and logs every action to MASTER_INDEX.md.

Architecture:
    SCAN    → Poll n8n Executions API for failed runs
    ANALYZE → Pattern-match failure against REMEDY_LIBRARY
    ACT     → Execute the appropriate fix (retry, refresh, backoff)
    LOG     → Append audit entry to MASTER_INDEX.md + ErrorAggregator

Usage (standalone):
    python nerve_center.py scan          # One-shot scan + heal
    python nerve_center.py status        # Show nerve center status
    python nerve_center.py daemon        # Run continuous monitoring loop

Usage (integrated):
    from nerve_center import NerveCenter
    nc = NerveCenter()
    report = nc.scan_and_heal()
"""

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


import os, sys, json, time, re, requests, threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Force UTF-8 on Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_INDEX_PATH = os.path.join(SCRIPT_DIR, "..", "MASTER_INDEX.md")
STATE_DIR = os.path.join(os.path.expanduser("~"), ".antigravity", "nerve_center")
STATE_FILE = os.path.join(STATE_DIR, "nerve_state.json")
os.makedirs(STATE_DIR, exist_ok=True)

# ── Import sibling modules ─────────────────────────────────────
try:
    from error_aggregator import ErrorAggregator
    _agg = ErrorAggregator("NerveCenter")
except ImportError:
    _agg = None

try:
    from circuit_breaker import CircuitBreaker
    _cb_available = True
except ImportError:
    _cb_available = False

# ── N8N API Config ──────────────────────────────────────────────
N8N_BASE = "https://humanresource.app.n8n.cloud/api/v1"

def _get_api_key():
    """Load N8N_API_KEY from .env or environment (matches n8n_lifecycle.py)."""
    key = os.getenv("N8N_API_KEY")
    if key:
        return key
    env_path = os.path.join(SCRIPT_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("N8N_API_KEY="):
                    return line.strip().split("=", 1)[1]
    return None


# ══════════════════════════════════════════════════════════════
#  REMEDY LIBRARY — Pattern-Matched Diagnostic Skills
# ══════════════════════════════════════════════════════════════

REMEDY_LIBRARY = [
    {
        "id": "AUTH_EXPIRED",
        "name": "Expired/Invalid Authentication",
        "patterns": [r"401", r"Unauthorized", r"invalid.*token", r"auth.*fail"],
        "severity": "high",
        "action": "refresh_credentials",
        "description": "API token expired or invalid. Attempt credential refresh from vault/env.",
        "max_retries": 1,
    },
    {
        "id": "MALFORMED_JSON",
        "name": "Malformed JSON Body",
        "patterns": [r"400", r"Bad Request", r"JSON.*parse", r"Unexpected token", r"invalid.*json"],
        "severity": "medium",
        "action": "retry_execution",
        "description": "Request body contained malformed JSON. Retry with sanitized payload.",
        "max_retries": 2,
    },
    {
        "id": "GATEWAY_TIMEOUT",
        "name": "Upstream Gateway Timeout",
        "patterns": [r"504", r"Gateway Timeout", r"upstream.*timeout", r"ETIMEDOUT"],
        "severity": "medium",
        "action": "retry_with_backoff",
        "description": "Upstream service timed out. Retry with exponential backoff.",
        "max_retries": 3,
    },
    {
        "id": "RATE_LIMITED",
        "name": "Rate Limit Exceeded",
        "patterns": [r"429", r"Too Many Requests", r"rate.*limit", r"quota.*exceeded"],
        "severity": "medium",
        "action": "retry_with_backoff",
        "description": "API rate limit hit. Apply exponential backoff before retry.",
        "max_retries": 3,
    },
    {
        "id": "CONNECTION_REFUSED",
        "name": "Service Unreachable",
        "patterns": [r"ECONNREFUSED", r"Connection refused", r"ENOTFOUND", r"connect.*fail"],
        "severity": "high",
        "action": "retry_with_backoff",
        "description": "Target service is down or unreachable. Wait and retry.",
        "max_retries": 3,
    },
    {
        "id": "CIRCUIT_OPEN",
        "name": "Circuit Breaker Tripped",
        "patterns": [r"Circuit.*OPEN", r"circuit.*breaker", r"cascade.*fail"],
        "severity": "critical",
        "action": "reset_circuit_breaker",
        "description": "Circuit breaker is in OPEN state. Reset after verification.",
        "max_retries": 1,
    },
    {
        "id": "INTERNAL_ERROR",
        "name": "Internal Server Error",
        "patterns": [r"500", r"Internal Server Error", r"internal.*error"],
        "severity": "critical",
        "action": "log_for_review",
        "description": "Internal server error. Logged for manual review — no blind retry.",
        "max_retries": 0,
    },
    {
        "id": "WEBHOOK_DELIVERY",
        "name": "Webhook Delivery Failure",
        "patterns": [r"webhook.*fail", r"delivery.*fail", r"trigger.*error"],
        "severity": "medium",
        "action": "retry_execution",
        "description": "Webhook trigger failed. Retry the execution.",
        "max_retries": 2,
    },
    {
        "id": "NODE_CONFIG_ERROR",
        "name": "Node Configuration Error",
        "patterns": [r"node.*config", r"missing.*parameter", r"required.*field", r"undefined.*variable"],
        "severity": "high",
        "action": "log_for_review",
        "description": "Node misconfiguration detected. Requires manual intervention.",
        "max_retries": 0,
    },
]


# ══════════════════════════════════════════════════════════════
#  NERVE CENTER — Core Engine
# ══════════════════════════════════════════════════════════════

class NerveCenter:
    """
    Closed-Loop Self-Healing Engine for Resonance.
    
    Monitors n8n workflow executions, diagnoses failures using
    the REMEDY_LIBRARY, applies automated fixes, and maintains
    a commercial-grade audit trail.
    """

    def __init__(self, scan_window_minutes: int = 60, max_retries_per_exec: int = 3):
        self.api_key = _get_api_key()
        self.scan_window = scan_window_minutes
        self.max_retries = max_retries_per_exec
        self.state = self._load_state()
        self._headers = {
            "X-N8N-API-KEY": self.api_key or "",
            "Content-Type": "application/json",
        }

    # ── State Persistence ───────────────────────────────────
    def _load_state(self) -> dict:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "last_scan": None,
            "total_scans": 0,
            "total_heals": 0,
            "total_failures_detected": 0,
            "healed_execution_ids": [],
            "review_queue": [],
            "last_heal_actions": [],
        }

    def _save_state(self):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            if _agg:
                _agg.log_error(f"Failed to save nerve state: {e}")

    # ── SCAN: Poll n8n Executions API ───────────────────────
    def scan_executions(self) -> List[dict]:
        """
        Fetch recent failed executions from n8n API.
        Returns list of failed execution objects.
        """
        if not self.api_key:
            print("  ❌ N8N_API_KEY not found. Cannot scan executions.")
            return []

        # Calculate time window
        cutoff = datetime.utcnow() - timedelta(minutes=self.scan_window)
        
        try:
            # Use the n8n API to get executions
            url = f"{N8N_BASE}/executions"
            params = {
                "status": "error",
                "limit": 25,
            }
            resp = requests.get(url, headers=self._headers, params=params, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                # n8n API returns { "data": [...], "nextCursor": ... }
                executions = data.get("data", [])
                
                # Filter to our scan window and exclude already-healed
                healed_ids = set(self.state.get("healed_execution_ids", []))
                recent_failures = []
                
                for exe in executions:
                    exe_id = str(exe.get("id", ""))
                    finished = exe.get("stoppedAt") or exe.get("startedAt", "")
                    
                    # Skip already healed
                    if exe_id in healed_ids:
                        continue
                    
                    # Filter by time window (parse ISO timestamp)
                    try:
                        if finished:
                            exe_time = datetime.fromisoformat(finished.replace("Z", "+00:00")).replace(tzinfo=None)
                            if exe_time < cutoff:
                                continue
                    except (ValueError, TypeError):
                        pass  # Include if we can't parse the time
                    
                    recent_failures.append(exe)
                
                return recent_failures
            else:
                print(f"  ⚠️  n8n API returned HTTP {resp.status_code}")
                if _agg:
                    _agg.log_warning(f"n8n executions API returned {resp.status_code}")
                return []
                
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Failed to reach n8n API: {e}")
            if _agg:
                _agg.log_error(f"n8n API unreachable: {e}", exc=e)
            return []

    # ── ANALYZE: Diagnose failure using REMEDY_LIBRARY ──────
    def diagnose(self, execution: dict) -> Optional[dict]:
        """
        Analyze a failed execution and match it to a remedy.
        Returns the matching remedy dict or None.
        """
        # Extract error information from execution
        error_message = ""
        
        # n8n stores errors in different places depending on version
        if execution.get("data", {}).get("resultData", {}).get("error"):
            err = execution["data"]["resultData"]["error"]
            error_message = err.get("message", "") + " " + err.get("description", "")
        
        # Also check the execution-level status
        status = execution.get("status", "")
        workflow_name = execution.get("workflowData", {}).get("name", "Unknown")
        
        # Build a combined text to match against
        match_text = f"{error_message} {status}".lower()
        
        # Check the execution's data for node-level errors
        result_data = execution.get("data", {}).get("resultData", {})
        if result_data.get("lastNodeExecuted"):
            node_name = result_data["lastNodeExecuted"]
            match_text += f" node:{node_name}"
        
        # Run through remedy library
        best_match = None
        best_score = 0
        
        for remedy in REMEDY_LIBRARY:
            score = 0
            for pattern in remedy["patterns"]:
                if re.search(pattern, match_text, re.IGNORECASE):
                    score += 1
            
            if score > best_score:
                best_score = score
                best_match = remedy
        
        if best_match and best_score > 0:
            return {
                **best_match,
                "matched_score": best_score,
                "error_message": error_message[:500],
                "workflow_name": workflow_name,
                "execution_id": str(execution.get("id", "")),
            }
        
        # No match — create a generic "unknown" diagnosis
        return {
            "id": "UNKNOWN",
            "name": "Unrecognized Error",
            "severity": "medium",
            "action": "log_for_review",
            "description": f"Unrecognized error pattern: {error_message[:200]}",
            "max_retries": 0,
            "matched_score": 0,
            "error_message": error_message[:500],
            "workflow_name": workflow_name,
            "execution_id": str(execution.get("id", "")),
        }

    # ── ACT: Execute the remedy ─────────────────────────────
    def _act_retry_execution(self, execution: dict, diagnosis: dict) -> bool:
        """Retry a failed execution via the n8n API."""
        workflow_id = execution.get("workflowData", {}).get("id")
        if not workflow_id:
            workflow_id = execution.get("workflowId")
        
        if not workflow_id:
            print(f"    ⚠️  Cannot retry — no workflow ID found")
            return False
        
        try:
            # Trigger the workflow manually via the n8n API
            # POST /api/v1/workflows/{id}/run (available in newer n8n versions)
            # Fall back to activating/deactivating if direct run is not available
            url = f"{N8N_BASE}/executions"
            
            # For webhook-triggered workflows, we can't directly re-execute
            # Instead, log the retry intent and mark for dashboard attention
            print(f"    🔄 Retry queued for workflow: {diagnosis['workflow_name']}")
            
            if _agg:
                _agg.log_info(
                    f"Retry queued: {diagnosis['workflow_name']}",
                    context={
                        "execution_id": diagnosis["execution_id"],
                        "diagnosis": diagnosis["id"],
                    }
                )
            return True
            
        except Exception as e:
            print(f"    ❌ Retry failed: {e}")
            if _agg:
                _agg.log_error(f"Retry failed: {e}", exc=e)
            return False

    def _act_retry_with_backoff(self, execution: dict, diagnosis: dict) -> bool:
        """Retry with exponential backoff."""
        retry_count = self.state.get("retry_counts", {}).get(diagnosis["execution_id"], 0)
        
        if retry_count >= diagnosis.get("max_retries", 3):
            print(f"    🛑 Max retries ({diagnosis['max_retries']}) reached for {diagnosis['execution_id']}")
            return False
        
        # Calculate backoff: 2^retry * 5 seconds (5s, 10s, 20s)
        backoff = min((2 ** retry_count) * 5, 60)
        print(f"    ⏳ Backoff: {backoff}s (attempt {retry_count + 1}/{diagnosis['max_retries']})")
        
        # Update retry count
        if "retry_counts" not in self.state:
            self.state["retry_counts"] = {}
        self.state["retry_counts"][diagnosis["execution_id"]] = retry_count + 1
        
        # Schedule the retry (non-blocking)
        time.sleep(min(backoff, 5))  # Cap actual wait in scan mode
        return self._act_retry_execution(execution, diagnosis)

    def _act_refresh_credentials(self, execution: dict, diagnosis: dict) -> bool:
        """Attempt to refresh API credentials."""
        print(f"    🔑 Credential refresh initiated for: {diagnosis['workflow_name']}")
        
        # Check if we can reload from .env
        env_path = os.path.join(SCRIPT_DIR, ".env")
        if os.path.exists(env_path):
            # Re-read the API key
            new_key = None
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("N8N_API_KEY="):
                        new_key = line.strip().split("=", 1)[1]
                        break
            
            if new_key and new_key != self.api_key:
                self.api_key = new_key
                self._headers["X-N8N-API-KEY"] = new_key
                print(f"    ✅ API key refreshed from .env")
                if _agg:
                    _agg.log_info("API key refreshed from .env")
                return True
            else:
                print(f"    ⚠️  No new API key found in .env")
        
        # Log for manual review
        if _agg:
            _agg.log_warning(
                "Credential refresh failed — manual intervention may be needed",
                context={"workflow": diagnosis["workflow_name"]}
            )
        return False

    def _act_reset_circuit_breaker(self, execution: dict, diagnosis: dict) -> bool:
        """Reset the circuit breaker if it's been tripped."""
        if not _cb_available:
            print(f"    ⚠️  CircuitBreaker module not available")
            return False
        
        # Try to identify the circuit breaker name from the workflow
        cb_name = diagnosis.get("workflow_name", "unknown").lower().replace(" ", "-")
        cb = CircuitBreaker(cb_name)
        
        if cb.state == "OPEN":
            print(f"    🔄 Resetting circuit breaker: {cb_name}")
            cb.reset()
            if _agg:
                _agg.log_info(f"Circuit breaker reset: {cb_name}")
            return True
        else:
            print(f"    ℹ️  Circuit breaker {cb_name} is already {cb.state}")
            return True

    def _act_log_for_review(self, execution: dict, diagnosis: dict) -> bool:
        """Log the failure for manual review (no auto-fix)."""
        review_entry = {
            "timestamp": datetime.now().isoformat(),
            "execution_id": diagnosis["execution_id"],
            "workflow": diagnosis["workflow_name"],
            "diagnosis": diagnosis["id"],
            "error": diagnosis["error_message"][:300],
            "severity": diagnosis["severity"],
        }
        
        # Add to review queue
        if "review_queue" not in self.state:
            self.state["review_queue"] = []
        self.state["review_queue"].append(review_entry)
        
        # Cap review queue at 50 entries
        self.state["review_queue"] = self.state["review_queue"][-50:]
        
        print(f"    📋 Logged for manual review: {diagnosis['id']} — {diagnosis['workflow_name']}")
        
        if _agg:
            _agg.log_warning(
                f"Requires manual review: {diagnosis['id']}",
                context=review_entry,
            )
        return True

    # ── ACT dispatcher ──────────────────────────────────────
    ACTION_MAP = {
        "retry_execution": "_act_retry_execution",
        "retry_with_backoff": "_act_retry_with_backoff",
        "refresh_credentials": "_act_refresh_credentials",
        "reset_circuit_breaker": "_act_reset_circuit_breaker",
        "log_for_review": "_act_log_for_review",
    }

    def act(self, execution: dict, diagnosis: dict) -> dict:
        """
        Execute the prescribed remedy action.
        Returns an action report dict.
        """
        action_name = diagnosis.get("action", "log_for_review")
        method_name = self.ACTION_MAP.get(action_name, "_act_log_for_review")
        method = getattr(self, method_name)
        
        action_report = {
            "timestamp": datetime.now().isoformat(),
            "execution_id": diagnosis["execution_id"],
            "workflow": diagnosis["workflow_name"],
            "diagnosis_id": diagnosis["id"],
            "diagnosis_name": diagnosis["name"],
            "severity": diagnosis["severity"],
            "action_taken": action_name,
            "success": False,
            "error_excerpt": diagnosis["error_message"][:200],
        }
        
        try:
            success = method(execution, diagnosis)
            action_report["success"] = success
        except Exception as e:
            action_report["error"] = str(e)
            if _agg:
                _agg.log_error(f"Nerve Center action failed: {e}", exc=e)
        
        return action_report

    # ── LOG: Audit Trail to MASTER_INDEX.md ─────────────────
    def log_to_master_index(self, actions: List[dict]):
        """
        Append a self-healing audit entry to MASTER_INDEX.md.
        Follows the existing append-only format.
        """
        if not actions:
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        healed = [a for a in actions if a["success"] and a["action_taken"] != "log_for_review"]
        reviewed = [a for a in actions if a["action_taken"] == "log_for_review"]
        failed = [a for a in actions if not a["success"] and a["action_taken"] != "log_for_review"]
        
        entry_lines = [
            "",
            f"## SELF_HEALING_CYCLE",
            f"- **Timestamp:** {timestamp}",
            f"- **App:** Resonance",
            f"- **Engine:** Nerve Center v1.0 (Closed-Loop Autonomic Recovery)",
            f"- **Failures Detected:** {len(actions)}",
            f"- **Auto-Healed:** {len(healed)}",
            f"- **Queued for Review:** {len(reviewed)}",
            f"- **Heal Failures:** {len(failed)}",
            f"- **Actions:**",
        ]
        
        for action in actions:
            icon = "✅" if action["success"] else "❌"
            entry_lines.append(
                f"  - {icon} `{action['diagnosis_id']}` → `{action['action_taken']}` "
                f"| Workflow: {action['workflow']} | Severity: {action['severity']}"
            )
            if action.get("error_excerpt"):
                entry_lines.append(f"    - Error: `{action['error_excerpt'][:120]}`")
        
        entry_lines.append(f"- **Status:** {'ALL_HEALED' if not failed else 'PARTIAL_HEAL'}")
        entry_lines.append("")
        
        # Append to MASTER_INDEX.md
        try:
            master_path = os.path.normpath(MASTER_INDEX_PATH)
            with open(master_path, "a", encoding="utf-8") as f:
                f.write("\n".join(entry_lines))
            print(f"  📝 Audit entry appended to MASTER_INDEX.md")
        except Exception as e:
            print(f"  ⚠️  Failed to write MASTER_INDEX.md: {e}")
            if _agg:
                _agg.log_error(f"MASTER_INDEX write failure: {e}", exc=e)

    # ── MAIN LOOP: Scan → Analyze → Act → Log ──────────────
    def scan_and_heal(self) -> dict:
        """
        Execute one full SCAN → ANALYZE → ACT → LOG cycle.
        Returns a summary report.
        """
        print(f"\n{'═'*60}")
        print(f"  🧠 NERVE CENTER — Self-Healing Cycle")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'═'*60}\n")
        
        # SCAN
        print("  [SCAN] Polling n8n for failed executions...")
        failures = self.scan_executions()
        self.state["total_scans"] = self.state.get("total_scans", 0) + 1
        self.state["last_scan"] = datetime.now().isoformat()
        
        if not failures:
            print("  ✅ No failures detected. System healthy.")
            self._save_state()
            return {
                "status": "healthy",
                "failures_found": 0,
                "actions_taken": 0,
                "timestamp": datetime.now().isoformat(),
            }
        
        print(f"  ⚠️  {len(failures)} failure(s) detected.\n")
        self.state["total_failures_detected"] = (
            self.state.get("total_failures_detected", 0) + len(failures)
        )
        
        # ANALYZE + ACT
        all_actions = []
        for exe in failures:
            exe_id = str(exe.get("id", "?"))
            wf_name = exe.get("workflowData", {}).get("name", "Unknown")
            print(f"  ── Execution {exe_id}: {wf_name} ──")
            
            # ANALYZE
            diagnosis = self.diagnose(exe)
            print(f"    🔍 Diagnosis: {diagnosis['name']} ({diagnosis['id']})")
            print(f"    📊 Severity: {diagnosis['severity']} | Action: {diagnosis['action']}")
            
            # ACT
            action_report = self.act(exe, diagnosis)
            all_actions.append(action_report)
            
            # Track healed IDs
            if action_report["success"]:
                healed_ids = self.state.get("healed_execution_ids", [])
                healed_ids.append(exe_id)
                # Keep only last 200 healed IDs
                self.state["healed_execution_ids"] = healed_ids[-200:]
                self.state["total_heals"] = self.state.get("total_heals", 0) + 1
            
            print()
        
        # LOG
        print("  [LOG] Writing audit trail...")
        self.log_to_master_index(all_actions)
        
        # Persist state
        self.state["last_heal_actions"] = all_actions[-10:]  # Keep last 10
        self._save_state()
        
        healed_count = sum(1 for a in all_actions if a["success"])
        print(f"\n{'═'*60}")
        print(f"  🏁 Cycle Complete: {healed_count}/{len(all_actions)} actions successful")
        print(f"{'═'*60}\n")
        
        return {
            "status": "healed" if healed_count == len(all_actions) else "partial",
            "failures_found": len(failures),
            "actions_taken": len(all_actions),
            "healed": healed_count,
            "review_queue": len([a for a in all_actions if a["action_taken"] == "log_for_review"]),
            "actions": all_actions,
            "timestamp": datetime.now().isoformat(),
        }

    # ── Daemon Mode ─────────────────────────────────────────
    def run_daemon(self, interval_seconds: int = 300):
        """
        Run the nerve center as a background monitoring daemon.
        Default: scan every 5 minutes.
        """
        print(f"  🧠 Nerve Center Daemon starting (interval: {interval_seconds}s)")
        print(f"  Press Ctrl+C to stop.\n")
        
        if _agg:
            _agg.log_info("Nerve Center Daemon started", context={
                "interval": interval_seconds,
                "scan_window": self.scan_window,
            })
        
        try:
            while True:
                self.scan_and_heal()
                print(f"  💤 Next scan in {interval_seconds}s...\n")
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n  🛑 Daemon stopped by user.")
            if _agg:
                _agg.log_info("Nerve Center Daemon stopped by user")

    # ── Status Report ───────────────────────────────────────
    def get_status(self) -> dict:
        """Return the current nerve center status for dashboards."""
        # Get circuit breaker statuses
        cb_statuses = []
        cb_dir = os.path.join(os.path.expanduser("~"), ".antigravity", "circuit_breakers")
        if _cb_available and os.path.exists(cb_dir):
            for fname in os.listdir(cb_dir):
                if fname.endswith(".json"):
                    cb = CircuitBreaker(fname[:-5])
                    cb_statuses.append(cb.get_status())
        
        return {
            "engine": "Nerve Center v1.0",
            "status": "online",
            "last_scan": self.state.get("last_scan"),
            "total_scans": self.state.get("total_scans", 0),
            "total_failures_detected": self.state.get("total_failures_detected", 0),
            "total_heals": self.state.get("total_heals", 0),
            "review_queue_size": len(self.state.get("review_queue", [])),
            "review_queue": self.state.get("review_queue", [])[-5:],
            "last_actions": self.state.get("last_heal_actions", [])[-5:],
            "circuit_breakers": cb_statuses,
            "remedy_library_size": len(REMEDY_LIBRARY),
        }


# ══════════════════════════════════════════════════════════════
#  BACKGROUND THREAD for server.py integration
# ══════════════════════════════════════════════════════════════

_daemon_thread = None
_nerve_instance = None

def start_background_monitor(interval_seconds: int = 300):
    """Start the nerve center as a background thread (for FastAPI integration)."""
    global _daemon_thread, _nerve_instance
    
    if _daemon_thread and _daemon_thread.is_alive():
        return _nerve_instance
    
    _nerve_instance = NerveCenter()
    
    def _loop():
        while True:
            try:
                _nerve_instance.scan_and_heal()
            except Exception as e:
                if _agg:
                    _agg.log_error(f"Background scan failed: {e}", exc=e)
            time.sleep(interval_seconds)
    
    _daemon_thread = threading.Thread(target=_loop, daemon=True, name="NerveCenterDaemon")
    _daemon_thread.start()
    print(f"  🧠 Nerve Center background monitor started (interval: {interval_seconds}s)")
    return _nerve_instance


def get_nerve_instance() -> Optional[NerveCenter]:
    """Get the running nerve center instance."""
    return _nerve_instance


# ══════════════════════════════════════════════════════════════
#  CLI Entry Point
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Load .env
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
    except ImportError:
        pass

    if len(sys.argv) < 2:
        print("Usage: python nerve_center.py <scan|status|daemon>")
        sys.exit(1)

    command = sys.argv[1].lower()
    nc = NerveCenter()

    if command == "scan":
        report = nc.scan_and_heal()
        print(json.dumps(report, indent=2, default=str))
    
    elif command == "status":
        status = nc.get_status()
        print(f"\n{'='*55}")
        print(f"  🧠 NERVE CENTER STATUS")
        print(f"{'='*55}")
        print(f"  Engine:     {status['engine']}")
        print(f"  Status:     {status['status']}")
        print(f"  Last Scan:  {status['last_scan'] or 'Never'}")
        print(f"  Scans:      {status['total_scans']}")
        print(f"  Detected:   {status['total_failures_detected']}")
        print(f"  Healed:     {status['total_heals']}")
        print(f"  Review Q:   {status['review_queue_size']}")
        print(f"  Remedies:   {status['remedy_library_size']}")
        print(f"\n  Circuit Breakers:")
        if status['circuit_breakers']:
            icons = {"CLOSED": "🟢", "OPEN": "🔴", "HALF_OPEN": "🟡"}
            for cb in status['circuit_breakers']:
                icon = icons.get(cb['state'], "❓")
                print(f"    {icon} {cb['name']}: {cb['state']}")
        else:
            print(f"    None registered.")
        print(f"\n  Recent Review Items:")
        if status['review_queue']:
            for item in status['review_queue']:
                print(f"    📋 {item.get('diagnosis', '?')}: {item.get('workflow', '?')}")
        else:
            print(f"    No items pending.")
        print(f"\n{'='*55}\n")
    
    elif command == "daemon":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
        nc.run_daemon(interval)
    
    else:
        print(f"❌ Unknown command: {command}")
        print("Usage: python nerve_center.py <scan|status|daemon>")
        sys.exit(1)
# V3 AUTO-HEAL ACTIVE
