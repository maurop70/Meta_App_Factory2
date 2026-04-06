"""
socratic_bridge.py — Resonance: Socratic Bridge (Native Python)
══════════════════════════════════════════════════════════════════════════════
Translates the n8n HTTP workflow to native Python for sub-second latency.
Handles the 'Agent Handshake' between the CMO (Strategy) and CFO (Math Witness).
"""

import os
import sys
import json
import time
import logging
import google.generativeai as genai

# Setup path to import CFO Excel Architect from parent dir
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_DIR = os.path.dirname(SCRIPT_DIR)
if FACTORY_DIR not in sys.path:
    sys.path.insert(0, FACTORY_DIR)

from cfo_excel_architect import get_cfo_architect

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("SocraticBridge")

class SocraticController:
    def __init__(self, model_name="gemini-2.5-flash", max_pivots=3):
        self.max_pivots = max_pivots
        self.model_name = model_name
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
        else:
            logger.warning("GEMINI_API_KEY not found. SocraticController will run in MOCK mode.")
            self.model = None

    def _extract_cmo_data(self, strategy_text: str) -> dict:
        """Use Gemini to extract structured financial data from the CMO's unstructured strategy."""
        if not self.model:
            return {"marketing_cost": 25000, "projected_revenue": 100000, "revenue_timeline_months": 12}
            
        system = (
            "Extract the following financial metrics from the marketing strategy below.\n"
            "Return ONLY valid JSON with no markdown blocks formatting.\n"
            "Keys MUST exactly be: `marketing_cost` (float), `projected_revenue` (float), `revenue_timeline_months` (int).\n"
        )
        prompt = f"{system}\n\nSTRATEGY:\n{strategy_text}"
        try:
            response = self.model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            data = json.loads(response.text)
            return {
                "marketing_cost": float(data.get("marketing_cost", 25000)),
                "projected_revenue": float(data.get("projected_revenue", 100000)),
                "revenue_timeline_months": float(data.get("revenue_timeline_months", 12))
            }
        except Exception as e:
            logger.error(f"CMO Data Extraction failed: {e}")
            # Safe Fallback to prevent crash
            return {"marketing_cost": 25000, "projected_revenue": 100000, "revenue_timeline_months": 12}

    def _call_cmo_pivot(self, original_strategy: str, cfo_feedback: str) -> str:
        """Ask the CMO to dynamically pivot based on CFO constraints."""
        if not self.model:
            return original_strategy + "\n[MOCK: Pivoted strategy to adjust budget down by 20%]"
            
        system = (
            "You are the CMO_Agent inside the Meta App Factory War Room. Your previous marketing "
            "strategy was aggressively audited by the CFO (the Math Witness) and flagged for a DEFICIT.\n"
            "You must pivot the strategy to immediately address the CFO's explicit constraints "
            "while doing your best to maintain your growth targets."
        )
        prompt = (
            f"{system}\n\n"
            f"[ORIGINAL CMO STRATEGY]:\n{original_strategy}\n\n"
            f"[CFO AUDIT FEEDBACK]:\n{cfo_feedback}\n\n"
            "Return ONLY the updated, PIVOTED STRATEGY (in plain text). Include explicit updated budget numbers."
        )
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"CMO Pivot generate error: {e}")
            return original_strategy

    def execute_handshake(self, project_id: str, initial_strategy: str, cto_data: dict = None, market_pulse: dict = None) -> dict:
        """
        Executes the Socratic Bridge debate securely. Natively calls CFO Excel Architect as the Math Witness.
        Caps at 3 iterations to prevent infinite loops, returning ESCALATED_TO_COMMANDER.
        """
        start_time = time.time()
        cfo_architect = get_cfo_architect()
        
        if cto_data is None:
            # Baseline feasibility variables needed by the Math Witness
            cto_data = {
                "technical_feasibility_score": 7.0, 
                "dev_buffer_weeks": 4.0, 
                "infrastructure_cost_estimate": 450, 
                "tech_debt_risk_premium_pct": 10
            }
        
        if market_pulse is None:
            market_pulse = {"verdict": "NEUTRAL", "trend_velocity": 5.0, "public_sentiment_score": 0.0}
        
        history = []
        current_strategy = initial_strategy
        pivots_taken = 0
        final_status = "UNKNOWN"

        logger.info(f"Initiating Agent Handshake for {project_id}: CMO ↔ CFO Socratic Bridge")
        history.append({"agent": "CMO", "action": "SUBMIT_STRATEGY", "content": current_strategy})

        while pivots_taken <= self.max_pivots:
            # Step 1: LLM translates strategy text -> numerical params for Math Witness
            cmo_data = self._extract_cmo_data(current_strategy)
            
            # Step 2: Hard-wired Math Witness (CFO Excel Architect) computes truth
            logger.info(f"Triggering Math Witness CFO Excel Architect (Iteration {pivots_taken + 1})")
            cfo_result = cfo_architect.generate_business_plan(
                project_id=project_id,
                cmo_data=cmo_data,
                cto_data=cto_data,
                market_pulse=market_pulse
            )
            
            # Evaluate the raw financial result
            if cfo_result.get("status") in ["error", "math_error"]:
                audit_verdict = "ERROR"
                cfo_feedback = cfo_result.get("message", "Hard math fault detected.")
            else:
                roi = float(cfo_result.get("roi_percentage", 0))
                roas = float(cfo_result.get("roas", 0))
                fragility = float(cfo_result.get("fragility_index", 50))
                
                # Socratic Bridge logic boundary
                if roi <= 5.0 or fragility > 75.0:
                    audit_verdict = "DEFICIT"
                    cfo_feedback = f"Unacceptable metrics. ROI is {roi}% (Needs > 5%), Fragility is {fragility} (Needs < 75), ROAS is {roas}."
                else:
                    audit_verdict = "PASS"
                    cfo_feedback = f"Financially verified. ROI: {roi}%, Fragility: {fragility}, ROAS: {roas}."
            
            history.append({"agent": "CFO", "action": "AUDIT", "verdict": audit_verdict, "feedback": cfo_feedback})
            
            # Step 3: Deliberation Branching
            if audit_verdict == "PASS":
                # Check Risk Guardian hook before fully committing
                try:
                    from cfo_controller import CFOExecutionController
                    guardian = CFOExecutionController()
                    marketing_val = float(cmo_data.get("marketing_cost", 0.0))
                    commit_res = guardian.commit_budget(project_id, marketing_val)
                    
                    if commit_res.get("status") == "REJECTED_BY_RISK_GUARDIAN":
                        audit_verdict = "DEFICIT"
                        cfo_feedback = f"[RISK GUARDIAN BLOCK]: {commit_res['message']} Pivot the marketing spend DOWN significantly to stay below MAX_BURN."
                        logger.warning("Strategy mathematically approved by CFO, but system Risk Guardian blocked the execution due to MAX_BURN constraints.")
                        
                        if pivots_taken >= self.max_pivots:
                            logger.error(f"Maximum pivot threshold ({self.max_pivots}) reached due to Risk Guardian. Escalating.")
                            final_status = "ESCALATED_TO_COMMANDER"
                            break
                            
                        logger.info(f"Routing financial constraint back to CMO for Pivot #{pivots_taken + 1}.")
                        current_strategy = self._call_cmo_pivot(current_strategy, cfo_feedback)
                        history.append({"agent": "CMO", "action": "PIVOT", "content": current_strategy})
                        pivots_taken += 1
                        continue # Re-run the loop with the new strategy
                        
                    else:
                        logger.info("CFO approved the strategy and Risk Guardian COMMITTED. Handshake Complete.")
                        final_status = "PASSED"
                        history[-1]["token"] = commit_res.get("token")
                        break
                except Exception as e:
                    logger.error(f"Risk Guardian hook failed: {e}")
                    final_status = "SYSTEM_ERROR"
                    break
                
            elif audit_verdict == "ERROR":
                logger.error("Math Witness internal logic failed.")
                final_status = "SYSTEM_ERROR"
                break
                
            elif audit_verdict == "DEFICIT":
                logger.warning(f"CFO flagged a DEFICIT. Constraint: {cfo_feedback}")
                
                if pivots_taken >= self.max_pivots:
                    logger.error(f"Maximum pivot threshold ({self.max_pivots}) reached. Strategy deadlocked.")
                    final_status = "ESCALATED_TO_COMMANDER"
                    break
                    
                logger.info(f"Routing financial constraint back to CMO for Pivot #{pivots_taken + 1}.")
                current_strategy = self._call_cmo_pivot(current_strategy, cfo_feedback)
                
                history.append({"agent": "CMO", "action": "PIVOT", "content": current_strategy})
                pivots_taken += 1

        end_time = time.time()
        latency = end_time - start_time
        
        logger.info(f"Socratic Bridge Execution Complete. Latency: {latency:.4f}s")
        
        return {
            "status": final_status,
            "final_strategy": current_strategy,
            "cfo_feedback": history[-1]["feedback"],
            "pivots_taken": pivots_taken,
            "latency_seconds": round(latency, 4),
            "history": history,
            "cfo_metrics": cfo_result if audit_verdict != "ERROR" else {}
        }

if __name__ == "__main__":
    # Test suite for verifying latency and functionality
    mock_strategy = "We will spend an aggressive $800,000 on influencer marketing to drive $200,000 in immediate sales within 3 months."
    controller = SocraticController()
    
    print("\nStarting Socratic Bridge Native Execution...")
    result = controller.execute_handshake(
        project_id="Aether_Mock_Trial", 
        initial_strategy=mock_strategy
    )
    
    print("\n" + "="*80)
    print(f"[{result['status']}] (Latency: {result['latency_seconds']}s)")
    print(f"ITERATIONS: {result['pivots_taken']} Pivot(s)")
    if result.get("cfo_metrics", {}).get("roi_percentage") is not None:
        metrics = result['cfo_metrics']
        print(f"CFO AUDIT : ROI {metrics['roi_percentage']}% | ROAS {metrics['roas']} | Fragility {metrics['fragility_index']}")
    print(f"CFO QUOTE : '{result['cfo_feedback']}'")
    print("\nFINAL CMO STRATEGY:\n" + result['final_strategy'][:300].replace('\n', ' ') + "...")
    print("="*80 + "\n")
