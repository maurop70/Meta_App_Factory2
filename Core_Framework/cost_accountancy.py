"""
core_framework/cost_accountancy.py — Bottom-up Cost & P&L engine (CFO dependency)
═══════════════════════════════════════════════════════════════════════════════
Ingests line-item inputs (raw materials, line-time, labor, packaging, logistics)
and produces a DETERMINISTIC P&L / cash-flow / CapEx schedule. There are NO
speculative fields: every value is derived arithmetically from supplied inputs.
Growth is only applied if an explicit per-year growth rate is provided.

Exports an .xlsx workbook (COGS, P&L, Cash Flow, CapEx sheets) to the project vault.

Usage:
    from core_framework.cost_accountancy import CostInputs, build_cfo_model
    model = build_cfo_model(CostInputs(...), xlsx_dir="vault/venture")
    # model["cogs_line_items"], model["cash_flow_5yr"], model["capex_schedule"], model["xlsx_path"]
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RawMaterial:
    item: str
    qty_per_unit: float       # e.g. ounces / grams / each
    unit_cost: float          # cost per qty unit (USD)

    @property
    def cost_per_unit(self) -> float:
        return round(self.qty_per_unit * self.unit_cost, 4)


@dataclass
class CapExItem:
    item: str
    cost: float               # one-time acquisition/setup cost (USD)
    useful_life_years: float  # amortization horizon

    @property
    def annual_amortization(self) -> float:
        if self.useful_life_years <= 0:
            return round(self.cost, 2)
        return round(self.cost / self.useful_life_years, 2)


@dataclass
class CostInputs:
    product_name: str
    units_per_month: int
    raw_materials: list                      # list[RawMaterial]
    line_time_minutes_per_unit: float
    line_cost_per_minute: float              # machine/line cost per minute
    labor_cost_per_unit: float
    packaging_cost_per_unit: float
    logistics_cost_per_unit: float
    retail_price_per_unit: float
    monthly_fixed_opex: float = 0.0          # rent, salaries, software (line-itemizable upstream)
    capex_items: list = field(default_factory=list)   # list[CapExItem]
    annual_growth_rate: float = 0.0          # 0.0 == no speculative growth
    years: int = 5


def compute_cogs_line_items(inp: CostInputs) -> list:
    """Per-unit COGS broken into auditable line items. Deterministic."""
    items = []
    for rm in inp.raw_materials:
        items.append({
            "category": "Raw Material",
            "item": rm.item,
            "qty_per_unit": rm.qty_per_unit,
            "unit_cost": rm.unit_cost,
            "cost_per_unit": rm.cost_per_unit,
        })
    line_time_cost = round(inp.line_time_minutes_per_unit * inp.line_cost_per_minute, 4)
    items.append({"category": "Line-Time", "item": "Production line time",
                  "qty_per_unit": inp.line_time_minutes_per_unit, "unit_cost": inp.line_cost_per_minute,
                  "cost_per_unit": line_time_cost})
    items.append({"category": "Labor", "item": "Direct labor",
                  "qty_per_unit": 1, "unit_cost": inp.labor_cost_per_unit,
                  "cost_per_unit": round(inp.labor_cost_per_unit, 4)})
    items.append({"category": "Packaging", "item": "Packaging",
                  "qty_per_unit": 1, "unit_cost": inp.packaging_cost_per_unit,
                  "cost_per_unit": round(inp.packaging_cost_per_unit, 4)})
    items.append({"category": "Logistics", "item": "Inbound/outbound logistics",
                  "qty_per_unit": 1, "unit_cost": inp.logistics_cost_per_unit,
                  "cost_per_unit": round(inp.logistics_cost_per_unit, 4)})
    return items


def cogs_per_unit(inp: CostInputs) -> float:
    return round(sum(li["cost_per_unit"] for li in compute_cogs_line_items(inp)), 4)


def build_capex_schedule(inp: CostInputs) -> list:
    """CapEx schedule with explicit per-item annual amortization."""
    schedule = []
    for ci in inp.capex_items:
        schedule.append({
            "item": ci.item,
            "acquisition_cost": round(ci.cost, 2),
            "useful_life_years": ci.useful_life_years,
            "annual_amortization": ci.annual_amortization,
        })
    return schedule


def build_cash_flow(inp: CostInputs) -> list:
    """Deterministic N-year cash flow. Year-over-year units scale only by the
    explicitly supplied growth rate (default 0.0 → flat, no speculation)."""
    cpu = cogs_per_unit(inp)
    annual_capex_amort = sum(c["annual_amortization"] for c in build_capex_schedule(inp))
    total_capex = sum(c["acquisition_cost"] for c in build_capex_schedule(inp))
    rows = []
    units_month = float(inp.units_per_month)
    for y in range(1, inp.years + 1):
        annual_units = units_month * 12
        revenue = round(annual_units * inp.retail_price_per_unit, 2)
        cogs = round(annual_units * cpu, 2)
        gross_profit = round(revenue - cogs, 2)
        opex = round(inp.monthly_fixed_opex * 12, 2)
        # CapEx is a cash outflow in year 1; amortization is the non-cash P&L view.
        capex_outflow = round(total_capex, 2) if y == 1 else 0.0
        operating_income = round(gross_profit - opex - annual_capex_amort, 2)
        net_cash_flow = round(gross_profit - opex - capex_outflow, 2)
        rows.append({
            "year": y,
            "units": int(round(annual_units)),
            "revenue": revenue,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "opex": opex,
            "capex_amortization": round(annual_capex_amort, 2),
            "operating_income": operating_income,
            "capex_outflow": capex_outflow,
            "net_cash_flow": net_cash_flow,
        })
        units_month = units_month * (1.0 + inp.annual_growth_rate)
    return rows


def _safe_slug(name: str) -> str:
    return "".join(c for c in (name or "venture") if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_") or "venture"


def export_xlsx(inp: CostInputs, model: dict, xlsx_dir: str) -> Optional[str]:
    """Write COGS / P&L / Cash Flow / CapEx sheets to an .xlsx in xlsx_dir."""
    try:
        import pandas as pd
    except ImportError:
        return None
    os.makedirs(xlsx_dir, exist_ok=True)
    path = os.path.join(xlsx_dir, f"{_safe_slug(inp.product_name)}_CFO_Model.xlsx")
    cogs_df = pd.DataFrame(model["cogs_line_items"])
    cashflow_df = pd.DataFrame(model["cash_flow_5yr"])
    capex_df = pd.DataFrame(model["capex_schedule"]) if model["capex_schedule"] else pd.DataFrame(
        [{"item": "(none)", "acquisition_cost": 0, "useful_life_years": 0, "annual_amortization": 0}]
    )
    summary_df = pd.DataFrame([{
        "product": inp.product_name,
        "cogs_per_unit": model["cogs_per_unit"],
        "retail_price_per_unit": inp.retail_price_per_unit,
        "gross_margin_pct": model["gross_margin_pct"],
        "units_per_month": inp.units_per_month,
    }])
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        cogs_df.to_excel(writer, sheet_name="COGS", index=False)
        cashflow_df.to_excel(writer, sheet_name="CashFlow_5yr", index=False)
        capex_df.to_excel(writer, sheet_name="CapEx", index=False)
    return path


def build_cfo_model(inp: CostInputs, xlsx_dir: Optional[str] = None) -> dict:
    """Top-level: produce the full deterministic CFO model (+ optional .xlsx export)."""
    cogs_items = compute_cogs_line_items(inp)
    cpu = round(sum(li["cost_per_unit"] for li in cogs_items), 4)
    gross_margin_pct = round(
        ((inp.retail_price_per_unit - cpu) / inp.retail_price_per_unit * 100.0), 2
    ) if inp.retail_price_per_unit else 0.0
    model = {
        "product_name": inp.product_name,
        "cogs_line_items": cogs_items,
        "cogs_per_unit": cpu,
        "gross_margin_pct": gross_margin_pct,
        "capex_schedule": build_capex_schedule(inp),
        "cash_flow_5yr": build_cash_flow(inp),
        "speculative": False,
    }
    if xlsx_dir:
        model["xlsx_path"] = export_xlsx(inp, model, xlsx_dir)
    return model
