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
# V3 AUTO-HEAL ACTIVE
