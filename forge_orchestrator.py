import os
import time
import requests
import logging
from typing import Optional, List, Dict, Any

from forge_rollback_manager import ForgeRollbackManager
from qa_architect import QAArchitect
import model_router

logger = logging.getLogger("ForgeOrchestrator")
logging.basicConfig(level=logging.INFO)

FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))
# Note: Ghost Operator is assumed to be running on port 5100
OPERATOR_URL = "http://localhost:5100"

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

    def execute_staging_cycle(self, staging_filename: str) -> Dict[str, Any]:
        """
        Invokes QA Architect on a staging file after it has been safely written.
        Returns the execution result dict.
        """
        logger.info(f"[ForgeOrchestrator] Beginning staging cycle for {staging_filename}")
        
        # In a real environment, we ensure the file is closed.
        # Direct programmatic execution to QA Architect:
        result = self.qa.execute_staging_script(staging_filename)
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
