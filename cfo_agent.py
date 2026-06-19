import os
import sys
import json
import logging
from model_router import route
from cfo_excel_architect import get_cfo_architect
# Additive binding: live formula-driven model (fin-model) + board packaging
# (fin-model-presentation). Import is lazy-safe — the skills themselves are only
# loaded when a model is actually requested (see cfo_financial_skills.load_skills).
from cfo_financial_skills import detect_model_intent, build_model_and_pack

logger = logging.getLogger("CFOAgent")

_FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))


def _build_cfo_bottom_up(cost_inputs: dict, vault_dir: str = None) -> dict:
    """Run the deterministic bottom-up model (Core_Framework.cost_accountancy) from
    LLM-extracted line-item inputs. Produces the structures the Critic gate mandates:
    cogs_line_items, cash_flow_5yr, capex_schedule, and an exported .xlsx path.
    Returns {} if inputs are insufficient (the gate then correctly rejects)."""
    if not cost_inputs or not cost_inputs.get("raw_materials"):
        return {}
    try:
        _cf_dir = os.path.join(_FACTORY_DIR, "Core_Framework")
        if _cf_dir not in sys.path:
            sys.path.insert(0, _cf_dir)
        import cost_accountancy as ca
        inp = ca.CostInputs(
            product_name=cost_inputs.get("product_name", "Venture Product"),
            units_per_month=int(cost_inputs.get("units_per_month", 0) or 0),
            raw_materials=[ca.RawMaterial(r.get("item", ""), float(r.get("qty_per_unit", 0) or 0),
                                          float(r.get("unit_cost", 0) or 0))
                           for r in cost_inputs.get("raw_materials", [])],
            line_time_minutes_per_unit=float(cost_inputs.get("line_time_minutes_per_unit", 0) or 0),
            line_cost_per_minute=float(cost_inputs.get("line_cost_per_minute", 0) or 0),
            labor_cost_per_unit=float(cost_inputs.get("labor_cost_per_unit", 0) or 0),
            packaging_cost_per_unit=float(cost_inputs.get("packaging_cost_per_unit", 0) or 0),
            logistics_cost_per_unit=float(cost_inputs.get("logistics_cost_per_unit", 0) or 0),
            retail_price_per_unit=float(cost_inputs.get("retail_price_per_unit", 0) or 0),
            monthly_fixed_opex=float(cost_inputs.get("monthly_fixed_opex", 0) or 0),
            capex_items=[ca.CapExItem(c.get("item", ""), float(c.get("cost", 0) or 0),
                                      float(c.get("useful_life_years", 1) or 1))
                         for c in cost_inputs.get("capex_items", [])],
            annual_growth_rate=float(cost_inputs.get("annual_growth_rate", 0) or 0),
        )
        vault_dir = vault_dir or os.path.join(_FACTORY_DIR, "vault", "venture")
        model = ca.build_cfo_model(inp, xlsx_dir=vault_dir)
        return {
            "cogs_line_items": model["cogs_line_items"],
            "cogs_per_unit": model["cogs_per_unit"],
            "gross_margin_pct": model["gross_margin_pct"],
            "capex_schedule": model["capex_schedule"],
            "cash_flow_5yr": model["cash_flow_5yr"],
            "xlsx_path": model.get("xlsx_path"),
        }
    except Exception as e:
        logger.error(f"CFO bottom-up model build failed: {e}")
        return {}


