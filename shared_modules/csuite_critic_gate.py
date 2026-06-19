"""
csuite_critic_gate.py — Deterministic structural gate for C-Suite venture outputs.
═════════════════════════════════════════════════════════════════════════════════
Enforces the CPG/Venture Validation rules (see .agents/AGENTS.md): the Critic must
reject any C-Suite sub-agent output that lacks the mandated *bottom-up* structures.
Delegation to execution is blocked until every agent passes its gate.

This gate is intentionally DETERMINISTIC and LLM-free so it is fast, free, and
unit-testable offline. The conversational Critic in server.py can call these to
decide whether to sign off or return the work to sender.
"""

from typing import Any


def _nonempty(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, dict, tuple, set)):
        return len(v) > 0
    return bool(v)


def validate_cfo_structures(output: dict) -> dict:
    """CFO must deliver: COGS line items, 5-yr cash flow, CapEx schedule, exported .xlsx."""
    missing = []
    cogs = (output or {}).get("cogs_line_items")
    if not (isinstance(cogs, list) and len(cogs) > 0):
        missing.append("COGS line-item breakdown (raw ingredients, line-time, labor, packaging)")
    if not _nonempty((output or {}).get("cash_flow_5yr")):
        missing.append("5-year cash-flow projection")
    if not _nonempty((output or {}).get("capex_schedule")):
        missing.append("tactical CapEx schedule (amortized equipment/setup)")
    if not _nonempty((output or {}).get("xlsx_path")):
        missing.append("exported .xlsx workbook path")
    return {"agent": "CFO", "passed": not missing, "missing": missing}


def validate_cmo_structures(output: dict) -> dict:
    """CMO must deliver: >=3-competitor matrix (MSRP, $/oz, ingredients, flaws) + line-item budget."""
    missing = []
    comp = (output or {}).get("competitor_matrix")
    if not (isinstance(comp, list) and len(comp) >= 3):
        missing.append("competitor matrix with >=3 competitors")
    else:
        required = ("msrp", "price_per_oz", "key_ingredients", "positioning_flaws")
        for i, c in enumerate(comp):
            for k in required:
                if not _nonempty((c or {}).get(k)):
                    missing.append(f"competitor[{i}] missing '{k}'")
    budget = (output or {}).get("marketing_budget")
    if isinstance(budget, dict):
        items = [k for k, v in budget.items() if _nonempty(v)]
    elif isinstance(budget, list):
        items = [b for b in budget if _nonempty(b)]
    else:
        items = []
    if len(items) < 4:
        missing.append("line-item marketing budget with >=4 categories (demo, paid social, influencer, slotting)")
    return {"agent": "CMO", "passed": not missing, "missing": missing}


def validate_cio_structures(output: dict) -> dict:
    """CIO must deliver: storefront<->3PL<->ERP API specs, cold-chain params, carrier selections."""
    missing = []
    bp = (output or {}).get("ops_blueprint") or {}
    if not _nonempty(bp.get("api_integrations")):
        missing.append("storefront<->3PL<->ERP API integration specs")
    if not _nonempty(bp.get("cold_chain")):
        missing.append("cold-chain temperature controls + spoilage buffer rates")
    if not _nonempty(bp.get("carriers")):
        missing.append("shipping carrier selections with rationale")
    return {"agent": "CIO", "passed": not missing, "missing": missing}


GATE_VALIDATORS = {
    "CFO": validate_cfo_structures,
    "CMO": validate_cmo_structures,
    "CIO": validate_cio_structures,
}


def critic_gate(agent: str, output: dict) -> dict:
    """Run the structural gate for a single agent. Returns {agent, passed, missing}."""
    validator = GATE_VALIDATORS.get((agent or "").upper())
    if not validator:
        return {"agent": agent, "passed": True, "missing": [], "note": "no structural gate for this agent"}
    return validator(output or {})


def critic_signoff(results) -> dict:
    """Aggregate per-agent gate results into a single sign-off verdict.

    `results` is an iterable of dicts from critic_gate(). Sign-off is granted only
    when every agent passed. Otherwise execution/delegation stays blocked.
    """
    results = list(results)
    rejections = [r for r in results if not r.get("passed")]
    return {
        "signed_off": not rejections,
        "rejections": rejections,
        "summary": (
            "Critic SIGN-OFF: all C-Suite structures present."
            if not rejections
            else "Critic REJECTION: missing required bottom-up structures — returned to sender."
        ),
    }
