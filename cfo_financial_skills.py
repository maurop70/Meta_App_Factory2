"""
cfo_financial_skills.py — CFO Agent ⇄ fin-model / fin-model-presentation binding
════════════════════════════════════════════════════════════════════════════════
Meta App Factory | Native Python Ecosystem

Binds the two financial skills to the CFO Agent so it can, during C-Suite
boardroom deliberations, build a live formula-driven model and package it for the
board — chained, in that order:

    fin-model  →  build_and_verify()         (live workbook + recalc gate)
    fin-model-presentation  →  present()     (native charts + board PDF)

This is an ADDITIVE capability: it does not touch the CFO Agent's existing
`synthesize()` persona, prompts, or memory. The skills supply the *how* (model
construction + presentation); the agent supplies the *judgment*.

Standalone-safe: the skills also run directly (see each SKILL.md). Binding here
is purely additive.
"""

from __future__ import annotations

import os
import re
import sys
import time

_FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_skills_root() -> str:
    """Find the .agents/skills tree across layouts so the binding works both in the
    dev checkout (skills are a sibling-parent of the repo) and after a fresh clone
    (skills are vendored inside the repo). Override with env MAF_SKILLS_ROOT."""
    candidates = [
        os.environ.get("MAF_SKILLS_ROOT"),
        os.path.join(_FACTORY_DIR, "..", ".agents", "skills"),   # dev sibling layout
        os.path.join(_FACTORY_DIR, ".agents", "skills"),         # vendored in-repo
    ]
    for c in candidates:
        if c and os.path.isdir(os.path.join(c, "fin-model")):
            return os.path.abspath(c)
    # default to the dev sibling location even if missing (clear error downstream)
    return os.path.abspath(os.path.join(_FACTORY_DIR, "..", ".agents", "skills"))


_SKILLS_ROOT = _resolve_skills_root()
_FIN_MODEL_DIR = os.path.join(_SKILLS_ROOT, "fin-model")
_FIN_PRES_DIR = os.path.join(_SKILLS_ROOT, "fin-model-presentation")

# Intents on which the CFO Agent should reach for the financial skills.
_MODEL_INTENT = re.compile(
    r"\b(financial model|build (?:a|the|me)?\s*model|update (?:the )?model|projection|"
    r"\d+[- ]?year|five[- ]?year|unit economics|p\s*&\s*l|p and l|profit and loss|"
    r"income statement|budget|break[- ]?even|sensitivity|scenario|tornado|"
    r"bear/base/bull|fundrais|how much (?:do|to|should).{0,20}raise|peak funding|"
    r"runway|board pack|investor pack|cfo review)\b",
    re.IGNORECASE,
)


def detect_model_intent(text: str) -> bool:
    """True if the request is one the CFO Agent should satisfy by building a model."""
    return bool(text and _MODEL_INTENT.search(text))


def load_skills():
    """Put the two skill dirs on sys.path and import their entrypoints.
    Returns (build_and_verify, present, paths) where paths proves which files were
    actually bound (used in the live call trace)."""
    for d in (_FIN_MODEL_DIR, _FIN_PRES_DIR):
        if d not in sys.path:
            sys.path.insert(0, d)
    import fin_model as _fm                      # noqa: E402
    import fin_model_presentation as _fp         # noqa: E402
    paths = {"fin_model": os.path.abspath(_fm.__file__),
             "fin_model_presentation": os.path.abspath(_fp.__file__)}
    return _fm.build_and_verify, _fp.present, paths


def _artifact_dir(project_id: str) -> str:
    safe = "".join(c for c in (project_id or "cfo_model") if c.isalnum() or c in (" ", "_", "-")).strip() or "cfo_model"
    path = os.path.join(_FACTORY_DIR, "projects", safe, "artifacts", "cfo_reports")
    os.makedirs(path, exist_ok=True)
    return path


def executive_summary_text(summary: dict) -> str:
    """A short, quotable headline the CFO Agent can speak back to the user."""
    infl = summary.get("ebitda_inflection_year")
    infl_s = f"Year {infl}" if infl else "not within the horizon"
    pf = summary.get("peak_funding_requirement")
    sr = summary.get("scenario_range") or [None, None]
    be = summary.get("break_even_units_per_month")
    parts = [
        f"{summary.get('product_name', 'The venture')}: gross margin {summary.get('gross_margin_pct')}%.",
        f"EBITDA turns positive in {infl_s}.",
        f"Peak funding requirement (max capital to raise) is ${pf:,}." if pf is not None else "",
        f"Break-even at {be:,} units/month." if be else "",
        f"Year-end EBITDA ranges ${sr[0]:,} (Bear) to ${sr[1]:,} (Bull)."
        if sr and sr[0] is not None else "",
    ]
    return " ".join(p for p in parts if p)


def build_model_and_pack(assumptions: dict, brand_tokens=None, project_id: str = "cfo_model",
                         present_pack: bool = True) -> dict:
    """Chain fin-model → fin-model-presentation and return the board-ready artifacts
    plus a CFO-quotable executive summary and a call trace proving the binding."""
    trace = []
    t0 = time.time()
    build_and_verify, present, paths = load_skills()
    trace.append({"step": "bind", "detail": "skills imported", "paths": paths,
                  "t_ms": round((time.time() - t0) * 1000)})

    out_dir = _artifact_dir(project_id)
    xlsx_path = os.path.join(out_dir, f"{project_id}_model.xlsx")

    t1 = time.time()
    model = build_and_verify(assumptions, xlsx_path)
    trace.append({"step": "fin-model", "skill": "fin-model.build_and_verify",
                  "status": "passed" if model["verification"]["passed"] else "FAILED",
                  "formula_errors": model["verification"]["formula_error_count"],
                  "xlsx": model["xlsx_path"], "t_ms": round((time.time() - t1) * 1000)})

    result = {
        "status": "success" if model["verification"]["passed"] else "verification_failed",
        "xlsx_path": model["xlsx_path"],
        "verification": model["verification"],
        "executive_summary": model["summary"],
        "executive_summary_text": executive_summary_text(model["summary"]),
        "special_ref_audit": model["special_ref_audit"],
        "bound_skill_paths": paths,
    }

    if present_pack and model["verification"]["passed"]:
        t2 = time.time()
        pdf_path = os.path.join(out_dir, f"{project_id}_board.pdf")
        pres = present(model, brand_tokens=brand_tokens, pdf_path=pdf_path, qa=True)
        trace.append({"step": "fin-model-presentation", "skill": "fin-model-presentation.present",
                      "pdf": pres["pdf_path"], "qa_clean": pres.get("qa", {}).get("clean"),
                      "charts": pres.get("charts"), "t_ms": round((time.time() - t2) * 1000)})
        result["pdf_path"] = pres["pdf_path"]
        result["qa"] = pres.get("qa")
    result["call_trace"] = trace
    result["total_ms"] = round((time.time() - t0) * 1000)
    return result
