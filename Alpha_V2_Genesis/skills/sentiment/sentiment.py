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

import json
import datetime
import yfinance as yf
from dotenv import load_dotenv

try:
    import google.generativeai as genai
except ImportError:
    genai = None

class SentimentAgent:
    def __init__(self):
        # Setup Cache Directory
        project_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
        self.cache_file = _os.path.join(project_root, "Alpha_Data", "sentiment_cache.json")
        self.cache_duration_hours = 0.5

        # Init Gemini locally
        load_dotenv()
        self.api_key = _os.getenv("GEMINI_API_KEY")
        if self.api_key and genai:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"response_mime_type": "application/json"})
        else:
            logger.error("GEMINI_API_KEY or genai dependency not found!")
            self.model = None

    def _load_cache(self):
        if _os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
                    
                cached_time = datetime.datetime.fromisoformat(cache.get("timestamp", "2000-01-01T00:00:00"))
                if (datetime.datetime.now() - cached_time).total_seconds() < (self.cache_duration_hours * 3600):
                    logger.info("Using cached Native Sentiment Analysis.")
                    data = cache.get("data")
                    if isinstance(data, dict):
                        data["cache_status"] = "CACHED"
                    return data
            except Exception as e:
                logger.error(f"Failed to load sentiment cache: {e}")
        return None

    def _save_cache(self, data):
        try:
            _os.makedirs(_os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump({
                    "timestamp": datetime.datetime.now().isoformat(),
                    "data": data
                }, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to write sentiment cache: {e}")

    def fetch_market_news(self, ticker="^SPX"):
        """Scrapes Top 10 headlines using yfinance."""
        try:
            tk = yf.Ticker(ticker)
            news = tk.news
            if not news:
                return []
            headlines = []
            for item in news[:10]:
                content = item.get('content', item) # fallback to root for legacy compat
                title = content.get('title', '')
                provider = content.get('provider', {})
                publisher = provider.get('displayName', '') or item.get('publisher', 'Unknown')
                if title:
                    headlines.append(f"[{publisher}] {title}")
            return headlines
        except Exception as e:
            logger.error(f"News fetch failed: {e}")
            return []

    def analyze_headlines(self, headlines=None):
        """Native Intelligence Pipeline: yfinance -> Gemini -> Cache"""
        # 1. Try Cache
        cached = self._load_cache()
        if cached:
            return cached

        # 2. Fetch News if not provided or empty
        if not headlines:
             headlines = self.fetch_market_news("^SPX")
             
        if not headlines:
             return {
                "bias": "NEUTRAL",
                "score": 0.0,
                "volatility_multiplier": 1.0,
                "narrative": "News scraper returned no results. Defaulting to NEUTRAL."
             }

        # 3. Process with Gemini
        logger.info(f"Synthesizing {len(headlines)} headlines natively via Gemini...")
        fallback_result = {
            "bias": "NEUTRAL",
            "score": 0.0,
            "volatility_multiplier": 1.0,
            "narrative": "Native Intelligence Engine offline (API Error). Defaulting to NEUTRAL."
        }

        if not self.model:
             return fallback_result

        prompt = f"""
        System Instruction: You are a quantitative market analyst determining the short-term directional bias for the S&P 500 (^SPX).
        Analyze the following recent market headlines for SPX. Return ONLY a JSON object. Bias must be a single word (BULLISH, BEARISH, or NEUTRAL). Do not include markdown formatting like ```json.
        
        Headlines:
        {json.dumps(headlines, indent=2)}

        Required Output JSON Schema:
        {{
            "bias": "BULLISH" | "BEARISH" | "NEUTRAL",
            "score": <float between -1.0 (very bearish) and 1.0 (very bullish)>,
            "volatility_multiplier": <float (e.g., 1.0 for normal, 1.5 for high fear events)>,
            "narrative": "<A strong 1-2 sentence explanation>"
        }}
        """

        try:
             response = self.model.generate_content(prompt)
             result_text = response.text
             result_text = result_text.strip().removeprefix("```json").removesuffix("```").strip()
             result = json.loads(result_text)
             
             # Validation
             bias = result.get('bias', 'NEUTRAL')
             if bias not in ["BULLISH", "BEARISH", "NEUTRAL"]:
                 bias = "NEUTRAL"
                 
             final_data = {
                 "bias": bias,
                 "score": float(result.get('score', 0.0)),
                 "volatility_multiplier": float(result.get('volatility_multiplier', 1.0)),
                 "narrative": result.get('narrative', 'Native AI Synthesis Complete.'),
                 "cache_status": "FRESH"
             }
             
             # 4. Save to Cache
             self._save_cache(final_data)
             return final_data

        except Exception as e:
             logger.error(f"Gemini API failure during sentiment synthesis: {e}")
             return fallback_result
# V3 AUTO-HEAL ACTIVE
