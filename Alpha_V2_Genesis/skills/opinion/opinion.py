import logging
import datetime

# Setup Logging
logger = logging.getLogger("OpinionAgent")

class OpinionAgent:
    def __init__(self):
        logger.info("OpinionAgent Initialized.")

    def evaluate_trade(self, trade_params, n8n_data, market_snapshot):
        """
        Evaluates a specific trade using MMM and Event Context.
        
        Args:
            trade_params (dict): {
                'ticker': 'SPX',
                'expiration': 'YYYY-MM-DD',
                'short_put': float,
                'short_call': float,
                'credit': float,
                'max_risk': float
            }
            n8n_data (dict): Data from N8N (events, forecast).
            market_snapshot (dict): { 'spx': float, 'vix': float, 'mmm': float }
            
        Returns:
            dict: Structured opinion with 'verdict', 'rationale', 'alerts'.
        """
        try:
            current_price = market_snapshot.get('spx')
            mmm = market_snapshot.get('mmm')
            vix = market_snapshot.get('vix')
            
            exp_date_str = trade_params.get('expiration')
            exp_date = datetime.datetime.strptime(exp_date_str, "%Y-%m-%d").date()
            today = datetime.date.today()
            days_to_exp = (exp_date - today).days
            
            short_put = trade_params.get('short_put')
            short_call = trade_params.get('short_call')
            
            opinion = {
                "verdict": "UNKNOWN",
                "rationale": "",
                "safety_checks": [],
                "event_risks": []
            }
            
            # 1. MMM Safety Check (The Golden Rule)
            lower_bound = current_price - mmm
            upper_bound = current_price + mmm
            
            is_put_safe = short_put < lower_bound
            is_call_safe = short_call > upper_bound
            
            put_buffer = round(((lower_bound - short_put) / current_price) * 100, 2)
            call_buffer = round(((short_call - upper_bound) / current_price) * 100, 2)
            
            opinion['safety_checks'].append({
                "type": "MMM_BOUNDS",
                "detail": f"Expected Range (MMM): {int(lower_bound)} - {int(upper_bound)}",
                "status": "PASS" if (is_put_safe and is_call_safe) else "FAIL"
            })
            
            if not is_put_safe:
                opinion['safety_checks'].append({"type": "PUT_RISK", "detail": f"Short Put {short_put} is INSIDE expected move ({int(lower_bound)}). Risk of ITM.", "status": "FAIL"})
            if not is_call_safe:
                opinion['safety_checks'].append({"type": "CALL_RISK", "detail": f"Short Call {short_call} is INSIDE expected move ({int(upper_bound)}). Risk of ITM.", "status": "FAIL"})

            # 2. Event Context Check (The N8N/Serper Input)
            events = n8n_data.get('events', [])
            relevant_events = []
            
            for e in events:
                # Check if event is within the trade duration
                # Assuming 'days_until' is provided by N8N
                evt_days = e.get('days_until', 99)
                if evt_days <= days_to_exp:
                    relevant_events.append(e)
                    opinion['event_risks'].append(f"{e['event']} (in {evt_days} days)")
            
            # 3. Final Verdict Logic
            risk_score = 0
            if not is_put_safe: risk_score += 1
            if not is_call_safe: risk_score += 1
            if len(relevant_events) > 0: risk_score += 1
            
            if risk_score == 0:
                opinion['verdict'] = "APPROVED"
                opinion['rationale'] = "Trade structure is statistically safe (Outside MMM) and clear of major known events."
            elif risk_score == 1 and len(relevant_events) > 0:
                 opinion['verdict'] = "CONDITIONAL"
                 opinion['rationale'] = f"Mathematically Safe (Outside MMM), but Event Risk detected ({', '.join(opinion['event_risks'])}). Proceed only if you accept binary event risk."
            else:
                 opinion['verdict'] = "REJECTED"
                 opinion['rationale'] = "Trade violates safety rules. Either inside MMM bounds or too many risk factors."
                 
            return opinion
            
        except Exception as e:
            logger.error(f"Evaluation Failed: {e}")
            return {"verdict": "ERROR", "rationale": str(e)}

if __name__ == "__main__":
    # Test Stub
    agent = OpinionAgent()
    print("Opinion Agent initialized.")
