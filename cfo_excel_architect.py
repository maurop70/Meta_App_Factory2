"""
cfo_excel_architect.py — Phase 5: Aether-Native CFO Excel Extraction
═════════════════════════════════════════════════════════════════════
Replaces the n8n Antigravity_CFO_Execution_Controller workflow.
Generates the Business Plan summary and Excel model natively.
Protected by the V3 Resilience Core (auto_heal).
"""
import os
import time
from datetime import datetime
import pandas as pd
from auto_heal import _log_heal_event

class CFOExcelArchitect:
    def __init__(self):
        # We will dynamically generate the path in generate_business_plan
        pass

    def _get_artifact_path(self, project_id: str) -> str:
        safe_id = "".join(c for c in project_id if c.isalnum() or c in (' ', '_', '-')).strip()
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "projects",
            safe_id,
            "artifacts",
            "cfo_reports"
        )
        os.makedirs(path, exist_ok=True)
        return path

    def generate_business_plan(self, project_id: str, cmo_data: dict, cto_data: dict, market_pulse: dict = None) -> dict:
        """
        Calculates standard financial metrics and generates an .xlsx file.
        Returns a dictionary representing the business plan summary.
        """
        try:
            # 1. Extract CMO Metrics
            marketing_cost = float(cmo_data.get("marketing_cost", 0))
            projected_revenue = float(cmo_data.get("projected_revenue", 0))
            rev_timeline = float(cmo_data.get("revenue_timeline_months", 12))
            
            # --- PHASE 9: Sentiment Action Map (Growth Multiplier / Capital Squeeze) ---
            sentiment = market_pulse.get("verdict", "NEUTRAL") if market_pulse else "NEUTRAL"
            growth_multiplier = 1.0
            
            if sentiment == "BULLISH":
                growth_multiplier = 1.5
                marketing_cost = marketing_cost * 1.2  # Authorize aggressive Go-to-Market budget
            elif sentiment == "BEARISH":
                growth_multiplier = 0.7
                marketing_cost = marketing_cost * 0.7  # CapEx freeze / 30% reduction
                
            projected_revenue = projected_revenue * growth_multiplier
            
            # 2. Extract CTO Metrics
            feasibility = float(cto_data.get("technical_feasibility_score", 5))
            dev_buffer = float(cto_data.get("dev_buffer_weeks", 0))
            infra_cost_mo = float(cto_data.get("infrastructure_cost_estimate", 0))
            tech_debt_premium = float(cto_data.get("tech_debt_risk_premium_pct", 0))
            
            # 3. Math Engine — The Excel Logic extracted from n8n 
            # A. Fragility Index (Max 100 - base 10 * feasibility)
            fragility = max(0.0, 100.0 - (feasibility * 10))

            # B. Total Cost Basis (Marketing + Buffer + Infra + Tech Debt)
            # Dev buffer cost assumption ($2.5k / dev week runtime cost)
            dev_cost = dev_buffer * 2500
            total_infra = infra_cost_mo * max(rev_timeline, 1)  # Spread across rev timeline
            base_budget = marketing_cost + dev_cost + total_infra
            
            risk_premium_dollars = base_budget * (tech_debt_premium / 100.0)
            total_cost = base_budget + risk_premium_dollars

            # C. ROI & NPV (10% discount rate)
            if total_cost > 0:
                roi_pct = ((projected_revenue - total_cost) / total_cost) * 100.0
                roas = projected_revenue / max(marketing_cost, 1.0)
            else:
                roi_pct = 0.0
                roas = 0.0
            
            discount_rate = 0.10
            npv = (projected_revenue / (1 + discount_rate)) - total_cost
            
            # D. Risk-Adjusted ROI (scaled by feasibility factor)
            risk_adj_roi = roi_pct * (feasibility / 10.0)

            # 4. Generate Excel using Native Pandas/OpenPyXL
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{project_id}_CFO_Report_{ts}.xlsx"
            filepath = os.path.join(self._get_artifact_path(project_id), filename)
            ui_filepath = os.path.join(self._get_artifact_path(project_id), "business_plan.xlsx")
            
            data_dict = {
                "marketing_cost": marketing_cost,
                "projected_revenue": projected_revenue,
                "dev_cost": dev_cost,
                "infra_cost": total_infra,
                "risk_premium": risk_premium_dollars,
                "total_cost": total_cost,
                "roi_pct": roi_pct,
                "risk_adj_roi": risk_adj_roi,
                "npv": npv,
                "fragility": fragility,
                "roas": roas,
                "sentiment": sentiment,
                "growth_multiplier": growth_multiplier
            }
            self._write_excel(filepath, data_dict)
            self._write_excel(ui_filepath, data_dict)

            # 5. Build Return JSON (Matches exactly what n8n used to emit)
            return {
                "status": "success",
                "file_name": filename,
                "strategic_sentiment": sentiment,
                "growth_multiplier": growth_multiplier,
                "fragility_index": round(fragility, 1),
                "total_cost": round(total_cost, 2),
                "projected_revenue": round(projected_revenue, 2),
                "roi_percentage": round(roi_pct, 1),
                "risk_adjusted_roi": round(risk_adj_roi, 1),
                "npv": round(npv, 2),
                "roas": round(roas, 2),
                "infrastructure_term_cost": round(total_infra, 2),
                "cfo_math_error": False,
                "message": "CFO Agent has deployed the Fragility Report natively."
            }

        except ZeroDivisionError as e:
            # [V3 RESILIENCE CORE] Route math faults cleanly
            _log_heal_event("CFOExcelArchitect", "Zero division in financial math", {"error": str(e)}, "math_error")
            return {"status": "math_error", "cfo_math_error": True, "error": str(e), "message": "Math Fault: Attempted to divide by zero on zero-budget constraint."}
            
        except Exception as e:
            # [V3 RESILIENCE CORE] Catch all pandas errors
            _log_heal_event("CFOExcelArchitect", "Native extraction fault", {"error": repr(e)}, "execution_fault")
            return {"status": "error", "cfo_math_error": True, "error": repr(e), "message": "Critical failure in CFO Excel Architect."}

    def generate_business_plan_from_json(self, project_id: str, cmo_data: dict, cto_data: dict, market_pulse: dict, claude_json: dict) -> dict:
        """
        Accepts the parsed cognitive assumptions from Claude 3.7 Sonnet,
        generates the Excel physically using strict deterministic math, 
        and returns the strict I/O contract.
        """
        try:
            # Extract Claude's Assumptions
            estimated_cogs = float(claude_json.get("estimated_cogs_per_unit", 0))
            recommended_price = float(claude_json.get("recommended_retail_price", 1))
            monthly_sales = float(claude_json.get("projected_monthly_sales", 0))
            risk_multiplier = float(claude_json.get("risk_multiplier_1_to_2", 1.0))
            
            # Reconstruct CMO/CTO Data
            rev_timeline = float(cmo_data.get("revenue_timeline_months", 12))
            feasibility = float(cto_data.get("technical_feasibility_score", 5))
            dev_buffer = float(cto_data.get("dev_buffer_weeks", 0))
            infra_cost_mo = float(cto_data.get("infrastructure_cost_monthly", 0))
            if infra_cost_mo == 0:
                infra_cost_mo = float(cto_data.get("infrastructure_cost_estimate", 0))
            tech_debt_premium = float(cto_data.get("tech_debt_risk_premium_pct", 0))
            
            # --- DETERMINISTIC MATH ENGINE ---
            sentiment = market_pulse.get("verdict", "NEUTRAL") if market_pulse else "NEUTRAL"
            
            # Revenue & COGS Calculations
            projected_revenue = monthly_sales * recommended_price * rev_timeline
            total_cogs = monthly_sales * estimated_cogs * rev_timeline
            gross_margin = projected_revenue - total_cogs
            
            # Base Cost Calculations
            marketing_cost = float(cmo_data.get("marketing_cost", 0))
            dev_cost = dev_buffer * 2500
            total_infra = infra_cost_mo * max(rev_timeline, 1)
            base_budget = marketing_cost + dev_cost + total_infra
            
            # Risk Adjusted Totals
            risk_premium_dollars = base_budget * (tech_debt_premium / 100.0)
            base_total_cost = base_budget + risk_premium_dollars + total_cogs
            total_cost = base_total_cost * risk_multiplier
            
            # ROI / NPV / Fragility
            fragility = max(0.0, 100.0 - (feasibility * 10))
            
            if total_cost > 0:
                roi_pct = ((projected_revenue - total_cost) / total_cost) * 100.0
                roas = projected_revenue / max(marketing_cost, 1.0)
            else:
                roi_pct = 0.0
                roas = 0.0
                
            discount_rate = 0.10
            npv = (projected_revenue / (1 + discount_rate)) - total_cost
            risk_adj_roi = roi_pct * (feasibility / 10.0)

            # File Generation
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{project_id}_CFO_Report_{ts}.xlsx"
            filepath = os.path.join(self._get_artifact_path(project_id), filename)
            ui_filepath = os.path.join(self._get_artifact_path(project_id), "business_plan.xlsx")
            
            data_dict = {
                "marketing_cost": marketing_cost,
                "projected_revenue": projected_revenue,
                "dev_cost": dev_cost,
                "infra_cost": total_infra,
                "risk_premium": risk_premium_dollars,
                "total_cost": total_cost,
                "roi_pct": roi_pct,
                "risk_adj_roi": risk_adj_roi,
                "npv": npv,
                "fragility": fragility,
                "roas": roas,
                "sentiment": sentiment,
                "growth_multiplier": risk_multiplier
            }
            self._write_excel(filepath, data_dict)
            self._write_excel(ui_filepath, data_dict)

            return {
                "status": "success",
                "file_name": filename,
                "strategic_sentiment": sentiment,
                "growth_multiplier": risk_multiplier,
                "fragility_index": round(fragility, 1),
                "total_cost": round(total_cost, 2),
                "projected_revenue": round(projected_revenue, 2),
                "roi_percentage": round(roi_pct, 1),
                "risk_adjusted_roi": round(risk_adj_roi, 1),
                "npv": round(npv, 2),
                "roas": round(roas, 2),
                "infrastructure_term_cost": round(total_infra, 2),
                "cfo_math_error": False,
                "message": f"Financial Model Generated: {filename}"
            }
        except Exception as e:
            _log_heal_event("CFOExcelArchitect", "Native extraction fault (JSON Bridge)", {"error": repr(e)}, "execution_fault")
            return {"status": "error", "cfo_math_error": True, "error": repr(e), "message": "Critical failure in CFO JSON Bridge."}

    def _write_excel(self, filepath: str, data: dict):
        """Builds a multi-sheet CFO model."""
        # Dashboard Sheet
        df_dash = pd.DataFrame([
            {"Metric": "Strategic Sentiment", "Value": str(data.get("sentiment", "NEUTRAL"))},
            {"Metric": "Revenue Multiplier", "Value": str(data.get("growth_multiplier", 1.0))},
            {"Metric": "Fragility Index", "Value": data["fragility"]},
            {"Metric": "Total Portfolio Cost", "Value": data["total_cost"]},
            {"Metric": "Projected Revenue", "Value": data["projected_revenue"]},
            {"Metric": "Baseline ROI %", "Value": data["roi_pct"]},
            {"Metric": "Risk-Adjusted ROI %", "Value": data["risk_adj_roi"]},
            {"Metric": "Net Present Value (NPV)", "Value": data["npv"]},
            {"Metric": "ROAS Target", "Value": data["roas"]}
        ])

        # Input Data Sheet
        df_input = pd.DataFrame([
            {"Category": "Marketing Cost", "Amount": data["marketing_cost"]},
            {"Category": "Dev Buffer Cost", "Amount": data["dev_cost"]},
            {"Category": "Infrastructure Term Cost", "Amount": data["infra_cost"]},
            {"Category": "Tech Debt Risk Premium", "Amount": data["risk_premium"]}
        ])
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df_dash.to_excel(writer, sheet_name="Dashboard", index=False)
            df_input.to_excel(writer, sheet_name="Input_Data", index=False)


# Singleton access
_architect = CFOExcelArchitect()

def get_cfo_architect():
    return _architect

if __name__ == "__main__":
    # Test execution
    architect = get_cfo_architect()
    result = architect.generate_business_plan(
        project_id="Aether",
        cmo_data={"marketing_cost": 50000, "projected_revenue": 250000, "revenue_timeline_months": 12},
        cto_data={
            "technical_feasibility_score": 6.8, 
            "dev_buffer_weeks": 4.5, 
            "infrastructure_cost_estimate": 450, 
            "tech_debt_risk_premium_pct": 10
        },
        market_pulse={"verdict": "BULLISH", "trend_velocity": 8.5, "public_sentiment_score": 65.0} # Phase 9 Test
    )
    print("Mock CFO Execution:")
    import json
    print(json.dumps(result, indent=2))
