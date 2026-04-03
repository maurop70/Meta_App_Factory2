"""
coo_agent.py — Phase 4: Chief Operating Officer
══════════════════════════════════════════════════
Monitors and regulates resource consumption (tokens/budget) across War Room iterations.
Prevents infinite debate loops and tracks the true operational cost of Meta App Factory sessions.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel

logger = logging.getLogger("COO_Agent")

class OpBudgetExceeded(Exception):
    pass

class ProjectLedger(BaseModel):
    project_id: str
    tokens_in: int = 0
    tokens_out: int = 0
    max_budget: int = 100000
    iteration_count: int = 0
    status: str = "active"
    last_updated: str = ""

    @property
    def total_tokens(self) -> int:
        return self.tokens_in + self.tokens_out

    @property
    def estimated_cost_usd(self) -> float:
        # Approximate Gemini 2.5 Flash Pricing
        # Input: ~$0.075 / 1M tokens
        # Output: ~$0.30 / 1M tokens
        in_cost = (self.tokens_in / 1_000_000) * 0.075
        out_cost = (self.tokens_out / 1_000_000) * 0.30
        return in_cost + out_cost

class COOManager:
    def __init__(self):
        self._ledgers: Dict[str, ProjectLedger] = {}
        # Simple character-based token approximation (1 token ~= 4 chars)
        self._chars_per_token = 4.0

    def get_ledger(self, project_id: str) -> ProjectLedger:
        if project_id not in self._ledgers:
            self._ledgers[project_id] = ProjectLedger(
                project_id=project_id,
                last_updated=datetime.now().isoformat()
            )
        return self._ledgers[project_id]

    def reset_ledger(self, project_id: str):
        self._ledgers[project_id] = ProjectLedger(
            project_id=project_id,
            last_updated=datetime.now().isoformat()
        )
        return self._ledgers[project_id]

    def restore_ledger(self, project_id: str, tokens_in: int, tokens_out: int, iteration_count: int = 0) -> ProjectLedger:
        """Phase 8: Manually rehydrate RAM ledger from a saved checkpoint."""
        if project_id not in self._ledgers:
            self._ledgers[project_id] = ProjectLedger(project_id=project_id)
            
        ledger = self._ledgers[project_id]
        ledger.tokens_in = tokens_in
        ledger.tokens_out = tokens_out
        ledger.iteration_count = iteration_count
        ledger.status = "active"
        if ledger.total_tokens >= ledger.max_budget:
            ledger.status = "halted"
            
        ledger.last_updated = datetime.now().isoformat()
        logger.info(f"[COO] Ledger re-hydrated for {project_id}: {ledger.total_tokens} total tokens.")
        return ledger

    def estimate_tokens(self, text: str) -> int:
        return int(len(text) / self._chars_per_token)

    def record_usage(self, project_id: str, agent_name: str, prompt: str, response: str) -> ProjectLedger:
        """Record usage based on string inputs/outputs, converting length to approximate tokens."""
        ledger = self.get_ledger(project_id)
        
        if ledger.status == "halted":
            raise OpBudgetExceeded(f"Project '{project_id}' is halted. Maximum budget of {ledger.max_budget} exceeded.")

        t_in = self.estimate_tokens(prompt)
        t_out = self.estimate_tokens(response)

        ledger.tokens_in += t_in
        ledger.tokens_out += t_out
        ledger.last_updated = datetime.now().isoformat()

        logger.info(f"[COO] {agent_name} consumed {t_in} IN / {t_out} OUT tokens. Total: {ledger.total_tokens}/{ledger.max_budget}")

        if ledger.total_tokens >= ledger.max_budget:
            ledger.status = "halted"
            logger.error(f"[COO] HALT TRIGGERED: Project '{project_id}' exceeded {ledger.max_budget} token limit.")
            raise OpBudgetExceeded(f"Project '{project_id}' exceeded {ledger.max_budget} limit.")
            
        return ledger

    def record_iteration(self, project_id: str):
        ledger = self.get_ledger(project_id)
        ledger.iteration_count += 1
        ledger.last_updated = datetime.now().isoformat()

# Singleton
_coo_instance = COOManager()

def get_coo() -> COOManager:
    return _coo_instance
