---
name: fin-model
description: Build a live, fully formula-driven Excel financial model that recalculates when inputs change. Use when the deliverable is a spreadsheet financial model, P&L / income statement, 3–5 year projection or operating plan, unit economics, budget, break-even analysis, sensitivity or scenario analysis (Bear/Base/Bull, tornado), or fundraising / "how much do we need to raise" (peak funding) math. Produces an .xlsx with a single Inputs source-of-truth tab and a hard zero-formula-error recalc gate.
---

# fin-model

## Purpose
Generate a **driver-based, single-source-of-truth** Excel model where every number
downstream of the `Inputs` tab is a **live Excel formula**, never a Python-computed
constant. Change an input → the whole model (unit economics, P&L, cash flow,
break-even, sensitivity, tornado, scenarios) recalculates in Excel.

This supersedes the static-value approach in `Core_Framework/cost_accountancy.py`
and `cfo_excel_architect.py` (which write `cell = <number>` via pandas). Those
remain for legacy callers; new model builds should use this skill.

## Trigger
Financial model · P&L · 3–5yr projection · unit economics · budget · break-even ·
sensitivity / scenario (Bear/Base/Bull, tornado) · fundraising / peak-funding math.

## Inputs (assumptions dict)
Single dict; only what you provide is used (sensible defaults fill the rest):
```
product_name, units_per_month, annual_growth_rate, retail_price_per_unit,
raw_materials:[{item, qty_per_unit, unit_cost}], line_time_minutes_per_unit,
line_cost_per_minute, labor_cost_per_unit, packaging_cost_per_unit,
logistics_cost_per_unit, monthly_fixed_opex, capex_items:[{item, cost,
useful_life_years}], tax_rate, nwc_days, num_stores, years (default 5),
scenarios:{bear/base/bull:{volume,price,cogs}}, sensitivity:{target_year,
row_values, col_values}
```

## Outputs
- `xlsx_path` — the workbook. Tab flow: **README → Inputs → Unit Economics → P&L →
  Cash Flow & Break-Even → Sensitivity.**
- `summary` — executive headline: `gross_margin_pct`, `ebitda_by_year`,
  `ebitda_inflection_year`, `peak_funding_requirement`,
  `break_even_units_per_month`, `scenario_ebitda_target_year`, `scenario_range`.
- `verification` — recalc gate report (`passed`, error count, tie-out values).
- `special_ref_audit` — proof that special-character sheet refs are quoted.

## Architecture enforced
- **One `Inputs` tab** holds every assumption; nothing hardcoded downstream.
- **Cell references inside formulas** (`=Inputs!$B$5*(1+Inputs!$B$6)`), never literals.
- **Color coding by role:** blue = input · black = formula · green = cross-sheet link.
- **Number formats:** currency `$#,##0;($#,##0);"-"` (negatives in parens, zeros as
  dashes), rates `0.0%`, multiples `0.0"x"`, years as text. Units in headers.
- **Peak funding = deepest point of cumulative free cash flow** (EBITDA − CapEx −
  ΔNWC − cash tax); cash tax is **NOL-adjusted**; ΔNWC from `nwc_days`.
- **Sensitivity = compact live closed-form formulas** (not fragile Excel Data
  Tables): a 2-way EBITDA grid (volume × COGS), a tornado (±15% one driver,
  sorted into a funnel), and Bear/Base/Bull driven by editable multipliers.

## Hard rules (own trap list — checked, fail loud)
- **Special-character sheet names** (`'P&L'`, `'Cash & Break-Even'`) are ALWAYS
  quoted in cross-sheet formulas. `audit_sheet_refs()` scans every formula; an
  unquoted ref (which silently becomes `#NAME?`) fails the build.
- **Sensitivity centre cell ties out** to the P&L EBITDA of the target year; the
  **Base scenario ties out** to the P&L base model. Both checked ≈ 0.
- **Zero formula errors is a ship gate.** `#REF!/#DIV/0!/#VALUE!/#NAME?/#N/A/#NUM!`
  anywhere → `verification.passed = False`.

## Mandatory verification loop (non-negotiable)
`build_and_verify()` recalculates the workbook with the pure-Python `formulas`
engine, scans **every** cell for Excel errors, confirms the tie-out cells are ≈0,
and confirms the live P&L EBITDA/Revenue equal an independent Python shadow model
("does the centre sensitivity cell equal the P&L's EBITDA? It must"). It never
returns "done" without this.

## Usage
```python
from fin_model import build_and_verify           # skill dir on sys.path
result = build_and_verify(assumptions, "out/model.xlsx")
assert result["verification"]["passed"], result["verification"]
print(result["summary"]["peak_funding_requirement"])
```
Standalone, or bound to the CFO Agent (see `cfo_agent.py`). Pair with
`fin-model-presentation` to add native charts and a board-ready PDF.

## Runtime
Native Python: `openpyxl` (build), `formulas` (recalc/verify). No Node.js
(manifest §1). Auto-registered into the MAF skills tree at
`.agents/skills/fin-model/`.
```bash
pip install openpyxl formulas
```
