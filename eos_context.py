"""
eos_context.py — Enterprise Operating System Context Store
═══════════════════════════════════════════════════════════
Meta App Factory V3.1 | Antigravity-AI

Singleton state store for cross-document consistency.
Persists brand identity, market data, and financial figures to disk so
every generated document (XLSX, PPTX, MD, code) uses the same source of truth.
"""

import os
import json
import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any

logger = logging.getLogger("EOSContext")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

_DEFAULT_STATE: dict = {
    # ── Identity ─────────────────────────────────────────
    "session_id": None,
    "mode": None,          # "technical" | "venture"
    "created_at": None,
    "last_updated": None,

    # ── Company ───────────────────────────────────────────
    "company_name": None,
    "tagline": None,
    "one_liner": None,
    "industry": None,
    "target_market": None,
    "problem_statement": None,
    "solution_statement": None,

    # ── Brand ─────────────────────────────────────────────
    "brand_name": None,
    "brand_colors": {},      # {"primary": "#hex", "secondary": "#hex", ...}
    "brand_fonts": {},       # {"heading": "Inter", "body": "Roboto"}
    "brand_tone": None,
    "logo_prompt": None,
    "logo_path": None,

    # ── Market Intelligence ───────────────────────────────
    "tam": None,             # Total Addressable Market ($)
    "sam": None,             # Serviceable Addressable Market ($)
    "som": None,             # Serviceable Obtainable Market ($)
    "competitors": [],       # [{"name": str, "weakness": str}, ...]
    "market_strategy": None,

    # ── Financial Model ───────────────────────────────────
    "monthly_revenue": None,
    "growth_rate": None,
    "fixed_costs": None,
    "variable_cost_per_unit": None,
    "equity_contribution": None,     # User's own investment
    "total_investment_needed": None,
    "funding_gap": None,             # total_needed - equity
    "breakeven_month": None,
    "y1_revenue_projected": None,
    "gross_margin_pct": None,

    # ── Funding Strategy ──────────────────────────────────
    "bank_loan_amount": None,
    "vc_raise_amount": None,
    "equity_to_give": None,         # % equity offered to VC
    "funding_strategy_md": None,

    # ── Deliverables ─────────────────────────────────────
    "financial_xlsx_path": None,
    "investor_pptx_path": None,
    "customer_pptx_path": None,
    "business_plan_md_path": None,
    "pitch_deck_json_path": None,
    "legal_analysis": None,           # Copyright/Trademark viability

    # ── Iterative Workflow State ──────────────────────────
    "phase_status": {
        "market": "pending",      # pending | iterating | locked | deadlocked
        "brand": "pending",
        "legal": "pending",
        "financials": "pending",
        "funding": "pending",
        "pitch": "pending",
        "business_plan": "pending"
    },
    "phase_iterations": {
        "market": 0, "brand": 0, "legal": 0, "financials": 0, "funding": 0, "pitch": 0, "business_plan": 0
    },
    "phase_critique": {
        "market": "", "brand": "", "legal": "", "financials": "", "funding": "", "pitch": "", "business_plan": ""
    },

    # ── Phases Completed ──────────────────────────────────
    "phases_completed": [],    # legacy tracker
}


