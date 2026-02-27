import logging

logger = logging.getLogger("SentimentSkill")

class SentimentAgent:
    def __init__(self):
        self.tail_events = self._load_catalyst_db()

    def _load_catalyst_db(self):
        logger.info("Using embedded default Catalyst Database.")
        return [
            {"keyword": "saaspocalypse", "drawdown_pct": 5.2, "description": "SaaS Sector Crash 2022"},
            {"keyword": "kevin warsh", "drawdown_pct": 0.5, "description": "Nomination rumors (Low Impact)"},
            {"keyword": "fed transition", "drawdown_pct": 5.0, "description": "Barclays Fed Transition Study (Month-1 Risk)"}
        ]

    def analyze_headlines(self, headlines):
        score = 0
        details = []
        multiplier = 1.0
        override_bias = None
        
        if not headlines:
            headlines = [
                {"title": "Kevin Warsh nomination likely for Fed"},
                {"title": "NFP Report due in 2 days, volatility expected"},
                {"title": "Tech sector fears SaaSpocalypse 2.0"},
                {"title": "Uncertainty grows around Fed transition"} 
            ]
            details.append("(Using Simulated Alpha Sentiment Feeds)")

        for item in headlines:
            text = item.get('title', '') if isinstance(item, dict) else str(item)
            text_lower = text.lower()
            
            # Historical Catalysts
            for event in self.tail_events:
                if event['keyword'] in text_lower:
                    if event['drawdown_pct'] >= 5.0:
                        override_bias = "BEARISH"
                        details.append(f"⚠️ HISTORICAL CATALYST MATCH: '{event['keyword']}' (Past Drawdown: -{event['drawdown_pct']}%) -> Force Bearish.")
                    elif event['drawdown_pct'] > 2.0:
                        override_bias = "BEARISH"
                        details.append(f"Catalyst Match: '{event['keyword']}' (Med Impact). Force Bearish.")
            
            if "fed" in text_lower and ("nomination" in text_lower or "transition" in text_lower):
                score -= 0.5
                details.append("Fed Leadership Shift (Chair Appointment in May) (-0.5)")
                
            if "nfp" in text_lower:
                 multiplier = 1.5
                 details.append("NFP Detected (Volatility Multiplier set to 1.5x)")

        final_bias = "NEUTRAL"
        if override_bias:
            final_bias = override_bias
            details.append(f"Bias OVERRIDDEN to {override_bias} by Catalyst Logic.")
        elif score < -0.3:
            final_bias = "BEARISH"
        elif score > 0.3:
            final_bias = "BULLISH"
            
        return {
            "bias": final_bias,
            "score": score,
            "volatility_multiplier": multiplier,
            "narrative": "; ".join(details)
        }
