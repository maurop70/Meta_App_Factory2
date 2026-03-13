# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
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


import yfinance as yf
import time
import logging
import os
import sys

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - VolSentry - %(levelname)s - %(message)s')
logger = logging.getLogger("Sentry")

def monitor_vix():
    logger.info("🛡️ Volatility Sentry Armed. Monitoring ^VIX...")
    last_vix = None
    
    while True:
        try:
            vix_data = yf.Ticker("^VIX").history(period="1d")
            if not vix_data.empty:
                current_vix = vix_data['Close'].iloc[-1]
                
                if last_vix is not None:
                    change = current_vix - last_vix
                    if change > 1.0:
                        logger.warning(f"⚠️ VOLATILITY SPIKE: VIX jumped +{change:.2f} to {current_vix:.2f}")
                        # In a real environment, this would trigger an alert sound or popup
                
                logger.info(f"VIX Level: {current_vix:.2f}")
                last_vix = current_vix
        except Exception as e:
            logger.error(f"Sentry Error: {e}")
            
        time.sleep(300) # Check every 5 minutes

if __name__ == "__main__":
    monitor_vix()
# V3 AUTO-HEAL ACTIVE
