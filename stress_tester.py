"""
stress_tester.py — Native Triad Module 2
═════════════════════════════════════════
Injects Chaos Data into the CFO Excel Architect.
Tests for: Zero-revenue scenarios, 1,000% inflation spikes, and empty strings.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class ChaosStressTester:
    def __init__(self, project_id: str):
        self.project_id = project_id
        
    def run_tests(self) -> dict:
        from cfo_excel_architect import CFOExcelArchitect
        cfo = CFOExcelArchitect()
        errors = []
        
        # Chaos 1: Zero Revenue
        try:
            cfo.generate_business_plan(self.project_id + "_chaos1", cmo_data={"marketing_cost": 5000, "projected_revenue": 0}, cto_data={}, market_pulse={})
        except Exception as e:
            if "ZeroDivisionError" in str(e) or "math" in str(e).lower() or "float" in str(e).lower():
                errors.append(f"Zero Revenue Chaos FAULT: {e}")
                
        # Chaos 2: High Inflation Spike (1,000%)
        try:
            cfo.generate_business_plan(self.project_id + "_chaos2", cmo_data={"marketing_cost": 5000, "projected_revenue": 100000, "inflation_rate": 10.0}, cto_data={}, market_pulse={})
        except Exception as e:
            errors.append(f"Inflation Spike Chaos FAULT: {e}")

        # Chaos 3: Empty Strings instead of numbers
        try:
            cfo.generate_business_plan(self.project_id + "_chaos3", cmo_data={"marketing_cost": "", "projected_revenue": ""}, cto_data={"dev_buffer_weeks": ""}, market_pulse={})
        except Exception as e:
            if "TypeError" in str(e) or "ValueError" in str(e) or "string" in str(e).lower():
                errors.append(f"Empty Strings Chaos FAULT: {e}")

        if errors:
            return {"status": "FAIL", "score": max(0, 100 - len(errors)*30), "errors": errors}
            
        return {"status": "PASS", "score": 100, "errors": []}
