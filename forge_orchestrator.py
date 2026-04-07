import os
import time
import requests
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from forge_rollback_manager import ForgeRollbackManager
from qa_architect import QAArchitect
import model_router

logger = logging.getLogger("ForgeOrchestrator")
logging.basicConfig(level=logging.INFO)

FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))
# Note: Ghost Operator is assumed to be running on port 5100
OPERATOR_URL = "http://localhost:5100"
# QA telemetry ingest — Phantom QA Elite SSE bridge
QA_INGEST_URL = "http://localhost:5030/api/qa/ingest"


def _push_forge_event(agent: str, message: str, status: str,
                      filename: str = None, attempt: int = None):
    """Fire-and-forget QA telemetry push. Never blocks the forge loop."""
    payload = {
        "agent":     agent,
        "message":   message,
        "status":    status,
        "timestamp": datetime.now().isoformat(),
    }
    if filename is not None:
        payload["filename"] = filename
    if attempt is not None:
        payload["attempt"] = attempt
    try:
        requests.post(QA_INGEST_URL, json=payload, timeout=2)
    except Exception:
        pass  # telemetry never blocks the forge



class ExecutiveForkTriggered(Exception):
    """Raised when an ambiguous architectural choice halts the autonomous loop."""
    pass

class ForgeOrchestrator:
    """
    The orchestrator managing the CI/CD development loop.
    Controls the interaction between Developer scripts, QA Architect testing,
    Executive Forks, and Rollback Version Control.
    """
    
    def __init__(self):
        self.qa = QAArchitect(timeout_seconds=15)
        self.rollback = ForgeRollbackManager()
        
    def _broadcast_phase(self, phase: str, status: str, project: str = "AntigravityWorkspace_Q3"):
        """
        Posts a state_machine event to the main api.py SSE endpoint.
        This drives the WarRoom.jsx 1-5 progress bar.
        """
        try:
            requests.post(
                "http://localhost:5000/api/warroom/intervene",
                json={
                    "message": f"[state_machine] phase={phase} status={status}",
                    "project_name": project,
                    "event_type": "state_machine",
                    "phase": phase,
                    "status": status
                },
                timeout=5
            )
        except Exception as e:
            logger.warning(f"[ForgeOrchestrator] Phase broadcast failed: {e}")

    def run_incubator_gate(self, app_idea: str, project: str = "AntigravityWorkspace_Q3"):
        """
        The Incubator Gate (Pre-Flight Intelligence)
        Routes the prompt to CMO for Market Recon, then to CTO for Technical Blueprint.
        Halts the orchestrator via an Executive Fork asking for @Operator authorization.
        Broadcasts state_machine events to drive the War Room 1-5 progress bar.
        """
        logger.info(f"[ForgeOrchestrator] Initiating Incubator Gate for: {app_idea}")

        # 1. Market Recon (CMO) — drive progress bar step 1
        self._broadcast_phase("CMO_STRATEGY", "ACTIVE", project)
        cmo_prompt = f"Analyze existing market competitors and define a superior 'Blue Ocean' feature set for: {app_idea}"
        cmo_recon = model_router.route("CMO", cmo_prompt)
        logger.info("[ForgeOrchestrator] CMO Market Recon retrieved.")
        self._broadcast_phase("CMO_STRATEGY", "DONE", project)

        # 2. Technical Blueprint (CTO) — drive progress bar step 2
        self._broadcast_phase("CTO_FEASIBILITY", "ACTIVE", project)
        cto_prompt = (
            f"Draft a native Python architecture specifically designed to beat the competitors "
            f"identified in this market recon:\n\n{cmo_recon}\n\nApp Idea: {app_idea}"
        )
        cto_blueprint = model_router.route("CTO", cto_prompt)
        logger.info("[ForgeOrchestrator] CTO Technical Blueprint retrieved.")
        self._broadcast_phase("CTO_FEASIBILITY", "DONE", project)

        # 3. The Executive Gate — drive progress bar step 3 (awaiting)
        self._broadcast_phase("CFO_FINANCIAL_MODEL", "WAITING", project)
        context = (
            f"=== PRE-FLIGHT INTELLIGENCE ===\n\n"
            f"[CMO MARKET RECON]\n{cmo_recon}\n\n"
            f"[CTO BLUEPRINT]\n{cto_blueprint}\n\n"
            f"[SYSTEM] Awaiting @Operator approval to enter /staging_environment/."
        )

        # This will raise ExecutiveForkTriggered and pause the pipeline while pinging the UI
        self.trigger_executive_fork(
            context=context,
            options=["@Operator Approve Build", "@Operator Reject Blueprint"],
            project=project
        )

    def execute_staging_cycle(self, staging_filename: str,
                               max_heal_attempts: int = 3) -> Dict[str, Any]:
        """
        Invokes QA Architect on a staging file after it has been safely written.
        On FAIL, triggers the CTO Auto-Heal rewrite loop (up to max_heal_attempts).
        Every attempt + verdict is broadcast to the Ghost Stream SSE feed.
        Returns the final execution result dict.
        """
        logger.info(f"[ForgeOrchestrator] Beginning staging cycle for {staging_filename}")

        _push_forge_event(
            "FORGE_ORCHESTRATOR",
            f"Staging cycle initiated: {staging_filename}",
            "RUNNING",
            filename=staging_filename,
        )

        staging_path = os.path.join(FACTORY_DIR, "staging_environment", staging_filename)

        for attempt in range(1, max_heal_attempts + 1):
            result = self.qa.execute_staging_script(staging_filename, attempt=attempt)

            if result["status"] == "pass":
                _push_forge_event(
                    "FORGE_ORCHESTRATOR",
                    f"✅ Staging cycle COMPLETE — {staging_filename} passed on attempt {attempt}.",
                    "HEAL_PASS" if attempt > 1 else "PASS",
                    filename=staging_filename,
                    attempt=attempt,
                )
                return result

            # Non-pass statuses that the CTO cannot fix (security / missing file)
            if result["status"] in ("security_block", "error") and "File not found" in result.get("error", ""):
                _push_forge_event(
                    "FORGE_ORCHESTRATOR",
                    f"🛑 Staging cycle BLOCKED — {result['status']}. Auto-Heal aborted.",
                    "FAIL",
                    filename=staging_filename,
                )
                return result

            # ── Auto-Heal: ask CTO to rewrite the failed script ──────────
            if attempt < max_heal_attempts:
                err_summary = result.get("stderr", "")[:500] or result.get("error", "Unknown error")
                _push_forge_event(
                    "CTO_AGENT",
                    f"🔧 HEAL_ATTEMPT {attempt}/{max_heal_attempts - 1} — Rewriting {staging_filename}. "
                    f"Error: {err_summary[:120]}",
                    "HEAL_ATTEMPT",
                    filename=staging_filename,
                    attempt=attempt,
                )

                heal_prompt = (
                    f"You are the CTO Auto-Heal Agent. A sandboxed Python script failed QA.\n\n"
                    f"Script: {staging_filename}\n"
                    f"Failure reason:\n{err_summary}\n\n"
                    f"Read the script, identify the bug, and return ONLY the corrected, "
                    f"complete Python source. No explanation, no markdown — raw Python only."
                )
                try:
                    # Read current source to include in context
                    with open(staging_path, "r", encoding="utf-8") as f:
                        current_source = f.read()
                    heal_prompt = (
                        f"{heal_prompt}\n\nCurrent source:\n```python\n{current_source[:3000]}\n```"
                    )
                except Exception:
                    pass

                try:
                    healed_code = model_router.route("CTO", heal_prompt)
                    # Strip accidental markdown fences
                    if "```" in healed_code:
                        lines = healed_code.splitlines()
                        healed_code = "\n".join(
                            l for l in lines
                            if not l.strip().startswith("```")
                        )
                    self.rollback.create_backup(staging_path)  # snapshot before overwrite
                    with open(staging_path, "w", encoding="utf-8") as f:
                        f.write(healed_code)
                    logger.info(f"[ForgeOrchestrator] CTO healed {staging_filename} (attempt {attempt}).")
                except Exception as heal_err:
                    _push_forge_event(
                        "CTO_AGENT",
                        f"❌ HEAL_FAIL — CTO rewrite failed: {heal_err}",
                        "HEAL_FAIL",
                        filename=staging_filename,
                        attempt=attempt,
                    )
                    return result  # give up — can't write the heal
            else:
                # Final attempt exhausted
                _push_forge_event(
                    "FORGE_ORCHESTRATOR",
                    f"❌ Auto-Heal EXHAUSTED after {max_heal_attempts} attempts. {staging_filename} remains FAIL.",
                    "HEAL_FAIL",
                    filename=staging_filename,
                    attempt=attempt,
                )

        return result


    def trigger_executive_fork(self, context: str, options: List[str], project: str = "AntigravityWorkspace_Q3"):
        """
        Halts the autonomous loop and broadcasts the Pre-Flight Intelligence summary
        directly to the War Room UI feed via the intervene endpoint.
        Requires the User to provide an executive directive to proceed.
        """
        logger.warning(f"[ForgeOrchestrator] EXECUTIVE FORK TRIGGERED. Awaiting human directive.")

        # Broadcast the full CMO+CTO brief directly into the War Room dialogue feed
        fork_message = (
            f"⚡ **EXECUTIVE FORK — @Operator Authorization Required**\n\n"
            f"{context}\n\n"
            f"**Options:** {' | '.join(options)}"
        )
        try:
            requests.post(
                "http://localhost:5000/api/warroom/intervene",
                json={
                    "message": fork_message,
                    "project_name": project,
                    "agent": "INCUBATOR_GATE"
                },
                timeout=10
            )
            logger.info("[ForgeOrchestrator] Executive Fork broadcast to War Room feed.")
        except Exception as e:
            logger.error(f"[ForgeOrchestrator] Failed to broadcast Executive Fork: {e}")

        # Also attempt to ping the Ghost Operator on port 5100 if it's alive
        payload = {"options": options, "context": context}
        try:
            r = requests.post(f"{OPERATOR_URL}/api/operator/executive-fork", json=payload, timeout=5)
            if r.status_code == 200:
                logger.info("[ForgeOrchestrator] Ghost Operator pinged successfully.")
        except Exception as e:
            logger.warning(f"[ForgeOrchestrator] Ghost Operator not reachable on 5100 (non-fatal): {e}")

        raise ExecutiveForkTriggered("Execution halted awaiting executive directive from War Room UI.")

    def merge_to_live(self, staging_file_path: str, live_file_path: str) -> bool:
        """
        Safely merges verified code to the live environment by taking a timestamped
        backup first, then copying the code over.
        """
        if not os.path.exists(staging_file_path):
            logger.error("[ForgeOrchestrator] Cannot merge; staging file missing.")
            return False
            
        logger.info(f"[ForgeOrchestrator] Initiating safe merge for {staging_file_path} -> {live_file_path}")
        
        # 1. Take snapshot backup of live target
        if os.path.exists(live_file_path):
            try:
                self.rollback.create_backup(live_file_path)
            except Exception as e:
                logger.error(f"[ForgeOrchestrator] Merge aborted. Backup failed: {e}")
                return False
                
        # 2. Perform merge
        try:
            import shutil
            shutil.copy2(staging_file_path, live_file_path)
            logger.info(f"[ForgeOrchestrator] Merge completed to {live_file_path}.")
            
            # Optional: clear staging file after successful merge
            os.remove(staging_file_path)
            return True
        except Exception as e:
            logger.error(f"[ForgeOrchestrator] File operation failed during merge: {e}")
            return False

if __name__ == "__main__":
    orchestrator = ForgeOrchestrator()
    logger.info("ForgeOrchestrator stands ready.")
