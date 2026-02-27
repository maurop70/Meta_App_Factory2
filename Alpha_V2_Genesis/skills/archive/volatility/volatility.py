import pandas as pd
import numpy as np
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("VolatilitySkill")

class VolatilityAgent:
    def __init__(self):
        pass

    def analyze_vix_rank(self, vix_current, vix_history_df):
        """
        Calculates the 30-Day VIX Rank.
        Formula: (Current - Low) / (High - Low)
        """
        if vix_history_df.empty:
            logger.warning("No VIX history provided.")
            return None

        # Ensure we look at last 30 periods
        # Assuming the DF is daily closes
        lookback = 30
        recent_data = vix_history_df.tail(lookback)
        
        low_30 = recent_data['Close'].min()
        high_30 = recent_data['Close'].max()
        
        if high_30 == low_30:
            return 0.0
            
        rank = (vix_current - low_30) / (high_30 - low_30)
        return round(rank * 100, 2) # Return as 0-100 score

    def get_signal(self, iv_rank):
        """Returns the strategic signal based on IV Rank."""
        if iv_rank is None:
            return {"action": "WAIT", "reason": "Insufficient Data"}
            
        if iv_rank < 20:
            return {
                "action": "BUY_PREMIUM", 
                "reason": f"Volatility is CHEAP (Rank {iv_rank}). Expect expansion."
            }
        elif iv_rank < 50:
             return {
                "action": "HOLD", 
                "reason": f"Volatility is NORMAL (Rank {iv_rank})."
            }
        elif iv_rank < 80:
             return {
                "action": "SELL_PREMIUM", 
                "reason": f"Volatility is EXPENSIVE (Rank {iv_rank}). Expect mean reversion."
            }
        else:
             return {
                "action": "WAIT", 
                "reason": f"Volatility is EXTREME (Rank {iv_rank}). Risk of spike."
            }

    def forecast_volatility(self, current_vix, history_df):
        """
        Predicts if Volatility will RISE or FALL tomorrow based on Mean Reversion.
        """
        if history_df.empty: return "UNKNOWN"
        
        # Simple Mean Reversion Logic
        # Calculate 30-day Mean
        mean_30 = history_df['Close'].tail(30).mean()
        
        # Distance from Mean
        diff = current_vix - mean_30
        
        # Thresholds
        if diff > 2.0:
            return "FALLING" # VIX is way above mean, expect drop
        elif diff < -2.0:
            return "RISING" # VIX is way below mean, expect spike
        else:
            return "STABLE"

    def analyze_market(self, vix_current, vix_history):
        """Main entry point for the agent."""
        rank = self.analyze_vix_rank(vix_current, vix_history)
        signal = self.get_signal(rank)
        forecast = self.forecast_volatility(vix_current, vix_history)
        
        return {
            "vix_current": vix_current,
            "vix_rank_30d": rank,
            "signal": signal["action"],
            "forecast": forecast,
            "rationale": f"{signal['reason']} Forecast: {forecast}."
        }

if __name__ == "__main__":
    # Test with Mock Data
    print("... Testing Volatility Agent ...")
    agent = VolatilityAgent()
    
    # Mock History: VIX trending up from 12 to 18
    dates = pd.date_range(start='2024-01-01', periods=30)
    values = np.linspace(12, 18, 30)
    mock_df = pd.DataFrame({'Close': values}, index=dates)
    
    current_vix = 16.5
    
    result = agent.analyze_market(current_vix, mock_df)
    print(f"Result: {result}")