class CFOAgent:
    def synthesize(self, project_id: str, cmo_data: dict, cto_data: dict, market_pulse: dict = None) -> dict:
        prompt = f"""You are an elite Chief Financial Officer.
You must ingest the following data and output foundational financial assumptions for a deterministic Python math engine to process. Do NOT attempt to calculate NPV or ROI yourself.

CMO Data:
{json.dumps(cmo_data, indent=2)}

CTO Data:
{json.dumps(cto_data, indent=2)}

Market Pulse (Sentiment):
{json.dumps(market_pulse or {}, indent=2)}

Synthesize the data and provide reasonable estimations for the following foundational variables:
- estimated_cogs_per_unit: Your best estimate for the cost of goods sold per unit (in USD).
- recommended_retail_price: Your recommended retail price point per unit (in USD).
- projected_monthly_sales: The estimated number of units sold per month at launch.
- risk_multiplier_1_to_2: A float between 1.0 (low risk) and 2.0 (high risk) scaling the total portfolio cost based on technical debt and market sentiment.

CPG/VENTURE STRUCTURAL MANDATE (Critic-enforced — NON-NEGOTIABLE):
- Speculative NPV/ROI projections built on raw revenue assumptions are STRICTLY PROHIBITED and will be rejected.
- Lump-sum cost estimates without line-item breakdowns are STRICTLY PROHIBITED and will be rejected.
- You MUST provide a granular bottom-up "cost_inputs" object so the deterministic engine can build the COGS line items, a 5-year cash-flow projection, and an amortized CapEx schedule. Provide your best line-item figures; if a value is unknown, give a clearly-reasoned estimate rather than a lump sum.

You must ALSO provide two substantive CFO narrative sections (3+ sentences each):
- financial_analysis: detailed pricing-strategy commentary and the break-even rationale (why this price, margin structure, what drives the break-even point).
- investment_recommendations: recommendations on funding (bootstrap vs raise), capex priorities, and cash-management / runway guidance.

Return ONLY valid JSON with these EXACT keys:
{{
    "estimated_cogs_per_unit": 0.0,
    "recommended_retail_price": 0.0,
    "projected_monthly_sales": 0,
    "risk_multiplier_1_to_2": 1.0,
    "financial_analysis": "",
    "investment_recommendations": "",
    "cost_inputs": {{
        "product_name": "",
        "units_per_month": 0,
        "raw_materials": [{{"item": "", "qty_per_unit": 0.0, "unit_cost": 0.0}}],
        "line_time_minutes_per_unit": 0.0,
        "line_cost_per_minute": 0.0,
        "labor_cost_per_unit": 0.0,
        "packaging_cost_per_unit": 0.0,
        "logistics_cost_per_unit": 0.0,
        "retail_price_per_unit": 0.0,
        "monthly_fixed_opex": 0.0,
        "capex_items": [{{"item": "", "cost": 0.0, "useful_life_years": 0.0}}],
        "annual_growth_rate": 0.0
    }}
}}
Do NOT wrap the JSON in Markdown block formatting. Output raw JSON only.
"""
        response = route("CFO", prompt, system_prompt="You are an elite CFO. Output strictly raw JSON.")
        
        # Clean response string if Claude wrapped it in markdown or prefixed it
        start_idx = response.find("{")
        end_idx = response.rfind("}")
        if start_idx != -1 and end_idx > start_idx:
            response_clean = response[start_idx:end_idx + 1]
        else:
            response_clean = response
            
        try:
            metrics = json.loads(response_clean)
        except Exception as e:
            logger.error(f"Failed to parse CFO JSON: {e} - Response: {response}")
            return {"status": "error", "message": f"CFO JSON Parsing failed: {e}"}
            
        architect = get_cfo_architect()
        result = architect.generate_business_plan_from_json(project_id, cmo_data, cto_data, market_pulse, metrics)

        # Thread the CFO narrative sections through to the consumer. The math
        # engine ignores these extra metric keys, and the schema validator
        # (CFOOutput) ignores unknown result keys, so this is non-breaking.
        if isinstance(result, dict):
            result.setdefault("financial_analysis", metrics.get("financial_analysis", ""))
            result.setdefault("investment_recommendations", metrics.get("investment_recommendations", ""))
            # Attach the deterministic bottom-up structures the Critic gate mandates
            # (COGS line items, 5-yr cash flow, CapEx schedule, exported .xlsx).
            bottom_up = _build_cfo_bottom_up(metrics.get("cost_inputs", {}))
            if bottom_up:
                result.update(bottom_up)
        return result

    # ── Financial-skills binding (fin-model → fin-model-presentation) ─────────
    # These methods are additive: the CFO Agent reaches for the financial skills
    # on model/projection/unit-economics/P&L/budget/break-even/sensitivity/
    # fundraising intents, builds the live model, then packages it for the board.

    def build_financial_model(self, assumptions: dict, brand_tokens=None,
                              project_id: str = "cfo_model", present_pack: bool = True) -> dict:
        """Directly build + verify a live model and (optionally) package it for the
        board. Returns workbook/PDF paths, the recalc gate, an executive summary,
        and a call trace proving the skills were reached through the binding."""
        try:
            return build_model_and_pack(assumptions, brand_tokens=brand_tokens,
                                        project_id=project_id, present_pack=present_pack)
        except Exception as e:
            logger.error(f"CFO financial-model build failed: {e}")
            return {"status": "error", "message": f"fin-model build failed: {e}"}

    def extract_assumptions(self, instruction: str, context: dict = None) -> dict:
        """Use the CFO's LLM (Claude via model_router) to turn a natural-language
        request into the fin-model assumptions dict. Falls back to a minimal,
        clearly-labelled default if the LLM is unavailable, so the binding still
        runs end-to-end offline."""
        context = context or {}
        prompt = f"""You are an elite CFO preparing inputs for a deterministic Excel model engine.
From the request below, output ONLY a raw JSON object of model assumptions (no markdown).
Use these EXACT keys (estimate sensibly where unstated; units are USD):
{{
  "product_name": "", "units_per_month": 0, "annual_growth_rate": 0.0,
  "retail_price_per_unit": 0.0,
  "raw_materials": [{{"item": "", "qty_per_unit": 0.0, "unit_cost": 0.0}}],
  "line_time_minutes_per_unit": 0.0, "line_cost_per_minute": 0.0,
  "labor_cost_per_unit": 0.0, "packaging_cost_per_unit": 0.0,
  "logistics_cost_per_unit": 0.0, "monthly_fixed_opex": 0.0,
  "capex_items": [{{"item": "", "cost": 0.0, "useful_life_years": 0.0}}],
  "tax_rate": 0.21, "nwc_days": 45, "num_stores": 0, "years": 5,
  "sensitivity": {{"target_year": 5}}
}}
REQUEST: {instruction}
CONTEXT: {json.dumps(context)}
Output raw JSON only."""
        try:
            resp = route("financial_model", prompt,
                         system_prompt="You are an elite CFO. Output strictly raw JSON.")
            s, e = resp.find("{"), resp.rfind("}")
            return json.loads(resp[s:e + 1]) if s != -1 and e > s else {}
        except Exception as ex:
            logger.error(f"CFO assumption extraction failed, using fallback: {ex}")
            return {"product_name": context.get("product_name", "Venture (assumptions estimated)"),
                    "units_per_month": 10000, "annual_growth_rate": 0.20,
                    "retail_price_per_unit": 4.0,
                    "raw_materials": [{"item": "Materials", "qty_per_unit": 1, "unit_cost": 1.0}],
                    "labor_cost_per_unit": 0.2, "packaging_cost_per_unit": 0.1,
                    "logistics_cost_per_unit": 0.25, "monthly_fixed_opex": 50000,
                    "capex_items": [{"item": "Equipment", "cost": 150000, "useful_life_years": 7}],
                    "tax_rate": 0.21, "nwc_days": 45, "num_stores": 0, "years": 5,
                    "sensitivity": {"target_year": 5}, "_assumptions_estimated": True}

    def route_and_build(self, instruction: str, assumptions: dict = None, brand_tokens=None,
                        project_id: str = "cfo_model", context: dict = None) -> dict:
        """Boardroom entrypoint: detect a model intent in `instruction`; if present,
        obtain assumptions (provided, or extracted via the CFO's LLM) and chain
        fin-model → fin-model-presentation. Non-model requests are passed through
        untouched (returns {'status': 'no_model_intent'}) so existing flows are safe."""
        if not detect_model_intent(instruction):
            return {"status": "no_model_intent",
                    "message": "No financial-model intent detected; CFO Agent handled normally."}
        if not assumptions:
            assumptions = self.extract_assumptions(instruction, context)
        result = self.build_financial_model(assumptions, brand_tokens=brand_tokens,
                                            project_id=project_id)
        result["intent"] = "financial_model"
        result["instruction"] = instruction
        return result
