"""
Alpha V2 Genesis — Scraper Self-Healer
========================================
When a ScraperError occurs (e.g. Yahoo Finance changes its HTML structure),
this module uses the Gemini API to re-discover the correct CSS selectors
and caches them for future use.

The Meta_App_Factory log watcher triggers this when it detects ScraperError
in Sentry/error logs.
"""

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


import os
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("alpha.scraper_healer")

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "Alpha_Data"
DATA_DIR.mkdir(exist_ok=True)
SELECTOR_CACHE = DATA_DIR / "selector_cache.json"
HEAL_HISTORY = DATA_DIR / "scraper_heal_history.json"


class ScraperHealer:
    """
    Self-healing engine for web scraper selectors.
    Uses Gemini to re-discover CSS selectors when Yahoo Finance
    changes its page structure.
    """

    # Default selectors (last known good as of 2026-03)
    DEFAULT_SELECTORS = {
        "yahoo_price": {
            "url_pattern": "finance.yahoo.com/quote",
            "selector": "[data-testid='qsp-price']",
            "fallback": "fin-streamer[data-field='regularMarketPrice']",
            "description": "Yahoo Finance real-time price",
        },
        "yahoo_change": {
            "url_pattern": "finance.yahoo.com/quote",
            "selector": "[data-testid='qsp-price-change']",
            "fallback": "fin-streamer[data-field='regularMarketChange']",
            "description": "Yahoo Finance price change",
        },
    }

    def __init__(self):
        self._cache = self._load_cache()

    def heal_scraper(self, url: str, old_selector: str,
                     context: str = "") -> dict:
        """
        Attempt to find a new working CSS selector for a failed scrape.

        Args:
            url: The URL that was being scraped
            old_selector: The CSS selector that stopped working
            context: Additional error context

        Returns:
            dict with keys: new_selector, confidence, source, status
        """
        logger.info("🔧 ScraperHealer: Attempting to heal selector for %s", url)

        result = {
            "url": url,
            "old_selector": old_selector,
            "new_selector": None,
            "confidence": 0.0,
            "source": "none",
            "status": "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Step 1: Check if we have a cached fix for this URL pattern
        cached = self._check_cache(url, old_selector)
        if cached:
            result["new_selector"] = cached["selector"]
            result["confidence"] = cached.get("confidence", 0.8)
            result["source"] = "cache"
            result["status"] = "healed"
            logger.info("✅ Cache hit: %s → %s", old_selector, cached["selector"])
            self._log_heal(result)
            return result

        # Step 2: Check known defaults / fallbacks
        for key, defaults in self.DEFAULT_SELECTORS.items():
            if defaults["url_pattern"] in url and old_selector == defaults["selector"]:
                result["new_selector"] = defaults["fallback"]
                result["confidence"] = 0.6
                result["source"] = "fallback"
                result["status"] = "healed"
                logger.info("↩️ Fallback: %s → %s", old_selector, defaults["fallback"])
                self._update_cache(url, old_selector, defaults["fallback"], 0.6)
                self._log_heal(result)
                return result

        # Step 3: Call Gemini to discover the new selector
        gemini_result = self._ask_gemini(url, old_selector, context)
        if gemini_result:
            result["new_selector"] = gemini_result["selector"]
            result["confidence"] = gemini_result.get("confidence", 0.7)
            result["source"] = "gemini"
            result["status"] = "healed"
            self._update_cache(url, old_selector, gemini_result["selector"],
                               gemini_result.get("confidence", 0.7))
            logger.info("🤖 Gemini: %s → %s (%.0f%%)",
                        old_selector, gemini_result["selector"],
                        gemini_result.get("confidence", 0.7) * 100)
        else:
            result["status"] = "failed"
            result["source"] = "gemini_failed"
            logger.warning("❌ Gemini could not find a replacement selector")

        self._log_heal(result)
        return result

    def get_selector(self, key: str) -> str | None:
        """Get the currently cached selector for a named key."""
        if key in self._cache:
            return self._cache[key].get("selector")
        if key in self.DEFAULT_SELECTORS:
            return self.DEFAULT_SELECTORS[key]["selector"]
        return None

    # ── Gemini API Integration ───────────────────────────────────
    def _ask_gemini(self, url: str, old_selector: str,
                    context: str = "") -> dict | None:
        """Call Gemini API to discover the new CSS selector."""
        try:
            import sys
            sys.path.insert(0, str(SCRIPT_DIR))
            from vault_client import get_secret
        except ImportError:
            logger.warning("vault_client not available — cannot call Gemini")
            return None

        api_key = get_secret("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not found — cannot call Gemini")
            return None

        try:
            prompt = (
                f"The CSS selector `{old_selector}` no longer works on the page "
                f"at `{url}`. The selector was used to extract financial price data "
                f"from Yahoo Finance.\n\n"
                f"Additional context: {context}\n\n"
                f"Based on your knowledge of Yahoo Finance's HTML structure, "
                f"suggest the most likely replacement CSS selector.\n\n"
                f"Return ONLY a JSON object with these keys:\n"
                f"- selector: the new CSS selector string\n"
                f"- confidence: a float 0-1 indicating your confidence\n"
                f"- reasoning: one sentence explaining your choice\n\n"
                f"Return ONLY the raw JSON. No markdown."
            )

            api_url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.5-flash:generateContent?key={api_key}"
            )

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 512,
                },
            }

            _v3_status = healed_post(api_url, payload)


            resp = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
            if resp.status_code != 200:
                logger.warning("Gemini API error: %s", resp.status_code)
                return None

            data = resp.json()
            # Find the text part (skip thought parts from thinking models)
            text = ""
            for part in data["candidates"][0]["content"]["parts"]:
                if "text" in part and not part.get("thought"):
                    text = part["text"]

            if not text:
                text = data["candidates"][0]["content"]["parts"][0]["text"]

            clean = text.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
            return result

        except Exception as e:
            logger.error("Gemini scraper heal failed: %s", e)
            return None

    # ── Cache Management ─────────────────────────────────────────
    def _load_cache(self) -> dict:
        if SELECTOR_CACHE.exists():
            try:
                return json.loads(SELECTOR_CACHE.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        SELECTOR_CACHE.write_text(
            json.dumps(self._cache, indent=2),
            encoding="utf-8"
        )

    def _check_cache(self, url: str, old_selector: str) -> dict | None:
        """Check if we have a cached replacement for this URL+selector combo."""
        cache_key = f"{url}::{old_selector}"
        entry = self._cache.get(cache_key)
        if entry:
            # Verify cache isn't too old (7 days max)
            cached_time = entry.get("cached_at", "")
            if cached_time:
                try:
                    from datetime import datetime, timezone
                    age = (datetime.now(timezone.utc) -
                           datetime.fromisoformat(cached_time))
                    if age.days > 7:
                        del self._cache[cache_key]
                        self._save_cache()
                        return None
                except Exception:
                    pass
            return entry
        return None

    def _update_cache(self, url: str, old_selector: str,
                      new_selector: str, confidence: float):
        cache_key = f"{url}::{old_selector}"
        self._cache[cache_key] = {
            "selector": new_selector,
            "confidence": confidence,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_cache()

    # ── Heal History ─────────────────────────────────────────────
    def _log_heal(self, result: dict):
        history = []
        if HEAL_HISTORY.exists():
            try:
                history = json.loads(HEAL_HISTORY.read_text(encoding="utf-8"))
            except Exception:
                pass
        history.append(result)
        history = history[-100:]  # Keep last 100
        HEAL_HISTORY.write_text(
            json.dumps(history, indent=2),
            encoding="utf-8"
        )

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
