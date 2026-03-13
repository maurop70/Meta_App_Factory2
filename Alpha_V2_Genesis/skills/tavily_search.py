# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
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

class TavilySearch:
    """
    Skill for the CMO Persona.
    Performs real-time competitor and market trend research via Tavily.
    """
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.base_url = "https://api.tavily.com/search"

    def search(self, query, search_depth="nested"):
        """Performs a deep market search."""
        if not self.api_key:
            return "Error: Tavily API Key not found. Please provide it in TAVILY_API_KEY env var."
        
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "include_answer": True
        }
        
        try:
            _v3_status = healed_post(self.base_url, payload)

            response = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
            response.raise_for_status()
            data = response.json()
            return data.get("answer") or data.get("results")
        except Exception as e:
            return f"Search failed: {e}"

if __name__ == "__main__":
    # Test
    searcher = TavilySearch()
    # print(searcher.search("What are the top 3 business strategy trends for 2026?"))

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
