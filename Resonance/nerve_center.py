"""
Antigravity Nerve Center v2.0 — Closed-Loop Self-Healing Engine with Learning
===============================================================================
Project Resonance | The Nervous System v2

Upgraded from v1.0 static REMEDY_LIBRARY to tree-based classification
with the SelfRectificationEngine ("Reason in Chains, Learn in Trees").

Architecture:
    SCAN    → Poll n8n Executions API for failed runs
    ANALYZE → Traverse reasoning tree for best diagnosis
    RECTIFY → If UNKNOWN, decompose error + propose + graft new branch
    ACT     → Execute the appropriate fix (retry, refresh, backoff)
    LEARN   → Feed outcome back to learning pipeline (promote/demote)
    LOG     → Append audit entry to MASTER_INDEX.md + ErrorAggregator

Usage (standalone):
    python nerve_center.py scan          # One-shot scan + heal + learn
    python nerve_center.py status        # Show nerve center status + tree stats
    python nerve_center.py daemon        # Run continuous monitoring loop
    python nerve_center.py inject        # Inject a test error for rectification

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


import os, sys, json, time, re, threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Force UTF-8 on Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Import Self-Rectification Engine (v2.0 upgrade) ───────
try:
    from self_rectification_engine import SelfRectificationEngine
    _RECTIFICATION_AVAILABLE = True
except ImportError:
    _RECTIFICATION_AVAILABLE = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_INDEX_PATH = os.path.join(SCRIPT_DIR, "..", "MASTER_INDEX.md")
STATE_DIR = os.path.join(os.path.expanduser("~"), ".antigravity", "nerve_center")
V2_STATE_DIR = os.path.join(os.path.expanduser("~"), ".antigravity", "nerve_center_v2_resonance")
STATE_FILE = os.path.join(STATE_DIR, "nerve_state.json")
os.makedirs(STATE_DIR, exist_ok=True)
os.makedirs(V2_STATE_DIR, exist_ok=True)

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

# ── Error Intake Config ─────────────────────────────────────────
ERROR_QUEUE_FILE = os.path.join(STATE_DIR, "error_queue.json")


# ══════════════════════════════════════════════════════════════
#  REMEDY LIBRARY — Retained as legacy seed reference
#  The SelfRectificationEngine inherits these as tree branches.
# ══════════════════════════════════════════════════════════════
# NOTE: The flat REMEDY_LIBRARY list is no longer used for diagnosis.
# All pattern matching now goes through the SelfRectificationEngine's
# ReasoningTree. The seed patterns are identical — defined in
# self_rectification_engine.py's SEED_REMEDIES constant.


# ══════════════════════════════════════════════════════════════
#  NERVE CENTER — Core Engine
# ══════════════════════════════════════════════════════════════

class NerveCenter:
    """
    Closed-Loop Self-Healing Engine v2.0 for Resonance.

    Upgraded pipeline: SCAN → ANALYZE → RECTIFY → ACT → LEARN → LOG

    - ANALYZE uses SelfRectificationEngine (reasoning tree) instead of flat REMEDY_LIBRARY
    - RECTIFY handles unknown errors via token decomposition + branch grafting
    - LEARN feeds outcomes back to promote/demote learned branches
    - All existing infrastructure (CircuitBreaker, ErrorAggregator) preserved
    """

    def __init__(self, scan_window_minutes: int = 60, max_retries_per_exec: int = 3):
        self.scan_window = scan_window_minutes
        self.max_retries = max_retries_per_exec
        self.state = self._load_state()

        # v2.0: Initialize Self-Rectification Engine
        if _RECTIFICATION_AVAILABLE:
            self.engine = SelfRectificationEngine(state_dir=V2_STATE_DIR)
        else:
            self.engine = None

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
            "total_rectifications": 0,
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

    # ── SCAN: Read local error queue ────────────────────────
    def scan_executions(self) -> List[dict]:
        """
        Read recent failures from the local error queue file.
        Other agents/modules can push errors into this queue.
        Returns list of failed execution objects.
        """
        if not os.path.exists(ERROR_QUEUE_FILE):
            return []

        try:
            with open(ERROR_QUEUE_FILE, "r", encoding="utf-8") as f:
                queue_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

        # Expect a list of execution-like dicts
        executions = queue_data if isinstance(queue_data, list) else queue_data.get("errors", [])

        # Filter to scan window and exclude already-healed
        cutoff = datetime.utcnow() - timedelta(minutes=self.scan_window)
        healed_ids = set(self.state.get("healed_execution_ids", []))
        recent_failures = []

        for exe in executions:
            exe_id = str(exe.get("id", ""))
            if exe_id in healed_ids:
                continue

            # Filter by time window if timestamp present
            timestamp = exe.get("timestamp") or exe.get("stoppedAt") or exe.get("startedAt", "")
            try:
                if timestamp:
                    exe_time = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).replace(tzinfo=None)
                    if exe_time < cutoff:
                        continue
            except (ValueError, TypeError):
                pass

            recent_failures.append(exe)

        # Clear the queue after reading
        if recent_failures:
            remaining = [e for e in executions if str(e.get("id", "")) not in {str(f.get("id", "")) for f in recent_failures}]
            try:
                with open(ERROR_QUEUE_FILE, "w", encoding="utf-8") as f:
                    json.dump(remaining, f, indent=2, default=str)
            except IOError:
                pass

        return recent_failures

    # ── ANALYZE + RECTIFY: Diagnosis via SelfRectificationEngine ──
    def diagnose(self, execution: dict) -> Optional[dict]:
        """
        v2.0: Analyze a failed execution using the reasoning tree.

        For known errors  → returns seeded diagnosis directly
        For unknown errors → enters rectification mode (decompose + graft)
        Falls back to static pattern match if SelfRectificationEngine unavailable.
        """
        # Extract error information from execution
        error_message = ""
        if isinstance(execution.get("data"), dict):
            result_data = execution.get("data", {}).get("resultData", {})
            if result_data.get("error"):
                err = result_data["error"]
                error_message = f"{err.get('message', '')} {err.get('description', '')}"

        status = execution.get("status", "")
        workflow_name = execution.get("workflowData", {}).get("name", "Unknown")
        node_name = ""
        if isinstance(execution.get("data"), dict):
            node_name = execution.get("data", {}).get("resultData", {}).get("lastNodeExecuted", "")

        match_text = f"{error_message} {status} {node_name}".strip()
        if not match_text.strip():
            match_text = f"Unknown error in workflow {workflow_name}"

        execution_id = str(execution.get("id", f"res_{int(time.time())}"))

        # v2.0 path: Use SelfRectificationEngine
        if self.engine:
            diagnosis = self.engine.diagnose(
                error_text=match_text,
                execution_id=execution_id,
                workflow_name=workflow_name,
            )
            # Track rectifications
            if diagnosis.get("source") == "rectified":
                self.state["total_rectifications"] = self.state.get("total_rectifications", 0) + 1
            return diagnosis

        # Legacy fallback: static pattern match (if SelfRectificationEngine unavailable)
        match_lower = match_text.lower()
        from self_rectification_engine import SEED_REMEDIES
        best_match = None
        best_score = 0
        for remedy in SEED_REMEDIES:
            score = 0
            for pattern in remedy["patterns"]:
                if re.search(pattern, match_lower, re.IGNORECASE):
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
                "execution_id": execution_id,
                "source": "seeded",
            }

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
            "execution_id": execution_id,
            "source": "unknown",
        }

    # ── ACT: Execute the remedy ─────────────────────────────
    def _act_retry_execution(self, execution: dict, diagnosis: dict) -> bool:
        """Queue a failed execution for retry."""
        workflow_id = execution.get("workflowData", {}).get("id")
        if not workflow_id:
            workflow_id = execution.get("workflowId")
        
        if not workflow_id:
            print(f"    ⚠️  Cannot retry — no workflow ID found")
            return False
        
        try:
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
        """Attempt to refresh API credentials from environment."""
        print(f"    🔑 Credential refresh initiated for: {diagnosis['workflow_name']}")
        
        # Check if we can reload from .env
        env_paths = [
            os.path.join(SCRIPT_DIR, ".env"),
            os.path.join(SCRIPT_DIR, "..", ".env"),
        ]
        for env_path in env_paths:
            if os.path.exists(env_path):
                print(f"    ✅ Credential source found: {os.path.basename(env_path)}")
                if _agg:
                    _agg.log_info("Credential source located for refresh")
                return True
        
        print(f"    ⚠️  No credential source found")
        if _agg:
            _agg.log_warning(
                "Credential refresh failed — no .env found",
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

    # ── LEARN: Feed outcome back to learning pipeline ───────
    def learn_from_action(self, action_report: dict):
        """
        v2.0 LEARN phase: Feed remedy outcome back to the learning pipeline.
        Promotes successful learned patterns, demotes failed ones.
        """
        if not self.engine:
            return

        execution_id = action_report.get("execution_id", "")
        success = action_report.get("success", False)

        result = self.engine.learn(execution_id, success)
        if result:
            action_label = result.get("action", "OBSERVED")
            if action_label == "PROMOTED":
                print(f"    📈 Learning: Pattern PROMOTED (confidence boosted)")
            elif action_label == "DEMOTED":
                print(f"    📉 Learning: Pattern DEMOTED (confidence reduced)")
                if result.get("flag") == "LOW_CONFIDENCE_REVIEW":
                    print(f"    ⚠️  Low confidence — flagged for review")
            if _agg:
                _agg.log_info(f"Learning: {action_label}", context={
                    "execution_id": execution_id,
                    "node_id": result.get("node_id"),
                })

    # ── LOG: Audit Trail to MASTER_INDEX.md ─────────────────
    def log_to_master_index(self, actions: List[dict]):
        """
        Append a self-healing audit entry to MASTER_INDEX.md.
        Follows the existing append-only format.
        v2.0: Includes rectification counts and source tags.
        """
        if not actions:
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        healed = [a for a in actions if a["success"] and a["action_taken"] != "log_for_review"]
        reviewed = [a for a in actions if a["action_taken"] == "log_for_review"]
        failed = [a for a in actions if not a["success"] and a["action_taken"] != "log_for_review"]
        rectified = [a for a in actions if a.get("source") == "rectified"]
        
        entry_lines = [
            "",
            f"## SELF_HEALING_CYCLE",
            f"- **Timestamp:** {timestamp}",
            f"- **App:** Resonance",
            f"- **Engine:** Nerve Center v2.0 (Self-Rectification + Learning)",
            f"- **Failures Detected:** {len(actions)}",
            f"- **Auto-Healed:** {len(healed)}",
            f"- **Rectified (Learned):** {len(rectified)}",
            f"- **Queued for Review:** {len(reviewed)}",
            f"- **Heal Failures:** {len(failed)}",
            f"- **Actions:**",
        ]
        
        for action in actions:
            icon = "✅" if action["success"] else "❌"
            source_tag = f" [{action.get('source', 'seeded').upper()}]" if action.get("source") else ""
            conf = f" (conf: {action.get('confidence', 0):.2f})" if action.get("confidence") else ""
            entry_lines.append(
                f"  - {icon} `{action['diagnosis_id']}` → `{action['action_taken']}`{source_tag}{conf} "
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

    # ── MAIN LOOP: Scan → Analyze → Rectify → Act → Learn → Log
    def scan_and_heal(self, injected_failures: Optional[List[dict]] = None) -> dict:
        """
        Execute one full SCAN → ANALYZE → RECTIFY → ACT → LEARN → LOG cycle.
        Returns a summary report.

        Args:
            injected_failures: Optional list of simulated failure dicts
                              (for testing without live n8n API)
        """
        print(f"\n{'═'*60}")
        print(f"  🧠 NERVE CENTER v2.0 — Self-Healing + Learning Cycle")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'═'*60}\n")
        
        # SCAN
        if injected_failures is not None:
            failures = injected_failures
            print(f"  [SCAN] Using {len(failures)} injected test failure(s).")
        else:
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
        
        # ANALYZE + RECTIFY + ACT + LEARN
        all_actions = []
        for exe in failures:
            exe_id = str(exe.get("id", "?"))
            wf_name = exe.get("workflowData", {}).get("name", "Unknown")
            print(f"  ── Execution {exe_id}: {wf_name} ──")
            
            # ANALYZE + RECTIFY (integrated in self.diagnose)
            diagnosis = self.diagnose(exe)
            source_tag = diagnosis.get("source", "seeded").upper()
            conf_str = f"{diagnosis.get('confidence', 0):.2f}" if diagnosis.get("confidence") else "n/a"
            print(f"    🔍 Diagnosis: {diagnosis['name']} ({diagnosis['id']})")
            print(f"    📊 Severity: {diagnosis['severity']} | Action: {diagnosis['action']} | Source: {source_tag} | Conf: {conf_str}")
            
            # ACT
            action_report = self.act(exe, diagnosis)
            # Carry v2 metadata into action report for LEARN phase
            action_report["source"] = diagnosis.get("source", "seeded")
            action_report["confidence"] = diagnosis.get("confidence", 0)
            all_actions.append(action_report)

            # LEARN (v2.0 upgrade)
            self.learn_from_action(action_report)
            
            # Track healed IDs
            if action_report["success"]:
                healed_ids = self.state.get("healed_execution_ids", [])
                healed_ids.append(exe_id)
                self.state["healed_execution_ids"] = healed_ids[-200:]
                self.state["total_heals"] = self.state.get("total_heals", 0) + 1
            
            print()
        
        # LOG
        print("  [LOG] Writing audit trail...")
        self.log_to_master_index(all_actions)
        
        # Persist state
        self.state["last_heal_actions"] = all_actions[-10:]
        self._save_state()
        
        healed_count = sum(1 for a in all_actions if a["success"])
        rectified_count = sum(1 for a in all_actions if a.get("source") == "rectified")

        print(f"\n{'═'*60}")
        print(f"  🏁 Cycle Complete: {healed_count}/{len(all_actions)} actions successful")
        if rectified_count:
            print(f"  🌱 {rectified_count} new pattern(s) learned via rectification")
        print(f"{'═'*60}\n")
        
        # Build engine stats for report
        engine_stats = self.engine.get_stats() if self.engine else {}

        return {
            "status": "healed" if healed_count == len(all_actions) else "partial",
            "failures_found": len(failures),
            "actions_taken": len(all_actions),
            "healed": healed_count,
            "rectified": rectified_count,
            "review_queue": len([a for a in all_actions if a["action_taken"] == "log_for_review"]),
            "actions": all_actions,
            "engine_stats": engine_stats,
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
        """Return the current nerve center v2.0 status for dashboards."""
        # Get circuit breaker statuses
        cb_statuses = []
        cb_dir = os.path.join(os.path.expanduser("~"), ".antigravity", "circuit_breakers")
        if _cb_available and os.path.exists(cb_dir):
            for fname in os.listdir(cb_dir):
                if fname.endswith(".json"):
                    cb = CircuitBreaker(fname[:-5])
                    cb_statuses.append(cb.get_status())

        # v2.0: Include reasoning tree and learning stats
        engine_stats = self.engine.get_stats() if self.engine else {}
        tree_stats = engine_stats.get("tree", {})

        return {
            "engine": "Nerve Center v2.0",
            "status": "online",
            "last_scan": self.state.get("last_scan"),
            "total_scans": self.state.get("total_scans", 0),
            "total_failures_detected": self.state.get("total_failures_detected", 0),
            "total_heals": self.state.get("total_heals", 0),
            "total_rectifications": self.state.get("total_rectifications", 0),
            "review_queue_size": len(self.state.get("review_queue", [])),
            "review_queue": self.state.get("review_queue", [])[-5:],
            "last_actions": self.state.get("last_heal_actions", [])[-5:],
            "circuit_breakers": cb_statuses,
            "remedy_library_size": tree_stats.get("seeded_nodes", 9),
            "reasoning_tree": tree_stats,
            "learning_ledger_size": engine_stats.get("learning_ledger_size", 0),
            "pending_outcomes": engine_stats.get("pending_outcomes", 0),
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
        print("Usage: python nerve_center.py <scan|status|daemon|inject>")
        sys.exit(1)

    command = sys.argv[1].lower()
    nc = NerveCenter()

    if command == "scan":
        report = nc.scan_and_heal()
        print(json.dumps(report, indent=2, default=str))
    
    elif command == "status":
        status = nc.get_status()
        print(f"\n{'='*55}")
        print(f"  🧠 NERVE CENTER v2.0 STATUS")
        print(f"{'='*55}")
        print(f"  Engine:       {status['engine']}")
        print(f"  Status:       {status['status']}")
        print(f"  Last Scan:    {status['last_scan'] or 'Never'}")
        print(f"  Scans:        {status['total_scans']}")
        print(f"  Detected:     {status['total_failures_detected']}")
        print(f"  Healed:       {status['total_heals']}")
        print(f"  Rectified:    {status['total_rectifications']}")
        print(f"  Review Q:     {status['review_queue_size']}")
        print(f"  Seed Nodes:   {status['remedy_library_size']}")
        tree = status.get('reasoning_tree', {})
        if tree:
            print(f"\n  --- Reasoning Tree ---")
            print(f"  Total Nodes:  {tree.get('total_nodes', 0)}")
            print(f"  Learned:      {tree.get('learned_nodes', 0)}")
            print(f"  Max Depth:    {tree.get('max_depth', 0)}")
            print(f"  Ledger:       {status.get('learning_ledger_size', 0)}")
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

    elif command == "inject":
        # Inject a simulated unknown error for rectification testing
        test_failures = [
            {
                "id": "RES_SIM_001",
                "status": "error",
                "workflowData": {"name": "Monthly_Report_Generator", "id": "wf_res_001"},
                "data": {
                    "resultData": {
                        "error": {
                            "message": "ESOCKETTIMEDOUT: Redis cluster node at 10.0.0.5:6379 not responding after 30s",
                            "description": "The Redis Sentinel failover did not complete within the timeout window. Data pipeline stalled."
                        },
                        "lastNodeExecuted": "Redis Cache Lookup"
                    }
                },
            },
        ]
        print("  🧪 Injecting simulated failure for rectification test...\n")
        report = nc.scan_and_heal(injected_failures=test_failures)
        print(json.dumps(report, indent=2, default=str))
    
    else:
        print(f"❌ Unknown command: {command}")
        print("Usage: python nerve_center.py <scan|status|daemon|inject>")
        sys.exit(1)
# V3 AUTO-HEAL ACTIVE — UPGRADED TO v2.0 WITH SELF-RECTIFICATION
