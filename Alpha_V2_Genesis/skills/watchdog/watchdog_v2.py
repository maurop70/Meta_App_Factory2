# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

from auto_heal import healed_post, auto_heal, diagnose

def _v3_preflight():
    """V3: Ping Resonance_Watchdog_V3 before execution."""
    if not _V3_AVAILABLE:
        return True
    try:
        import json as _j
        _cfg_path = _os.path.join(_FACTORY_DIR, "resilience_config.json")
        if not _os.path.exists(_cfg_path):
            return True
        with open(_cfg_path) as _f:
            _cfg = _j.load(_f)
        _url = _cfg.get("cloud_health", {}).get("watchdog_url", "")
        if not _url:
            return True
        import requests as _rq
        _r = _rq.get(_url, timeout=5)
        return _r.status_code == 200
    except Exception:
        return False


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
# V3 AUTO-HEAL ACTIVE
