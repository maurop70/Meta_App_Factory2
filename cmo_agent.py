"""
cmo_agent.py — CMO Intelligence Agent V3 (Live Fire)
═════════════════════════════════════════════════════
Market intelligence via Gemini 2.5 Pro Function Calling.

Search backend: DuckDuckGo HTML scraper (requests + BeautifulSoup, no API key)
Resilience:     generate_with_backoff_sync wraps every HTTP call.
Fallback:       Deterministic hash-seeded simulation if scraper or API fails.
"""

import os
import json
import hashlib
import random
import requests
import logging
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError
from ai_utils import generate_with_backoff_sync
from agent_base import AgentBase, ProvenanceClaim

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# PYDANTIC OUTPUT SCHEMA (strict validation of Gemini's JSON response)
# ─────────────────────────────────────────────────────────────────────────────

class CMOGeminiOutput(BaseModel):
    """
    Strict Pydantic schema for the CMO Gemini output.
    Validation failure routes to _fallback_sentiment with confidence=0.0,
    guaranteeing the Hallucination Gate catches it.
    """
    verdict: str
    trend_velocity: float
    public_sentiment_score: float
    summary: str
    sources: list[str] = []


_DDG_URL = "https://html.duckduckgo.com/html/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ─────────────────────────────────────────────────────────────────────────────
# NATIVE PYTHON TOOLS (declared to Gemini 2.5 Pro via function calling)
# ─────────────────────────────────────────────────────────────────────────────

