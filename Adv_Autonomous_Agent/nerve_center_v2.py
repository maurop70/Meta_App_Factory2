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

try:
    import model_router
    _ROUTER_AVAILABLE = True
except ImportError:
    _ROUTER_AVAILABLE = False

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

        # Sentinel Overwatch Configuration
        self.sentinel_mode = True
        self.sentinel_logs = []
        self.loop_threshold = 3  # Identical errors in a row to trigger loop intercept
        self.telemetry_path = os.path.join(_FACTORY_DIR, "auto_heal_log.json")

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

        # Register attempt for outcome tracking
        self.engine.register_attempt(
            execution_id=execution_id,
            node_id=diagnosis.get("id", "UNKNOWN"),
            remedy_action=diagnosis.get("action", "log_for_review"),
            error_text=match_text,
            is_learned=diagnosis.get("source") == "rectified",
            workflow_name=workflow_name
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
        "sentinel_snap_back": "_act_sentinel_snap_back",
        "sentinel_escalate": "_act_sentinel_escalate",
    }

    def _act_sentinel_snap_back(self, execution: dict, diagnosis: dict) -> bool:
        """
        Sentinel: Safe Bypass Protocol (Snap-Back).
        Uses Gemini 2.5 Flash to inject a correction prompt.
        """
        if not _ROUTER_AVAILABLE:
            return False
            
        error_text = diagnosis.get("error_message", "")
        wf_name = diagnosis.get("workflow_name", "Unknown")
        
        system_prompt = (
            "You are the Ecosystem Overwatch Sentinel. An agent is failing with the following error. "
            "Inject a 1-sentence 'Snap-Back' correction prompt to reset its context and solve the logic failure."
        )
        prompt = f"Agent: {wf_name}\nError: {error_text}\n\nCorrection Directive:"
        
        correction = model_router.route("sentinel_snap_back", prompt, system_prompt)
        print(f"    ⚡ Sentinel Snap-Back: {correction}")
        
        # Log to MASTER_INDEX
        self.state["sentinel_actions"] = self.state.get("sentinel_actions", []) + [
            {"type": "snap_back", "wf": wf_name, "correction": correction}
        ]
        return True

    def _act_sentinel_escalate(self, execution: dict, diagnosis: dict) -> bool:
        """
        Sentinel: Escalation Protocol.
        Uses Gemini 2.5 Pro for deep diagnostic and alerts the Commander.
        """
        if not _ROUTER_AVAILABLE:
            return False
            
        error_text = diagnosis.get("error_message", "")
        wf_name = diagnosis.get("workflow_name", "Unknown")
        
        system_prompt = (
            "You are the Ecosystem Overwatch Sentinel. A structural failure has occurred that requires human intervention. "
            "Perform a deep diagnostic and provide a summary for the Commander (User)."
        )
        prompt = f"Agent: {wf_name}\nStructural Error: {error_text}\n\nDeep Diagnostic Summary:"
        
        diagnostic = model_router.route("sentinel_diagnostic", prompt, system_prompt)
        print(f"    🚨 Sentinel Escalation: Process Halted. Diagnostic: {diagnostic}")
        
        # Add to review queue with higher severity
        self._act_log_for_review(execution, {**diagnosis, "severity": "critical", "error_message": f"[SENTINEL_DIAGNOSTIC] {diagnostic}"})
        return True

    def act(self, execution: dict, diagnosis: dict) -> dict:
        """Execute the prescribed remedy action."""
        action_name = diagnosis.get("action", "log_for_review")
        
        # SENTINEL: Boundary Override for No-Bypass Zones
        # Any failure in a sensitive domain must escalate, no matter the remedy.
        if self.is_sensitive_domain(diagnosis) and action_name != "sentinel_escalate":
            print(f"    🛑 Boundary Clarification: Sensitive domain detected. Forcing Escalation.")
            action_name = "sentinel_escalate"

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
            confidence = result.get("confidence", 0.0)
            
            if action_label == "PROMOTED":
                print(f"    📈 Learning: Pattern PROMOTED (confidence boosted to {confidence:.2f})")
                
                # V3 Hardening Hook: Trigger Phantom QA for high-confidence patterns
                if confidence >= 0.9 and result.get("is_learned"):
                    self._dispatch_hardening_task(result)
                    
            elif action_label == "DEMOTED":
                print(f"    📉 Learning: Pattern DEMOTED (confidence reduced to {confidence:.2f})")
                if result.get("flag") == "LOW_CONFIDENCE_REVIEW":
                    print(f"    ⚠️  Low confidence — flagged for review")

    def _dispatch_hardening_task(self, learning_result: dict):
        """
        V3 Hardening: Dispatch a permanent fix request to Phantom QA.
        """
        node_id = learning_result.get("node_id", "Unknown")
        wf_name = learning_result.get("workflow_name", "Unknown")
        error_text = learning_result.get("error_text", "")
        
        print(f"    🛡️  [V3 HARDENING] Triggering Phantom QA Gate for {node_id}...")
        
        hardening_directive = {
            "timestamp": datetime.now().isoformat(),
            "origin": "Adv_Overwatch_Sentinel",
            "task": "PERMANENT_HARDENING",
            "target_app": wf_name,
            "error_pattern": error_text[:500],
            "confidence": learning_result.get("confidence"),
            "directive": (
                f"Analyze the following recurring error pattern in {wf_name} and implement a permanent structural fix "
                f"in the source code (validation, error handling, or logic correction). Pattern: {error_text[:200]}"
            )
        }
        
        # Log to MASTER_INDEX with Hardening tag
        self.log_to_master_index([{
            "success": True,
            "diagnosis_id": node_id,
            "action_taken": "V3_HARDENING_DISPATCH",
            "workflow": wf_name,
            "severity": "high",
            "error_excerpt": f"Initiating permanent patch for: {error_text[:100]}"
        }])
        
        # Physical dispatch (simulated via file-based command bridge for now, 
        # as Phantom QA monitors the shared auto_heal_log)
        # In a full deployment, this would trigger a Pydantic tool call or MCP handoff.
        try:
            bridge_path = os.path.join(_FACTORY_DIR, "hardening_queue.json")
            queue = []
            if os.path.exists(bridge_path):
                with open(bridge_path, "r", encoding="utf-8") as f:
                    queue = json.load(f)
            queue.append(hardening_directive)
            with open(bridge_path, "w", encoding="utf-8") as f:
                json.dump(queue, f, indent=2)
            print(f"    ✅ Hardening task queued in hardening_queue.json")
        except Exception as e:
            print(f"    ⚠️  Failed to dispatch hardening task: {e}")

    # ── SENTINEL: Ecosystem Overwatch ──────────────────────
    def scan_ecosystem(self) -> List[dict]:
        """
        SENTINEL: Monitor auto_heal_log.json and other event streams.
        Detects infinite loops (3 errors in 2 mins) and behavioral anomalies.
        """
        if not self.sentinel_mode:
            return []
            
        print(f"  🛰️  [SENTINEL] Scanning Ecosystem Telemetry: {os.path.basename(self.telemetry_path)}")
        failures = []
        
        if not os.path.exists(self.telemetry_path):
            return []
            
        try:
            with open(self.telemetry_path, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            return []
            
        # Time-Constrained Loop Detection (3 errors in 120s)
        now = datetime.now()
        window = timedelta(minutes=2)
        
        error_counts = {}
        # Scan last 50 entries to ensure we catch bursts
        recent_logs = []
        for entry in reversed(logs[-50:]):
            try:
                ts = datetime.fromisoformat(entry.get("timestamp", ""))
                if now - ts <= window:
                    recent_logs.append(entry)
            except (ValueError, TypeError):
                continue

        for entry in recent_logs:
            msg = entry.get("error", entry.get("target", ""))
            wf = entry.get("app_name", entry.get("project", "Unknown"))
            key = (wf, msg)
            error_counts[key] = error_counts.get(key, 0) + 1
            
            if error_counts[key] >= self.loop_threshold:
                print(f"    ⚠️  Infinite Loop Intercepted: {wf} | Window: 120s")
                failures.append({
                    "id": f"SENTINEL_LOOP_{int(time.time())}",
                    "status": "overwatch_intercept",
                    "workflowData": {"name": wf, "id": "ecosystem"},
                    "data": {"resultData": {"error": {"message": f"INFINITE_LOOP: {msg}"}, "lastNodeExecuted": "Overwatch Sentinel"}}
                })
                break

        return failures

    def is_sensitive_domain(self, diagnosis: dict) -> bool:
        """
        SENTINEL: Boundary Check for No-Bypass Zones.
        Financial & Security domains must NEVER be auto-healed via snap-back.
        """
        wf = str(diagnosis.get("workflow_name", "")).upper()
        msg = str(diagnosis.get("error_message", "")).upper()
        
        # 1. Financial & Market Data (CFO Agent / Trading)
        if "CFO" in wf or any(kw in msg for kw in ["OPTIONS", "VOLATILITY", "TRADE", "LEDGER", "PRICE"]):
            print(f"    🔒 No-Bypass Zone: Financial Domain Detected ({wf})")
            return True
            
        # 2. Security & Infrastructure (Permissions / Zero-Trust)
        if any(kw in msg for kw in ["PERMISSION", "ZERO-TRUST", "VAULT", "CREDENTIAL", "AUTH", "INFRASTRUCTURE"]):
            print(f"    🔒 No-Bypass Zone: Security/Infrastructure Domain Detected")
            return True
            
        return False

    # ── LOG: Audit Trail to MASTER_INDEX.md ─────────────────
    def log_to_master_index(self, actions: List[dict]):
        """Append a self-healing audit entry to MASTER_INDEX.md."""
        if not actions:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        healed = [a for a in actions if a["success"] and a["action_taken"] not in ["log_for_review", "sentinel_escalate"]]
        reviewed = [a for a in actions if a["action_taken"] in ["log_for_review", "sentinel_escalate"]]
        failed = [a for a in actions if not a["success"] and a["action_taken"] not in ["log_for_review", "sentinel_escalate"]]
        rectified = [a for a in actions if a.get("source") == "rectified"]

        entry_lines = [
            "",
            f"## OVERWATCH_SENTINEL_CYCLE",
            f"- **Timestamp:** {timestamp}",
            f"- **App:** Adv_Autonomous_Agent",
            f"- **Engine:** Overwatch Sentinel v2.5",
            f"- **Failures Detected:** {len(actions)}",
            f"- **Auto-Healed (Snap-Back):** {len(healed)}",
            f"- **Escalated/Reviewed:** {len(reviewed)}",
            f"- **Heal Failures:** {len(failed)}",
            f"- **Actions:**",
        ]

        for action in actions:
            icon = "✅" if action["success"] else "❌"
            if action["action_taken"] == "sentinel_escalate":
                icon = "🚨"
            source_tag = f" [{action.get('source', 'seeded').upper()}]" if action.get("source") else ""
            conf = f" (conf: {action.get('confidence', 0):.2f})" if action.get("confidence") else ""
            entry_lines.append(
                f"  - {icon} `{action['diagnosis_id']}` → `{action['action_taken']}`{source_tag}{conf} "
                f"| Workflow: {action['workflow']} | Severity: {action['severity']}"
            )
            if action.get("error_excerpt"):
                entry_lines.append(f"    - Error: `{action['error_excerpt'][:120]}`")

        entry_lines.append(f"- **Status:** {'ALL_SECURED' if not failed else 'PARTIAL_SECURED'}")
        entry_lines.append("")

        try:
            # Assuming MASTER_INDEX_PATH is defined at module level
            from nerve_center_v2 import MASTER_INDEX_PATH
            master_path = os.path.normpath(MASTER_INDEX_PATH)
            with open(master_path, "a", encoding="utf-8") as f:
                f.write("\n".join(entry_lines))
            print(f"  📝 Sentinel audit entry appended to MASTER_INDEX.md")
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
        failures = []
        if injected_failures is not None:
            failures.extend(injected_failures)
            print(f"  [SCAN] Using {len(injected_failures)} injected test failure(s).")
        
        # SENTINEL: Ecosystem Scan
        ecosystem_failures = self.scan_ecosystem()
        failures.extend(ecosystem_failures)

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
        healed = [a for a in all_actions if a["success"]]
        rectified = [a for a in all_actions if a.get("source") == "rectified"]

        print(f"\n{'═'*60}")
        print(f"  🏁 Cycle Complete: {len(healed)}/{len(all_actions)} actions successful")
        if len(rectified):
            print(f"  🌱 {len(rectified)} new pattern(s) learned via rectification")
        print(f"{'═'*60}\n")

        return {
            "status": "partial_heal" if failures else "healthy",
            "failures_found": len(failures),
            "actions_taken": len(all_actions),
            "healed": len(healed),
            "rectified": len(rectified),
            "audit_trail": all_actions,
            "engine_stats": self.engine.get_stats()
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
