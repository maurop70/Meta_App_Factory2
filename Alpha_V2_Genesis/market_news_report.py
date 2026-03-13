"""
╔══════════════════════════════════════════════════════════════╗
║  ALPHA V2 GENESIS — MARKET NEWS INTELLIGENCE REPORT        ║
║  Gemini-powered news summary + SPX position impact analysis ║
╚══════════════════════════════════════════════════════════════╝

Generates a structured report with:
  1. Top market-moving headlines with SPX impact analysis
  2. Upcoming economic events with position-specific risk assessment
  3. Confidence-adjusted trade recommendations

Uses Gemini 2.5 Flash via the existing vault_client for API key management.
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


import os, json, logging, time, re
from datetime import datetime
from pathlib import Path

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "Alpha_Data")
REPORT_PATH = os.path.join(DATA, "news_report.json")
PORTFOLIO_PATH = os.path.join(DATA, "portfolio.json")

os.makedirs(DATA, exist_ok=True)

try:
    from vault_client import get_secret
except ImportError:
    def get_secret(key, default="", **kw):
        return os.getenv(key, default)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NewsReport")


def _load_portfolio_context():
    """Loads the current open positions for contextual news analysis."""
    try:
        if not os.path.exists(PORTFOLIO_PATH):
            return None
        with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        positions = [p for p in data.get("positions", []) if p.get("status") == "OPEN"]
        if not positions:
            return None
        # Build a concise summary for the Gemini prompt
        summaries = []
        for p in positions:
            summaries.append(
                f"- {p.get('strategy', 'Iron Condor')} | "
                f"Short Put: {p.get('short_put_strike')} | Short Call: {p.get('short_call_strike')} | "
                f"Long Put: {p.get('long_put_strike')} | Long Call: {p.get('long_call_strike')} | "
                f"Expiry: {p.get('expiration_date')} | Credit: ${p.get('credit_received', p.get('open_price', 'N/A'))}"
            )
        return "\n".join(summaries)
    except Exception as e:
        logger.warning(f"Portfolio context load failed: {e}")
        return None


def _load_market_context():
    """Loads latest market snapshot from server warm-up data."""
    try:
        state_path = os.path.join(
            os.environ.get("ALPHA_RUNTIME_DIR", DATA), "ledger_state.json"
        )
        if os.path.exists(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            return state
    except Exception:
        pass
    return None


def generate_news_report(market_snapshot=None):
    """
    Calls Gemini 2.5 Flash to generate a market news intelligence report.

    Args:
        market_snapshot: dict with spx, vix, iv_rank, etc. (optional)

    Returns:
        dict with structured news report
    """
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found")
        return {"error": "API key not configured", "headlines": [], "events": []}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    # Build context
    portfolio_ctx = _load_portfolio_context()
    now = datetime.now()

    spx_info = ""
    if market_snapshot:
        spx_info = (
            f"Current market data (live):\n"
            f"  SPX: {market_snapshot.get('spx', 'N/A')}\n"
            f"  VIX: {market_snapshot.get('vix', 'N/A')}\n"
            f"  IV Rank: {market_snapshot.get('iv_rank', 'N/A')}%\n"
            f"  5d Trend: {market_snapshot.get('trend_5d', market_snapshot.get('trend_5d_pct', 'N/A'))}%\n"
        )

    position_info = ""
    if portfolio_ctx:
        position_info = f"\nActive positions:\n{portfolio_ctx}\n"

    system_prompt = (
        "You are the Lead Market Intelligence Analyst for Alpha V2 Genesis, "
        "a professional SPX Iron Condor trading system. Your role is to provide "
        "a concise, actionable market news briefing.\n\n"
        "RESPOND WITH VALID JSON ONLY. No markdown, no code fences.\n\n"
        "Required JSON structure:\n"
        "{\n"
        '  "report_title": "Market Intelligence Brief — [DATE]",\n'
        '  "market_regime": "RISK-ON" | "RISK-OFF" | "NEUTRAL" | "TRANSITIONING",\n'
        '  "headlines": [\n'
        "    {\n"
        '      "title": "Headline text",\n'
        '      "source": "Source name",\n'
        '      "summary": "2-3 sentence summary",\n'
        '      "spx_impact": "How this affects SPX price action",\n'
        '      "position_impact": "How this affects current iron condor positions",\n'
        '      "severity": "HIGH" | "MEDIUM" | "LOW"\n'
        "    }\n"
        "  ],\n"
        '  "upcoming_events": [\n'
        "    {\n"
        '      "event": "Event name",\n'
        '      "date": "YYYY-MM-DD",\n'
        '      "time": "HH:MM ET",\n'
        '      "consensus": "Expected value/outcome",\n'
        '      "risk_to_position": "Specific risk to current positions",\n'
        '      "vix_impact": "Expected VIX reaction",\n'
        '      "severity": "HIGH" | "MEDIUM" | "LOW"\n'
        "    }\n"
        "  ],\n"
        '  "trade_recommendation": "1-3 sentence recommendation for current positions",\n'
        '  "key_levels": {\n'
        '    "spx_support": [level1, level2],\n'
        '    "spx_resistance": [level1, level2],\n'
        '    "vix_warning_threshold": number\n'
        "  }\n"
        "}"
    )

    user_prompt = (
        f"Date: {now.strftime('%A, %B %d, %Y')} at {now.strftime('%I:%M %p ET')}\n\n"
        f"{spx_info}\n"
        f"{position_info}\n"
        "Provide your market intelligence briefing covering:\n"
        "1. The 3-5 most important market news stories RIGHT NOW affecting SPX\n"
        "2. Economic events in the next 5 trading days with exact dates and consensus\n"
        "3. Specific impact on my Iron Condor position(s) if any are open\n"
        "4. Key SPX support/resistance levels to watch\n\n"
        "Focus on ACTIONABLE intelligence. Be specific about price levels and risk scenarios."
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": system_prompt + "\n\n" + user_prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
        },
    }

    try:
        logger.info("Generating Market News Intelligence Report via Gemini...")
        _v3_status = healed_post(url, payload)

        resp = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()

        if resp.status_code != 200:
            logger.error(f"Gemini API {resp.status_code}: {resp.text[:300]}")
            return {"error": f"Gemini API error: {resp.status_code}", "headlines": [], "events": []}

        result = resp.json()
        raw_text = (
            result.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        # Strip markdown fences if present
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"```\s*$", "", clean)

        report = json.loads(clean)

        # Add metadata
        report["generated_at"] = now.isoformat()
        report["market_snapshot"] = market_snapshot or {}

        # Persist to disk
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(
            f"News report generated: {len(report.get('headlines', []))} headlines, "
            f"{len(report.get('upcoming_events', []))} events"
        )
        return report

    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned non-JSON: {e}")
        return {"error": "Failed to parse Gemini response", "headlines": [], "events": []}
    except Exception as e:
        logger.error(f"News report generation failed: {e}")
        return {"error": str(e), "headlines": [], "events": []}


def load_cached_report():
    """Load the most recent cached report from disk."""
    try:
        if os.path.exists(REPORT_PATH):
            with open(REPORT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


if __name__ == "__main__":
    # CLI: generate and print the report
    report = generate_news_report()
    print(json.dumps(report, indent=2))

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