def search_market_sentiment(query: str) -> dict:
    """
    Searches DuckDuckGo for real-world market sentiment, industry trends,
    and analyst commentary on a business topic. No API key required.

    Args:
        query: Market or technology topic
            (e.g. 'on-premise AI hardware enterprise 2025 market growth')

    Returns:
        dict with keys: query, results (list of {title, snippet, url}), source, count
    """
    def _fetch():
        resp = requests.post(
            _DDG_URL,
            data={"q": query + " market trend analysis 2025", "b": ""},
            headers=_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        return resp

    try:
        # Wrapped in backoff to handle DuckDuckGo rate-limiting (429) gracefully
        resp = generate_with_backoff_sync(
            _fetch,
            max_api_retries=3,
            base_delay=2.0,
            backoff_factor=2.0,
        )

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        for block in soup.select(".result__body")[:7]:
            title_el = block.select_one(".result__title")
            snippet_el = block.select_one(".result__snippet")
            url_el = block.select_one(".result__url")
            title = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            url = url_el.get_text(strip=True) if url_el else ""
            if title:
                results.append({"title": title, "snippet": snippet, "url": url})

        logger.info(f"[CMO Agent] DDG market search → {len(results)} results for: {query!r}")
        return {"query": query, "results": results, "source": "DuckDuckGo", "count": len(results)}

    except Exception as e:
        logger.warning(f"[CMO Agent] search_market_sentiment failed: {e}")
        return {"query": query, "error": str(e), "results": [], "source": "DuckDuckGo", "count": 0}


def search_competitor_landscape(market_segment: str) -> dict:
    """
    Searches DuckDuckGo for competitor positioning, market leaders,
    and emerging threats within a specific market segment.

    Args:
        market_segment: Market segment to research
            (e.g. 'enterprise AI hardware appliances competitors 2025')

    Returns:
        dict with keys: segment, results (list of {title, snippet, url}), source, count
    """
    def _fetch():
        resp = requests.post(
            _DDG_URL,
            data={"q": market_segment + " competitors market leaders enterprise 2025", "b": ""},
            headers=_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        return resp

    try:
        resp = generate_with_backoff_sync(
            _fetch,
            max_api_retries=3,
            base_delay=2.0,
            backoff_factor=2.0,
        )

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        for block in soup.select(".result__body")[:7]:
            title_el = block.select_one(".result__title")
            snippet_el = block.select_one(".result__snippet")
            url_el = block.select_one(".result__url")
            title = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            url = url_el.get_text(strip=True) if url_el else ""
            if title:
                results.append({"title": title, "snippet": snippet, "url": url})

        logger.info(f"[CMO Agent] DDG competitor search → {len(results)} results for: {market_segment!r}")
        return {"segment": market_segment, "results": results, "source": "DuckDuckGo", "count": len(results)}

    except Exception as e:
        logger.warning(f"[CMO Agent] search_competitor_landscape failed: {e}")
        return {"segment": market_segment, "error": str(e), "results": [], "source": "DuckDuckGo", "count": 0}


# ─────────────────────────────────────────────────────────────────────────────
# CMO AGENT MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_cmo_analysis(intent: str) -> dict:
    """
    Live CMO market intelligence analysis using Gemini 2.5 Pro Function Calling.
    Called via asyncio.to_thread() from native_sequence().

    Returns a dict compatible with the market_pulse interface:
      { verdict, trend_velocity, public_sentiment_score, summary, sources, live_data }
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("[CMO Agent] GEMINI_API_KEY missing — using deterministic fallback.")
        return _fallback_sentiment(intent, error="GEMINI_API_KEY missing")

    client = genai.Client(api_key=api_key)

    prompt = f"""You are the Chief Marketing Officer of the Antigravity AI platform.

The Commander has issued this strategic directive:
"{intent}"

Your mission: Evaluate REAL MARKET CONDITIONS for this strategy using your search tools.

REQUIRED STEPS:
1. Call search_market_sentiment with a focused query derived from the intent
2. Call search_competitor_landscape with the primary market segment identified
3. Synthesize ONLY what the search results actually report — do not fabricate data

Based strictly on what the search results show, return a JSON object:
{{
    "verdict": "BULLISH" or "BEARISH" or "NEUTRAL",
    "trend_velocity": <float 1.0-10.0 based on actual search signals>,
    "public_sentiment_score": <float -100.0 to 100.0 based on actual signals>,
    "summary": "<CMO synthesis — 2-3 sentences citing actual search findings>",
    "sources": ["<article title or domain 1>", "<article title or domain 2>", ...]
}}

Scoring guide:
- trend_velocity > 7 only if results show explicit explosive growth signals
- public_sentiment_score < -30 if results show significant negative press
- Default to NEUTRAL if signals are mixed or results are sparse

Return only valid JSON. No markdown fences.
"""

    tools = [search_market_sentiment, search_competitor_landscape]

    try:
        response = generate_with_backoff_sync(
            client.models.generate_content,
            model="gemini-2.5-pro",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False),
            ),
        )

        raw = response.text.strip().replace("```json", "").replace("```", "").strip()

        try:
            parsed = CMOGeminiOutput(**json.loads(raw))
        except (ValidationError, json.JSONDecodeError, ValueError) as ve:
            logger.error(f"[CMO Agent] Pydantic validation failed: {ve}")
            # confidence=0.0 forces [SIMULATED] citation path in CMOAgent._attach_provenance
            return _fallback_sentiment(intent, error=f"Pydantic validation: {ve}")

        result = {
            "verdict": parsed.verdict.upper(),
            "trend_velocity": parsed.trend_velocity,
            "public_sentiment_score": parsed.public_sentiment_score,
            "summary": parsed.summary,
            "sources": parsed.sources,
            "live_data": True,
        }
        logger.info(
            f"[CMO Agent] Live analysis: {result['verdict']} | "
            f"velocity={result['trend_velocity']} | sentiment={result['public_sentiment_score']}"
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[CMO Agent] JSON parse failed: {e}")
        return _fallback_sentiment(intent, error=f"JSON parse error: {e}")
    except Exception as e:
        logger.error(f"[CMO Agent] Gemini call failed: {e}")
        return _fallback_sentiment(intent, error=str(e))


def _fallback_sentiment(intent: str, error: str = None) -> dict:
    """
    Deterministic fallback. Uses a stable hash of the intent — not a random
    dice roll — so retries produce consistent results.
    """
    seed = int(hashlib.md5(intent.encode()).hexdigest()[:8], 16)
    random.seed(seed)
    velocity = round(random.uniform(3.5, 7.5), 1)
    sentiment = round(random.uniform(-40.0, 60.0), 1)
    verdict = (
        "BULLISH" if velocity > 6.5 and sentiment > 20
        else "BEARISH" if velocity < 4.0 and sentiment < -20
        else "NEUTRAL"
    )
    random.seed()
    note = f" [Error: {error}]" if error else ""
    return {
        "verdict": verdict,
        "trend_velocity": velocity,
        "public_sentiment_score": sentiment,
        "summary": f"[SIMULATED — live search unavailable{note}]",
        "sources": [],
        "live_data": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PROVENANCE WRAPPER
# ─────────────────────────────────────────────────────────────────────────────

class CMOAgent(AgentBase):
    """AgentBase subclass that attaches UDPP provenance to CMO analysis output."""
    AGENT_ID = "cmo"

    def run(self, intent: str) -> dict:
        result = run_cmo_analysis(intent)
        return self._attach_provenance(result)

    def _attach_provenance(self, result: dict) -> dict:
        """Build and attach the _provenance sidecar based on live_data flag."""
        if result.get("live_data"):
            # Source: DuckDuckGo HTML endpoint (the actual POST destination used by both tools)
            citation = "https://html.duckduckgo.com/html/ [DuckDuckGo HTML Search]"
            tool = "web_search"
            confidence_score = 0.70  # scrape-quality, model-synthesized
        else:
            # Simulation or error — citation will trigger Hallucination Gate FAIL
            err_note = result.get("summary", "")
            citation = f"[SIMULATED — no live data: {err_note[:80]}]"
            tool = "fallback_simulation"
            confidence_score = 0.0

        provenance = self.build_provenance_block({
            "verdict": ProvenanceClaim.build(
                result.get("verdict"), citation, tool, confidence_score),
            "trend_velocity": ProvenanceClaim.build(
                result.get("trend_velocity"), citation, tool, confidence_score * 0.90),
            "public_sentiment_score": ProvenanceClaim.build(
                result.get("public_sentiment_score"), citation, tool, confidence_score * 0.90),
            "summary": ProvenanceClaim.build(
                result.get("summary"), citation, tool, confidence_score),
        })

        return self.merge_into_output(result, provenance)


if __name__ == "__main__":
    import sys
    test_intent = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "Migrate Antigravity to 100% on-premise AI hardware sold to Enterprise clients."
    )
    agent = CMOAgent()
    print(json.dumps(agent.run(test_intent), indent=2))
