import logging
import json
import os
from datetime import datetime

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WatchdogSkill")

class WatchdogAgent:
    def __init__(self, portfolio_path=None):
        if portfolio_path is None:
            # Fallback path if None
            self.portfolio_path = "portfolio.json"
        else:
            self.portfolio_path = portfolio_path

    def load_portfolio(self):
        """Loads the active trade from JSON."""
        if not os.path.exists(self.portfolio_path):
            return None
        try:
            with open(self.portfolio_path, 'r') as f:
                data = json.load(f)
                
                # Case 1: 'positions' list (New Format)
                if 'positions' in data:
                    for pos in data['positions']:
                        if pos.get('status') == 'OPEN':
                            return pos
                            
                # Case 2: 'active_trade' dict (Legacy Format)
                return data.get('active_trade')
        except Exception as e:
            logger.error(f"Error loading portfolio: {e}")
            return None

    def monitor_position(self, current_spx, vol_forecast_signal, sentiment_signal="NEUTRAL"):
        """
        Analyzes the active trade health.
        """
        trade = self.load_portfolio()
        # Mock trade if missing for verification
        if not trade:
             return {
                 "status": "SAFE",
                 "verdict": "WAIT",
                 "distance_pct": 0,
                 "danger_side": "NONE",
                 "trade_details": None,
                 "message": "No active positions."
             }


        # 1. Calculate Distance to Danger
        short_call = trade.get('short_call_strike', 99999)
        short_put = trade.get('short_put_strike', 0)
        
        dist_call = (short_call - current_spx) / current_spx * 100
        dist_put = (current_spx - short_put) / current_spx * 100
        
        min_dist = min(abs(dist_call), abs(dist_put))
        danger_side = "CALL" if abs(dist_call) < abs(dist_put) else "PUT"
        
        # Calculate DTE (Days to Expiry)
        dte = 7 # Default
        try:
            exp_date = datetime.strptime(trade.get('expiration_date'), "%Y-%m-%d")
            today = datetime.now()
            dte = (exp_date - today).days
        except Exception:
            pass

        # 2. Determine Health
        status = "SAFE"
        verdict = "HOLD"
        reasons = []

        if min_dist < 0.5:
            status = "DANGER"
            verdict = "CLOSE_STOP"
            reasons.append(f"CRITICAL: Price > Strike! Stop Loss.")
        elif min_dist < 1.5:
             status = "WARNING"
             reasons.append("Gamma Risk High.")
        else:
             reasons.append("Monitoring...")

        return {
            "status": status,  # SAFE, WARNING, DANGER
            "verdict": verdict, # HOLD, CLOSE_STOP, CLOSE_RISK, CLOSE_PROFIT
            "distance_pct": round(min_dist, 2),
            "danger_side": danger_side,
            "trade_details": trade,
            "message": " ".join(reasons)
        }

    def _check_mean_reversion(self, distance_pct, dte, current_verdict, mmm_val=None, current_spx=None):
        """
        Stats Check: Mean Reversion & Defensive Roll Logic (Phase 3).
        """
        prob_otm = 80 if abs(distance_pct) > 1.0 else 60 
        
        if abs(distance_pct) >= 1.5 and dte <= 5:
            if prob_otm >= 70:
                return {
                    "override": True,
                    "new_verdict": "HOLD",
                    "message": f"MEAN REVERSION: {distance_pct:.2f}% dist has {prob_otm}% OTM probability (>70%). Forcing HOLD."
                }
        
        if current_verdict in ["CLOSE_Stop", "CLOSE_RISK", "DANGER"] and prob_otm < 70:
             msg = f"MEAN REVERSION: Prob {prob_otm}% (<70%). Recommend Defensive Roll."
             if mmm_val and current_spx:
                 upper = current_spx + mmm_val
                 lower = current_spx - mmm_val
                 msg += f" MUST be outside MMM Range [${lower:.0f} - ${upper:.0f}]."
                 
             return {
                "override": False, 
                "new_verdict": current_verdict,
                "message": msg
            }

        return None
