import json
import logging
from model_router import route
from cfo_excel_architect import get_cfo_architect

logger = logging.getLogger("CFOAgent")

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

Return ONLY valid JSON with these EXACT keys:
{{
    "estimated_cogs_per_unit": 0.0,
    "recommended_retail_price": 0.0,
    "projected_monthly_sales": 0,
    "risk_multiplier_1_to_2": 1.0
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
        return result
