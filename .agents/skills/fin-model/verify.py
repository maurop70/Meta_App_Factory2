"""
verify.py — fin-model recalculation & tie-out gate (MAF skill: fin-model)
═════════════════════════════════════════════════════════════════════════
Recalculates a built workbook with a real engine (the pure-Python `formulas`
evaluator) and enforces the HARD ship gate:

  1. ZERO formula errors anywhere: #REF! / #DIV/0! / #VALUE! / #NAME? / #N/A / #NUM!.
  2. Sensitivity centre cell ties out to the P&L EBITDA of the target year (≈0).
  3. Base scenario ties out to the P&L base model (≈0).
  4. Live P&L EBITDA / Revenue recalculate to the Python shadow model
     ("does the centre sensitivity cell equal the P&L's EBITDA? It must").

`run_full_check(build_result)` returns a structured report; `passed` is the gate.
"""

from __future__ import annotations

import logging
import warnings

logging.getLogger("formulas").setLevel(logging.ERROR)
logging.getLogger("schedula").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

EXCEL_ERRORS = ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NUM!", "#NULL!")


def _scalar(rng):
    """Extract a scalar from a `formulas` Range / numpy array result."""
    v = getattr(rng, "value", rng)
    try:
        # numpy array → first element
        return v[0, 0]
    except (TypeError, IndexError):
        try:
            return v[0]
        except (TypeError, IndexError, KeyError):
            return v


def _normalize(sol: dict) -> dict:
    """Map formulas keys ("'[file]SHEET'!A1") → {"SHEET!A1": value} (sheet upper-cased)."""
    out = {}
    for k, rng in sol.items():
        key = k
        if "]" in key:
            key = key.split("]", 1)[1]      # drop "'[file"
        key = key.replace("'", "")           # drop quotes around sheet
        if "!" not in key:
            continue
        sheet, addr = key.split("!", 1)
        out[f"{sheet.upper()}!{addr.upper()}"] = _scalar(rng)
    return out


def recalculate(xlsx_path: str):
    import formulas
    xl = formulas.ExcelModel().loads(xlsx_path).finish()
    sol = xl.calculate()
    return _normalize(sol)


def scan_errors(cells: dict) -> list:
    errs = []
    for key, val in cells.items():
        s = str(val)
        if any(e in s for e in EXCEL_ERRORS):
            errs.append({"cell": key, "value": s})
    return errs


def run_full_check(build_result: dict, tol: float = 1.0) -> dict:
    """tol = absolute $ tolerance for tie-outs / shadow comparison (rounding-safe)."""
    path = build_result["xlsx_path"]
    vt = build_result["verify_targets"]
    cells = recalculate(path)

    errors = scan_errors(cells)

    def get(sheet_addr):
        return cells.get(sheet_addr.upper())

    # tie-out cells (must be ~0)
    tie = get(vt["tieout_cell"])
    scen_tie = get(vt["scenario_tieout_cell"])
    tie_ok = tie is not None and abs(float(tie)) <= tol
    scen_ok = scen_tie is not None and abs(float(scen_tie)) <= tol

    # P&L EBITDA / Revenue vs Python shadow
    yr = vt["years"]
    from openpyxl.utils import get_column_letter
    ebitda_live, rev_live = [], []
    ebitda_match, rev_match = True, True
    for y in range(yr):
        col = get_column_letter(2 + y)
        e = get(f"{vt['pnl_sheet']}!{col}{vt['pnl_ebitda_row']}")
        rv = get(f"{vt['pnl_sheet']}!{col}{vt['pnl_revenue_row']}")
        e = float(e) if e is not None else None
        rv = float(rv) if rv is not None else None
        ebitda_live.append(e)
        rev_live.append(rv)
        if e is None or abs(e - vt["expected_ebitda"][y]) > tol:
            ebitda_match = False
        if rv is None or abs(rv - vt["expected_revenue"][y]) > tol:
            rev_match = False

    passed = (len(errors) == 0 and tie_ok and scen_ok and ebitda_match and rev_match)
    return {
        "passed": passed,
        "formula_error_count": len(errors),
        "formula_errors": errors[:50],
        "sensitivity_tieout": {"cell": vt["tieout_cell"], "value": tie, "ok": tie_ok},
        "scenario_tieout": {"cell": vt["scenario_tieout_cell"], "value": scen_tie, "ok": scen_ok},
        "ebitda_live": ebitda_live,
        "ebitda_expected": vt["expected_ebitda"],
        "ebitda_match": ebitda_match,
        "revenue_match": rev_match,
        "cells_evaluated": len(cells),
    }
