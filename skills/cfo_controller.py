"""
cfo_controller.py — Risk Guardian and Local Financial State
═══════════════════════════════════════════════════════════
Replaces the latency-heavy n8n Antigravity_CFO_Execution_Controller.
Manages the native `finance_state.json` config and evaluates the `MAX_BURN` hard boundary.
"""

import os
import json
import uuid
import logging
from datetime import datetime

logger = logging.getLogger("CFOController")

class CFOExecutionController:
    def __init__(self):
        # Locate finance_state.json in the project root
        self.state_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "finance_state.json"
        )
        self._initialize_state()
        
        # Parse MAX_BURN from .env safely
        self.max_burn = 1000000.0  # Safe default of $1,000,000
        env_path = os.path.join(os.path.dirname(self.state_file), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MAX_BURN="):
                        try:
                            self.max_burn = float(line.strip().split("=")[1])
                        except ValueError:
                            pass

    def _initialize_state(self):
        """Creates the state schema if entirely missing to prevent file IO crashes."""
        if not os.path.exists(self.state_file):
            state = {
                "project_budgets": {},
                "current_burn_rate": 0.0,
                "approval_tokens": []
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=4)

    def _load_state(self) -> dict:
        """Reads the deterministic JSON state object."""
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"State load failed: {e}. Defaulting to zero-state.")
            return {"project_budgets": {}, "current_burn_rate": 0.0, "approval_tokens": []}

    def _save_state(self, state: dict):
        """Persists state changes instantly."""
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)

    def commit_budget(self, project_id: str, requested_amount: float) -> dict:
        """
        Attempts to permanently commit a mathematical budget to the global burn rate.
        If exceeding the hard MAX_BURN limit, forcefully rejects it.
        Otherwise, yields a cryptographic "Approval Token" required for execution.
        """
        state = self._load_state()
        
        # Calculate the proposed aggregate burn
        proposed_burn = float(state.get("current_burn_rate", 0.0)) + float(requested_amount)
        
        # The Risk Guardian Boundary
        if proposed_burn > self.max_burn:
            diff = proposed_burn - self.max_burn
            logger.warning(
                f"RISK GUARDIAN BLOCK: {project_id} attempted to commit "
                f"${requested_amount:,.2f}. Exceeds Ecosystem MAX_BURN (${self.max_burn:,.2f}) "
                f"by ${diff:,.2f}."
            )
            return {
                "status": "REJECTED_BY_RISK_GUARDIAN",
                "message": f"Global MAX_BURN exceeded by ${diff:,.2f}. Denied.",
                "token": None
            }
            
        # Hard Commit State Modification
        state["current_burn_rate"] = proposed_burn
        
        if project_id not in state["project_budgets"]:
            state["project_budgets"][project_id] = 0.0
            
        state["project_budgets"][project_id] += float(requested_amount)
        
        # Generate the Cryptographic Check Ticket for the Child App Orchestrators
        approval_token = str(uuid.uuid4())
        token_entry = {
            "token": approval_token,
            "project_id": project_id,
            "committed_amount": requested_amount,
            "timestamp": datetime.now().isoformat()
        }
        
        state["approval_tokens"].append(token_entry)
        
        # Commit to local JSON
        self._save_state(state)
        
        logger.info(
            f"BUDGET COMMITTED: ${requested_amount:,.2f} registered to {project_id}. "
            f"Ecosystem Burn: ${proposed_burn:,.2f} / ${self.max_burn:,.2f}"
        )
        
        return {
            "status": "COMMITTED",
            "message": f"Budget instantly committed. Burn: ${proposed_burn:,.2f} / ${self.max_burn:,.2f}",
            "token": approval_token
        }

if __name__ == "__main__":
    # Internal Unit Testing (Triggered explicitly)
    print("Testing CFO Execution Controller locally...")
    controller = CFOExecutionController()
    
    res1 = controller.commit_budget("Aether_Test", 50000)
    print(f"Pass 1: {res1['status']} - {res1['message']}")
    
    # Intentionally overflow MAX_BURN
    res2 = controller.commit_budget("Aegis_Overflow", 9999999.0)
    print(f"Pass 2: {res2['status']} - {res2['message']}")
