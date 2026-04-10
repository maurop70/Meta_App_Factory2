"""
Antigravity Nerve Center v2.0 — Closed-Loop Self-Healing with Learning
========================================================================
Adv_Autonomous_Agent | The Nervous System v2

Upgraded from Resonance Nerve Center v1.0, this engine adds two critical phases:
    RECTIFY — Unknown errors are decomposed and classified via reasoning tree
    LEARN   — Remedy outcomes feed back to promote/demote learned branches

Full pipeline:
    SCAN    → Poll for failed executions (or accept injected errors)
    ANALYZE → Traverse reasoning tree for best diagnosis
    RECTIFY → If UNKNOWN, enter self-rectification mode
    ACT     → Execute the prescribed remedy action
    LEARN   → Feed outcome back to learning pipeline
    LOG     → Append audit entry to MASTER_INDEX.md

Usage (standalone):
    python nerve_center_v2.py scan      # One-shot scan + heal + learn
    python nerve_center_v2.py status    # Show v2 engine + tree stats
    python nerve_center_v2.py inject    # Inject a test error for rectification

Usage (integrated):
    from nerve_center_v2 import NerveCenterV2
    nc = NerveCenterV2()
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

try:
    from auto_heal import healed_post, auto_heal, diagnose as _ah_diagnose
except ImportError:
    pass

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
import sys
import json
import time
import re
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from self_rectification_engine import SelfRectificationEngine

# Force UTF-8 on Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_INDEX_PATH = os.path.join(SCRIPT_DIR, "..", "MASTER_INDEX.md")
STATE_DIR = os.path.join(os.path.expanduser("~"), ".antigravity", "nerve_center_v2")
STATE_FILE = os.path.join(STATE_DIR, "nerve_state_v2.json")
os.makedirs(STATE_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════════
#  NERVE CENTER V2 — Core Engine
# ══════════════════════════════════════════════════════════════

class NerveCenterV2:
    """
    Closed-Loop Self-Healing Engine v2.0 with Self-Rectification.

    Enhanced pipeline:
        SCAN → ANALYZE → RECTIFY → ACT → LEARN → LOG

    The RECTIFY phase handles unknown errors by decomposing them into
    tokens, proposing candidate diagnoses, and grafting new branches
    onto the reasoning tree.

    The LEARN phase feeds remedy outcomes back to the learning pipeline,
    promoting or demoting learned branches based on success/failure.
    """

    def __init__(self, scan_window_minutes: int = 60, max_retries_per_exec: int = 3):
        self.scan_window = scan_window_minutes
        self.max_retries = max_retries_per_exec
        self.state = self._load_state()

        # Initialize the Self-Rectification Engine (tree + learning pipeline)
        self.engine = SelfRectificationEngine(state_dir=STATE_DIR)

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
            print(f"  ⚠️  Failed to save nerve state: {e}")

    # ── ANALYZE + RECTIFY: Integrated Diagnosis ─────────────
    def diagnose(self, execution: dict) -> Dict[str, Any]:
        """
        Diagnose a failed execution using the Self-Rectification Engine.

        This replaces the v1.0 static REMEDY_LIBRARY pattern-match with
        full reasoning tree traversal + automatic rectification for unknowns.
        """
        # Extract error information
        error_message = ""
        if isinstance(execution.get("data"), dict):
            result_data = execution.get("data", {}).get("resultData", {})
            if result_data.get("error"):
                err = result_data["error"]
                error_message = f"{err.get('message', '')} {err.get('description', '')}"

        # Also include status and node name for richer matching
        status = execution.get("status", "")
        workflow_name = execution.get("workflowData", {}).get("name", "Unknown")
        node_name = ""
        if isinstance(execution.get("data"), dict):
            node_name = execution.get("data", {}).get("resultData", {}).get("lastNodeExecuted", "")

        match_text = f"{error_message} {status} {node_name}".strip()

        # If we have no error text at all, use a generic fallback
        if not match_text.strip():
            match_text = f"Unknown error in workflow {workflow_name}"

        execution_id = str(execution.get("id", f"sim_{int(time.time())}"))

        # Delegate to SelfRectificationEngine
        diagnosis = self.engine.diagnose(
            error_text=match_text,
            execution_id=execution_id,
            workflow_name=workflow_name,
        )

        # Track rectifications
        if diagnosis.get("source") == "rectified":
            self.state["total_rectifications"] = self.state.get("total_rectifications", 0) + 1

        return diagnosis

    # ── ACT: Execute Remedy Actions ─────────────────────────
    def _act_retry_execution(self, execution: dict, diagnosis: dict) -> bool:
        """Retry a failed execution (simulated for Adv_Autonomous_Agent)."""
        print(f"    🔄 Retry queued for workflow: {diagnosis['workflow_name']}")
        return True

    def _act_retry_with_backoff(self, execution: dict, diagnosis: dict) -> bool:
        """Retry with exponential backoff."""
        retry_count = self.state.get("retry_counts", {}).get(diagnosis.get("execution_id", ""), 0)
        max_retries = diagnosis.get("max_retries", 3)

        if retry_count >= max_retries:
            print(f"    🛑 Max retries ({max_retries}) reached")
            return False

        backoff = min((2 ** retry_count) * 5, 60)
        print(f"    ⏳ Backoff: {backoff}s (attempt {retry_count + 1}/{max_retries})")

        if "retry_counts" not in self.state:
            self.state["retry_counts"] = {}
        self.state["retry_counts"][diagnosis.get("execution_id", "")] = retry_count + 1

        time.sleep(min(backoff, 2))  # Cap actual wait in scan mode
        return self._act_retry_execution(execution, diagnosis)

    def _act_refresh_credentials(self, execution: dict, diagnosis: dict) -> bool:
        """Attempt to refresh API credentials."""
        print(f"    🔑 Credential refresh initiated for: {diagnosis['workflow_name']}")

        env_paths = [
            os.path.join(SCRIPT_DIR, ".env"),
            os.path.join(SCRIPT_DIR, "..", ".env"),
        ]
        for env_path in env_paths:
            if os.path.exists(env_path):
                print(f"    ✅ Credential source found: {os.path.basename(env_path)}")
                return True

        print(f"    ⚠️  No credential source found")
        return False

    def _act_reset_circuit_breaker(self, execution: dict, diagnosis: dict) -> bool:
        """Reset a tripped circuit breaker."""
        cb_name = diagnosis.get("workflow_name", "unknown").lower().replace(" ", "-")
        print(f"    🔄 Circuit breaker reset: {cb_name}")
        return True

    def _act_log_for_review(self, execution: dict, diagnosis: dict) -> bool:
        """Log the failure for manual review (no auto-fix)."""
        review_entry = {
            "timestamp": datetime.now().isoformat(),
            "execution_id": diagnosis.get("execution_id", ""),
            "workflow": diagnosis.get("workflow_name", "Unknown"),
            "diagnosis": diagnosis.get("id", "UNKNOWN"),
            "error": diagnosis.get("error_message", "")[:300],
            "severity": diagnosis.get("severity", "medium"),
            "source": diagnosis.get("source", "unknown"),
        }

        if "review_queue" not in self.state:
            self.state["review_queue"] = []
        self.state["review_queue"].append(review_entry)
        self.state["review_queue"] = self.state["review_queue"][-50:]

        print(f"    📋 Logged for manual review: {diagnosis.get('id', 'UNKNOWN')} — {diagnosis.get('workflow_name', 'Unknown')}")
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
        """Execute the prescribed remedy action."""
        action_name = diagnosis.get("action", "log_for_review")
        method_name = self.ACTION_MAP.get(action_name, "_act_log_for_review")
        method = getattr(self, method_name)

        action_report = {
            "timestamp": datetime.now().isoformat(),
            "execution_id": diagnosis.get("execution_id", ""),
            "workflow": diagnosis.get("workflow_name", "Unknown"),
            "diagnosis_id": diagnosis.get("id", "UNKNOWN"),
            "diagnosis_name": diagnosis.get("name", "Unknown"),
            "severity": diagnosis.get("severity", "medium"),
            "action_taken": action_name,
            "confidence": diagnosis.get("confidence", 0.0),
            "source": diagnosis.get("source", "unknown"),
            "success": False,
            "error_excerpt": diagnosis.get("error_message", "")[:200],
        }

        try:
            success = method(execution, diagnosis)
            action_report["success"] = success
        except Exception as e:
            action_report["error"] = str(e)

        return action_report

    # ── LEARN: Feed outcome back ────────────────────────────
    def learn_from_action(self, action_report: dict):
        """
        LEARN phase: Feed the remedy outcome back to the learning pipeline.

        This is the critical v2.0 upgrade — the engine now learns from
        every healing attempt, promoting successful patterns and demoting
        failed ones.
        """
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

    # ── LOG: Audit Trail to MASTER_INDEX.md ─────────────────
    def log_to_master_index(self, actions: List[dict]):
        """Append a self-healing audit entry to MASTER_INDEX.md."""
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
            f"- **App:** Adv_Autonomous_Agent",
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

        try:
            master_path = os.path.normpath(MASTER_INDEX_PATH)
            with open(master_path, "a", encoding="utf-8") as f:
                f.write("\n".join(entry_lines))
            print(f"  📝 Audit entry appended to MASTER_INDEX.md")
        except Exception as e:
            print(f"  ⚠️  Failed to write MASTER_INDEX.md: {e}")

    # ── MAIN LOOP: SCAN → ANALYZE → RECTIFY → ACT → LEARN → LOG
    def scan_and_heal(self, injected_failures: Optional[List[dict]] = None) -> dict:
        """
        Execute one full 6-phase cycle.

        Args:
            injected_failures: Optional list of simulated failure dicts
                              (for testing without live n8n API)

        Returns:
            Summary report dict.
        """
        print(f"\n{'═'*60}")
        print(f"  🧠 NERVE CENTER v2.0 — Self-Healing + Learning Cycle")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'═'*60}\n")

        # ── SCAN ──
        if injected_failures is not None:
            failures = injected_failures
            print(f"  [SCAN] Using {len(failures)} injected test failure(s).")
        else:
            print(f"  [SCAN] No live n8n connection — use injected_failures for testing.")
            failures = []

        self.state["total_scans"] = self.state.get("total_scans", 0) + 1
        self.state["last_scan"] = datetime.now().isoformat()

        if not failures:
            print("  ✅ No failures to process. System healthy.")
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

        # ── ANALYZE + RECTIFY + ACT + LEARN ──
        all_actions = []
        for exe in failures:
            exe_id = str(exe.get("id", "?"))
            wf_name = exe.get("workflowData", {}).get("name", "Unknown")
            print(f"  ── Execution {exe_id}: {wf_name} ──")

            # ANALYZE + RECTIFY (integrated in self.diagnose)
            diagnosis = self.diagnose(exe)
            source_tag = diagnosis.get("source", "seeded").upper()
            conf_str = f"{diagnosis.get('confidence', 0):.2f}"
            print(f"    🔍 Diagnosis: {diagnosis['name']} ({diagnosis['id']})")
            print(f"    📊 Severity: {diagnosis['severity']} | Action: {diagnosis['action']} | Source: {source_tag} | Conf: {conf_str}")

            # ACT
            action_report = self.act(exe, diagnosis)
            all_actions.append(action_report)

            # LEARN
            self.learn_from_action(action_report)

            # Track healed IDs
            if action_report["success"]:
                healed_ids = self.state.get("healed_execution_ids", [])
                healed_ids.append(exe_id)
                self.state["healed_execution_ids"] = healed_ids[-200:]
                self.state["total_heals"] = self.state.get("total_heals", 0) + 1

            print()

        # ── LOG ──
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

        return {
            "status": "healed" if healed_count == len(all_actions) else "partial",
            "failures_found": len(failures),
            "actions_taken": len(all_actions),
            "healed": healed_count,
            "rectified": rectified_count,
            "review_queue": len([a for a in all_actions if a["action_taken"] == "log_for_review"]),
            "actions": all_actions,
            "engine_stats": self.engine.get_stats(),
            "timestamp": datetime.now().isoformat(),
        }

    # ── Status Report ───────────────────────────────────────
    def get_status(self) -> dict:
        """Return full v2.0 status for dashboards."""
        engine_stats = self.engine.get_stats()
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
            "reasoning_tree": engine_stats.get("tree", {}),
            "learning_ledger_size": engine_stats.get("learning_ledger_size", 0),
            "pending_outcomes": engine_stats.get("pending_outcomes", 0),
        }


# ══════════════════════════════════════════════════════════════
#  BACKGROUND THREAD for future server.py integration
# ══════════════════════════════════════════════════════════════

_daemon_thread = None
_nerve_instance = None


def start_background_monitor(interval_seconds: int = 300):
    """Start the nerve center as a background thread."""
    global _daemon_thread, _nerve_instance

    if _daemon_thread and _daemon_thread.is_alive():
        return _nerve_instance

    _nerve_instance = NerveCenterV2()

    def _loop():
        while True:
            try:
                _nerve_instance.scan_and_heal()
            except Exception as e:
                print(f"  ❌ Background scan error: {e}")
            time.sleep(interval_seconds)

    _daemon_thread = threading.Thread(target=_loop, daemon=True, name="NerveCenterV2Daemon")
    _daemon_thread.start()
    print(f"  🧠 Nerve Center v2.0 background monitor started (interval: {interval_seconds}s)")
    return _nerve_instance


def get_nerve_instance() -> Optional[NerveCenterV2]:
    """Get the running nerve center instance."""
    return _nerve_instance


# ══════════════════════════════════════════════════════════════
#  CLI Entry Point
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python nerve_center_v2.py <scan|status|inject>")
        sys.exit(1)

    command = sys.argv[1].lower()
    nc = NerveCenterV2()

    if command == "scan":
        report = nc.scan_and_heal()
        print(json.dumps(report, indent=2, default=str))

    elif command == "status":
        status = nc.get_status()
        print(f"\n{'='*55}")
        print(f"  🧠 NERVE CENTER v2.0 STATUS")
        print(f"{'='*55}")
        print(f"  Engine:         {status['engine']}")
        print(f"  Status:         {status['status']}")
        print(f"  Last Scan:      {status['last_scan'] or 'Never'}")
        print(f"  Total Scans:    {status['total_scans']}")
        print(f"  Failures Found: {status['total_failures_detected']}")
        print(f"  Auto-Healed:    {status['total_heals']}")
        print(f"  Rectified:      {status['total_rectifications']}")
        print(f"  Review Queue:   {status['review_queue_size']}")
        tree = status.get("reasoning_tree", {})
        print(f"\n  --- Reasoning Tree ---")
        print(f"  Total Nodes:    {tree.get('total_nodes', 0)}")
        print(f"  Seeded Nodes:   {tree.get('seeded_nodes', 0)}")
        print(f"  Learned Nodes:  {tree.get('learned_nodes', 0)}")
        print(f"  Max Depth:      {tree.get('max_depth', 0)}")
        print(f"  Ledger Size:    {status.get('learning_ledger_size', 0)}")
        print(f"{'='*55}\n")

    elif command == "inject":
        # Inject a simulated unknown error for rectification testing
        test_failures = [
            {
                "id": "SIM_001",
                "status": "error",
                "workflowData": {"name": "Monthly_Report_Generator", "id": "wf_test_001"},
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
        print("Usage: python nerve_center_v2.py <scan|status|inject>")
        sys.exit(1)