class EOSContext:
    """Thread-safe EOS state store with per-project disk persistence."""

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.project_dir = os.path.join(SCRIPT_DIR, "projects", self.project_name)
        os.makedirs(self.project_dir, exist_ok=True)
        self.state_path = os.path.join(self.project_dir, "eos_state.json")
        
        self._state = dict(_DEFAULT_STATE)
        self._state["company_name"] = self.project_name
        self._state_lock = Lock()
        self._load()

    # ── Persistence ──────────────────────────────────────

    def _load(self):
        try:
            if os.path.exists(self.state_path):
                with open(self.state_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._state.update(saved)
                logger.info(f"EOS state loaded for '{self.project_name}'")
        except Exception as e:
            logger.warning(f"EOS state load failed for '{self.project_name}': {e}")

    def save(self):
        with self._state_lock:
            try:
                self._state["last_updated"] = datetime.now(timezone.utc).isoformat()
                with open(self.state_path, "w", encoding="utf-8") as f:
                    json.dump(self._state, f, indent=2, default=str)
            except Exception as e:
                logger.warning(f"EOS state save failed for '{self.project_name}': {e}")

    # ── Access ────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        with self._state_lock:
            return self._state.get(key, default)

    def set(self, key: str, value: Any):
        with self._state_lock:
            self._state[key] = value
        self.save()

    def update(self, data: dict):
        with self._state_lock:
            self._state.update(data)
        self.save()

    def to_dict(self) -> dict:
        with self._state_lock:
            return dict(self._state)

    def reset(self):
        with self._state_lock:
            self._state = dict(_DEFAULT_STATE)
            self._state["created_at"] = datetime.now(timezone.utc).isoformat()
        self.save()
        logger.info("EOS context reset")

    def mark_phase_complete(self, phase: str):
        with self._state_lock:
            phases = self._state.get("phases_completed", [])
            if phase not in phases:
                phases.append(phase)
            self._state["phases_completed"] = phases
        self.save()

    def is_phase_complete(self, phase: str) -> bool:
        return phase in self._state.get("phases_completed", [])

    # ── Workflow State Methods ────────────────────────────

    def start_iteration(self, phase: str) -> int:
        """Mark phase as iterating and increment count. Returns the new count."""
        with self._state_lock:
            self._state["phase_status"][phase] = "iterating"
            self._state["phase_iterations"][phase] += 1
            count = self._state["phase_iterations"][phase]
            if count > 3:
                self._state["phase_status"][phase] = "deadlocked"
            return count

    def set_critique(self, phase: str, critique: str):
        """Save the CRITIC's latest objections for the specialized agent to use."""
        with self._state_lock:
            self._state["phase_critique"][phase] = critique
        self.save()

    def get_critique(self, phase: str) -> str:
        with self._state_lock:
            return self._state["phase_critique"].get(phase, "")

    def lock_phase(self, phase: str):
        with self._state_lock:
            self._state["phase_status"][phase] = "locked"
            self.mark_phase_complete(phase)
        self.save()

    def all_phases_locked(self) -> bool:
        """Check if core startup phases are locked."""
        with self._state_lock:
            st = self._state["phase_status"]
            return (
                st.get("market") == "locked" and
                st.get("brand") == "locked" and
                st.get("legal") == "locked" and
                st.get("financials") == "locked"
            )

    # ── Computed Properties ───────────────────────────────

    def compute_funding_gap(self) -> float | None:
        total = self._state.get("total_investment_needed")
        equity = self._state.get("equity_contribution")
        if total is not None and equity is not None:
            gap = float(total) - float(equity)
            self.set("funding_gap", gap)
            return gap
        return None

    def get_financial_config(self) -> dict:
        """Return config dict ready for FinancialArchitect.generate_projections()."""
        s = self._state
        return {
            "company_name": s.get("company_name") or "Startup",
            "monthly_revenue": s.get("monthly_revenue") or 50000.0,
            "growth_rate": s.get("growth_rate") or 0.08,
            "fixed_costs": s.get("fixed_costs") or 20000.0,
            "investment": s.get("total_investment_needed") or 100000.0,
            "agents": 4,
            "cost_per_agent": 50.0,
        }

    def get_brand_context_str(self) -> str:
        """Return a compact string of brand/financial context for LLM injection."""
        s = self._state
        parts = []
        if s.get("company_name"):
            parts.append(f"Company: {s['company_name']} — {s.get('tagline', '')}")
        if s.get("tam"):
            parts.append(f"Market: TAM={s['tam']} | SAM={s['sam']} | SOM={s['som']}")
        if s.get("monthly_revenue"):
            parts.append(f"Financials: Rev={s['monthly_revenue']}/mo | Growth={s.get('growth_rate','?')}/mo")
        if s.get("brand_colors"):
            colors = ", ".join(f"{k}={v}" for k, v in s["brand_colors"].items())
            parts.append(f"Brand Colors: {colors}")
        return "\n".join(parts)


# ── Module-level singleton factory ───────────────────────────────
_instances: dict[str, EOSContext] = {}
_factory_lock = Lock()


def get_eos(project_name: str = "Aether") -> EOSContext:
    """Return the EOS context for a specific project, creating it if needed."""
    if project_name not in _instances:
        with _factory_lock:
            if project_name not in _instances:
                _instances[project_name] = EOSContext(project_name)
                logger.info(f"EOSContext created for project: {project_name}")
    return _instances[project_name]
