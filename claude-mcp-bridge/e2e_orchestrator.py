"""
E2E Orchestrator — MAF QA Lab
-------------------------------
Coordinates Inspector + Seed + Playwright agents in sequence.
Manages run state on disk. Streams events to QA Lab UI.
Entry point for all E2E evaluation requests.

Entry points:
  - orchestrator.run(app_name, run_id)       — full pipeline
  - orchestrator.get_app_list()              — registry lookup
  - orchestrator.get_run_status(run_id)      — state query
  - orchestrator.respond_to_escalation(...)  — human escalation response

MCP tool: run_e2e_evaluation
Gemini:   run_e2e_evaluation
Command:  "test <app_name>" in loop_ui.py terminal
"""

import os
import sys
import json
import uuid
import threading
import logging
from datetime import datetime, timezone
from dataclasses import asdict

# ── Path setup ────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))

if BRIDGE_DIR not in sys.path:
    sys.path.insert(0, BRIDGE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

REGISTRY_PATH   = os.path.join(BRIDGE_DIR, "e2e_app_registry.json")
QA_RUNS_DIR     = os.path.join(BASE_DIR, "logs", "qa_runs")
E2E_REPORTS_DIR = os.path.join(BASE_DIR, "logs", "e2e_reports")

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# E2EOrchestrator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class E2EOrchestrator:
    """
    Coordinates Inspector + Seed + Playwright agents.
    Manages run state on disk and streams events to the QA Lab UI.
    """

    # ── Registry ──────────────────────────────────────────────────────────────

    def get_app_list(self) -> list:
        """Return the list of registered apps from e2e_app_registry.json."""
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            return json.load(f)["apps"]

    def _get_app_config(self, app_name: str) -> dict:
        apps = self.get_app_list()
        for app in apps:
            if app["name"] == app_name:
                return app
        raise ValueError(f"App '{app_name}' not found in registry")

    # ── Run state I/O ─────────────────────────────────────────────────────────

    def _read_run(self, run_id: str) -> dict:
        path = os.path.join(QA_RUNS_DIR, f"{run_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _write_run(self, run_id: str, state: dict):
        os.makedirs(QA_RUNS_DIR, exist_ok=True)
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        path = os.path.join(QA_RUNS_DIR, f"{run_id}.json")
        tmp  = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)
        os.replace(tmp, path)

    def _update_run(self, run_id: str, updates: dict):
        """Read–merge–write with a simple retry loop for file-locking safety."""
        import time
        for attempt in range(5):
            try:
                state = self._read_run(run_id) or {}
                state.update(updates)
                self._write_run(run_id, state)
                return
            except Exception as e:
                if attempt == 4:
                    raise
                time.sleep(0.1)

    def _append_event(self, run_id: str, event_type: str, data: dict):
        """Append a structured event to the run's event list on disk."""
        import time
        for attempt in range(5):
            try:
                state  = self._read_run(run_id) or {}
                events = state.get("events", [])
                events.append({
                    "type":      event_type,
                    "data":      data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                state["events"] = events
                self._write_run(run_id, state)
                return
            except Exception as e:
                if attempt == 4:
                    logger.error(f"Failed to append event {event_type}: {e}")
                time.sleep(0.05)

    # ── Event callback (for PlaywrightAgent) ──────────────────────────────────

    def _make_event_callback(self, run_id: str):
        """
        Returns a callback(event_type: str, data: Any) for PlaywrightAgent.
        Updates run counters + appends every event to the event log.
        """
        def callback(event_type: str, data):
            try:
                updates = {}
                safe_data = data if isinstance(data, dict) else {"raw": str(data)}

                if event_type == "test_start":
                    updates["current_test"] = safe_data.get("name", "")

                elif event_type == "test_pass":
                    state = self._read_run(run_id) or {}
                    updates["passed"]       = state.get("passed", 0) + 1
                    results                 = state.get("test_results", [])
                    results.append(safe_data)
                    updates["test_results"] = results

                elif event_type == "test_fail":
                    state = self._read_run(run_id) or {}
                    updates["failed"]       = state.get("failed", 0) + 1
                    results                 = state.get("test_results", [])
                    results.append(safe_data)
                    updates["test_results"] = results

                elif event_type == "fix_cycle_start":
                    updates["status"] = "fixing"
                    updates["cycle"]  = safe_data.get("cycle", 0)

                elif event_type == "fix_cycle_complete":
                    state   = self._read_run(run_id) or {}
                    history = state.get("fix_history", [])
                    history.append(safe_data)
                    updates["fix_history"] = history

                elif event_type == "escalate":
                    updates["status"]    = "escalate"
                    updates["escalation"] = safe_data

                elif event_type == "complete":
                    updates["status"] = "complete"

                if updates:
                    self._update_run(run_id, updates)

                self._append_event(run_id, event_type, safe_data)

            except Exception as e:
                logger.error(f"Event callback error ({event_type}): {e}")

        return callback

    # ── Public helpers ────────────────────────────────────────────────────────

    def respond_to_escalation(self, run_id: str, choice: str) -> bool:
        """Record a human escalation choice (A / B / C) for the run."""
        try:
            self._update_run(run_id, {"escalation_response": choice})
            return True
        except Exception:
            return False

    def get_run_status(self, run_id: str) -> dict:
        """Return the current run state dict, or None if not found."""
        return self._read_run(run_id)

    # ── Main pipeline ─────────────────────────────────────────────────────────

    def run(self, app_name: str, run_id: str) -> object:
        """
        Full E2E evaluation pipeline:
          Phase 1 — InspectorAgent  → TestPlan
          Phase 2 — SeedAgent       → SeedReport
          Phase 3 — PlaywrightAgent → EvaluationReport

        Returns EvaluationReport (or a minimal dict on hard failure).
        Run state is persisted to logs/qa_runs/{run_id}.json throughout.
        Events stream in real-time to the QA Lab UI via the event log.
        """
        os.makedirs(QA_RUNS_DIR, exist_ok=True)
        os.makedirs(E2E_REPORTS_DIR, exist_ok=True)

        # ── Resolve app config ───────────────────────────────────────────────
        try:
            app_config = self._get_app_config(app_name)
        except ValueError as e:
            self._update_run(run_id, {"status": "failed", "error": str(e)})
            raise

        # ── Phase 1: Inspect ─────────────────────────────────────────────────
        self._update_run(run_id, {
            "status":   "inspecting",
            "app_name": app_name,
        })
        self._append_event(run_id, "status_change", {
            "status":  "inspecting",
            "message": "Inspector Agent analyzing code and docs...",
        })

        try:
            from inspector_agent import InspectorAgent
            inspector = InspectorAgent()
            test_plan = inspector.inspect(app_config)

            tc_list = test_plan.test_cases if hasattr(test_plan, "test_cases") else []
            self._update_run(run_id, {
                "total_tests":    len(tc_list),
                "test_plan_path": os.path.join(QA_RUNS_DIR, f"{run_id}_test_plan.json"),
            })
            self._append_event(run_id, "status_change", {
                "status":  "inspecting_complete",
                "message": f"Inspector found {len(tc_list)} test cases",
            })

        except Exception as e:
            logger.error(f"[Orchestrator] Inspector failed: {e}")
            self._update_run(run_id, {"status": "failed", "error": f"Inspector: {e}"})
            raise

        # ── Phase 2: Seed ────────────────────────────────────────────────────
        self._update_run(run_id, {"status": "seeding"})
        self._append_event(run_id, "status_change", {
            "status":  "seeding",
            "message": "Seed Agent preparing test data...",
        })

        try:
            from seed_agent import SeedAgent
            seeder      = SeedAgent()
            seed_report = seeder.seed(app_config, test_plan, run_id)

            # Normalise SeedReport → dict for logging
            if hasattr(seed_report, "tables_seeded"):
                seed_info = {
                    "tables_seeded":    seed_report.tables_seeded,
                    "records_inserted": seed_report.records_inserted,
                }
            elif isinstance(seed_report, dict):
                seed_info = {
                    "tables_seeded":    seed_report.get("tables_seeded", []),
                    "records_inserted": seed_report.get("records_inserted", 0),
                }
            else:
                seed_info = {}

            self._append_event(run_id, "status_change", {
                "status":  "seeding_complete",
                "message": f"Seed complete: {seed_info.get('records_inserted', 0)} records inserted",
                **seed_info,
            })

        except Exception as e:
            logger.warning(f"[Orchestrator] Seed failed (non-fatal): {e}")
            self._append_event(run_id, "status_change", {
                "status":  "seeding_warning",
                "message": f"Seed warning: {e}",
            })
            # Non-fatal — continue to testing

        # ── Phase 3: Test ────────────────────────────────────────────────────
        self._update_run(run_id, {"status": "testing"})
        self._append_event(run_id, "status_change", {
            "status":  "testing",
            "message": "Playwright Agent running tests...",
        })

        try:
            from playwright_agent import PlaywrightAgent
            pw_agent = PlaywrightAgent()
            callback  = self._make_event_callback(run_id)
            report    = pw_agent.run(app_config, test_plan, run_id, callback)

            # Determine final status
            if hasattr(report, "status"):
                final_status = (report.status or "complete").lower()
            elif isinstance(report, dict):
                final_status = report.get("status", "complete").lower()
            else:
                final_status = "complete"

            # Map PlaywrightAgent status values to run state values
            status_map = {
                "ready":    "complete",
                "escalate": "escalate",
                "failed":   "failed",
            }
            run_status = status_map.get(final_status, "complete")
            self._update_run(run_id, {"status": run_status})

        except Exception as e:
            logger.error(f"[Orchestrator] Playwright failed: {e}")
            self._update_run(run_id, {"status": "failed", "error": f"Playwright: {e}"})
            raise

        # ── Save final report ─────────────────────────────────────────────────
        try:
            report_path = os.path.join(E2E_REPORTS_DIR, f"{run_id}_report.json")

            if hasattr(report, "__dict__"):
                report_dict = {k: v for k, v in report.__dict__.items()}
            elif hasattr(report, "_asdict"):
                report_dict = report._asdict()
            elif isinstance(report, dict):
                report_dict = report
            else:
                report_dict = {"raw": str(report)}

            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report_dict, f, indent=2, default=str)

            self._update_run(run_id, {"report_path": report_path})

        except Exception as e:
            logger.warning(f"[Orchestrator] Failed to save report: {e}")

        return report


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# __main__ — quick registry check (no real evaluation)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    orch = E2EOrchestrator()
    apps = orch.get_app_list()
    print(f"Apps registered: {[a['name'] for a in apps]}")
    print("Orchestrator initialized OK")
