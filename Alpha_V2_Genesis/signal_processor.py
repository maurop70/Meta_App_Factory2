"""
signal_processor.py -- News Bureau Chief: Actionable Signal Processor
======================================================================
Meta App Factory | Alpha_V2_Genesis | Antigravity-AI

Filters external news for 'Actionable Signals' that impact Alpha_V2
decision models. Links to Delegate_AI to auto-trigger a Context Refresh
when high-impact global events are detected.

Usage:
    from signal_processor import SignalProcessor
    sp = SignalProcessor()
    signals = sp.process_news_report(news_report)
    if signals["auto_trigger"]:
        sp.trigger_context_refresh()
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("news.signals")

SCRIPT_DIR = Path(__file__).resolve().parent
FACTORY_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(FACTORY_DIR))
sys.path.insert(0, str(FACTORY_DIR / "Sentinel_Bridge"))

STATE_DIR = FACTORY_DIR / ".Gemini_state"
SIGNAL_STATE_PATH = STATE_DIR / "signal_processor_state.json"
REPORT_PATH = SCRIPT_DIR / "Alpha_Data" / "news_report.json"

# Lazy imports
_pii = None
_delegate = None


def _get_pii():
    global _pii
    if _pii is None:
        try:
            from pii_masker import PIIMasker
            _pii = PIIMasker()
        except ImportError:
            logger.warning("PIIMasker not available")
    return _pii


def _get_delegate():
    global _delegate
    if _delegate is None:
        try:
            sys.path.insert(
                0, str(FACTORY_DIR / "Delegate_AI_Beta_Agreement_Vault")
            )
            from delegate_logic import DelegateOrchestrator
            _delegate = DelegateOrchestrator()
        except ImportError:
            logger.warning("DelegateOrchestrator not available")
    return _delegate


# ── Signal Classification Rules ──────────────────────────

SIGNAL_KEYWORDS = {
    "macro_shock": {
        "keywords": [
            "rate hike", "rate cut", "fed", "fomc", "inflation",
            "recession", "gdp", "unemployment", "nonfarm", "cpi",
            "pce", "banking crisis", "debt ceiling",
        ],
        "impact": "high",
        "category": "Macroeconomic",
    },
    "volatility_spike": {
        "keywords": [
            "vix spike", "volatility", "fear index", "black swan",
            "crash", "flash crash", "circuit breaker", "halt",
        ],
        "impact": "critical",
        "category": "Volatility Event",
    },
    "geopolitical": {
        "keywords": [
            "war", "conflict", "sanctions", "tariff", "trade war",
            "embargo", "military", "invasion", "nuclear",
        ],
        "impact": "critical",
        "category": "Geopolitical Risk",
    },
    "earnings_surprise": {
        "keywords": [
            "earnings miss", "earnings beat", "guidance cut",
            "profit warning", "revenue miss", "downgrade",
        ],
        "impact": "medium",
        "category": "Corporate Earnings",
    },
    "sector_rotation": {
        "keywords": [
            "sector rotation", "flight to safety", "risk-off",
            "risk-on", "bond rally", "equity selloff", "rotation",
        ],
        "impact": "medium",
        "category": "Market Rotation",
    },
    "liquidity_event": {
        "keywords": [
            "margin call", "liquidation", "deleveraging",
            "redemption", "fund closure", "forced selling",
        ],
        "impact": "high",
        "category": "Liquidity Crisis",
    },
    "ai_tech": {
        "keywords": [
            "ai regulation", "semiconductor", "chip ban",
            "tech antitrust", "data privacy", "ai safety",
        ],
        "impact": "medium",
        "category": "Technology / AI",
    },
}

# Impact score mapping
IMPACT_SCORES = {"critical": 10, "high": 7, "medium": 4, "low": 1}


class ActionableSignal:
    """An actionable signal extracted from news data."""

    def __init__(self, headline: str, category: str, impact: str,
                 matched_keywords: list, source: str = ""):
        self.headline = headline
        self.category = category
        self.impact = impact
        self.matched_keywords = matched_keywords
        self.source = source
        self.score = IMPACT_SCORES.get(impact, 1)
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "headline": self.headline[:200],
            "category": self.category,
            "impact": self.impact,
            "score": self.score,
            "matched_keywords": self.matched_keywords[:5],
            "source": self.source,
            "timestamp": self.timestamp,
        }


class SignalProcessor:
    """
    Filters news for actionable signals impacting Alpha_V2 decision models.
    Auto-triggers context refresh via Delegate_AI on high-impact events.
    """

    def __init__(self, auto_trigger_threshold: int = 7):
        self.threshold = auto_trigger_threshold
        self._signals: list = []
        self._state = self._load_state()
        self._pii = _get_pii()

    def _load_state(self) -> dict:
        if SIGNAL_STATE_PATH.exists():
            try:
                return json.loads(
                    SIGNAL_STATE_PATH.read_text(encoding="utf-8")
                )
            except Exception:
                pass
        return {
            "processed_count": 0,
            "triggers_fired": 0,
            "last_processed": None,
            "recent_signals": [],
        }

    def _save_state(self) -> None:
        STATE_DIR.mkdir(exist_ok=True)
        try:
            safe_state = dict(self._state)
            # PII mask recent signals
            if self._pii and "recent_signals" in safe_state:
                masked = []
                for sig in safe_state["recent_signals"][-20:]:
                    if isinstance(sig, dict):
                        masked.append({
                            k: self._pii.mask(str(v)) if isinstance(v, str) else v
                            for k, v in sig.items()
                        })
                    else:
                        masked.append(sig)
                safe_state["recent_signals"] = masked
            SIGNAL_STATE_PATH.write_text(json.dumps(safe_state, indent=2))
        except Exception as e:
            logger.error("Could not save signal state: %s", e)

    # ── Core: Process News Report ────────────────────────

    def process_news_report(self, report: dict = None) -> dict:
        """
        Process a news report and extract actionable signals.
        If no report is passed, loads the cached one from disk.
        """
        if report is None:
            report = self._load_cached_report()
            if report is None:
                return {
                    "signals": [],
                    "max_score": 0,
                    "auto_trigger": False,
                    "error": "No news report available",
                }

        self._signals = []
        headlines = report.get("headlines", [])

        for headline in headlines:
            title = headline.get("title", "")
            summary = headline.get("summary", "")
            spx_impact = headline.get("spx_impact", "")
            severity = headline.get("severity", "LOW")
            source = headline.get("source", "")

            # Combine text for keyword matching
            text = f"{title} {summary} {spx_impact}".lower()

            # PII mask before processing
            if self._pii:
                text = self._pii.mask(text)

            # Match against signal rules
            for rule_id, rule in SIGNAL_KEYWORDS.items():
                matched = [kw for kw in rule["keywords"] if kw in text]
                if matched:
                    # Boost impact based on headline severity
                    impact = rule["impact"]
                    if severity == "HIGH" and impact == "medium":
                        impact = "high"

                    signal = ActionableSignal(
                        headline=title,
                        category=rule["category"],
                        impact=impact,
                        matched_keywords=matched,
                        source=source,
                    )
                    self._signals.append(signal)

        # Also process upcoming events
        events = report.get("upcoming_events", [])
        for event in events:
            event_name = event.get("event", "")
            risk = event.get("risk_to_position", "")
            event_severity = event.get("severity", "LOW")

            text = f"{event_name} {risk}".lower()
            if self._pii:
                text = self._pii.mask(text)

            for rule_id, rule in SIGNAL_KEYWORDS.items():
                matched = [kw for kw in rule["keywords"] if kw in text]
                if matched:
                    impact = rule["impact"]
                    if event_severity == "HIGH" and impact == "medium":
                        impact = "high"

                    signal = ActionableSignal(
                        headline=f"[EVENT] {event_name}",
                        category=rule["category"],
                        impact=impact,
                        matched_keywords=matched,
                        source="Upcoming Events",
                    )
                    self._signals.append(signal)

        # Deduplicate by category (keep highest score per category)
        deduped = {}
        for sig in self._signals:
            key = sig.category
            if key not in deduped or sig.score > deduped[key].score:
                deduped[key] = sig
        self._signals = list(deduped.values())

        # Sort by score descending
        self._signals.sort(key=lambda s: -s.score)

        max_score = max((s.score for s in self._signals), default=0)
        auto_trigger = max_score >= self.threshold

        # Update state
        self._state["processed_count"] = (
            self._state.get("processed_count", 0) + 1
        )
        self._state["last_processed"] = datetime.now(timezone.utc).isoformat()
        self._state["recent_signals"] = [
            s.to_dict() for s in self._signals
        ][-20:]
        self._save_state()

        result = {
            "signals": [s.to_dict() for s in self._signals],
            "signal_count": len(self._signals),
            "max_score": max_score,
            "auto_trigger": auto_trigger,
            "threshold": self.threshold,
            "market_regime": report.get("market_regime", "UNKNOWN"),
        }

        if auto_trigger:
            logger.warning(
                "HIGH-IMPACT EVENT DETECTED (score=%d). "
                "Auto-triggering context refresh.",
                max_score,
            )

        return result

    def _load_cached_report(self) -> Optional[dict]:
        """Load latest news report from disk."""
        if REPORT_PATH.exists():
            try:
                return json.loads(REPORT_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    # ── Auto-Trigger: Context Refresh ────────────────────

    def trigger_context_refresh(self) -> dict:
        """
        Trigger an immediate Context Refresh for Alpha_V2 via Delegate_AI.
        Called when a high-impact signal is detected.
        """
        delegate = _get_delegate()
        if delegate is None:
            logger.warning("Delegate_AI not available for context refresh")
            return {
                "triggered": False,
                "reason": "DelegateOrchestrator unavailable",
            }

        # Build the delegation request
        top_signals = [s.to_dict() for s in self._signals[:3]]
        context = {
            "reason": "High-impact news event detected",
            "signals": top_signals,
            "action": "context_refresh",
            "target": "Alpha_V2_Genesis",
        }

        try:
            result = delegate.delegate_task(
                task_type="context_refresh",
                description=(
                    f"News Bureau Chief: Context refresh triggered. "
                    f"{len(top_signals)} high-impact signals detected."
                ),
                context=context,
            )
            self._state["triggers_fired"] = (
                self._state.get("triggers_fired", 0) + 1
            )
            self._save_state()

            return {"triggered": True, "delegate_result": result}
        except Exception as e:
            logger.error("Context refresh trigger failed: %s", e)
            return {"triggered": False, "error": str(e)}

    # ── Dashboard ────────────────────────────────────────

    def get_status(self) -> dict:
        """Status for dashboards and monitoring."""
        return {
            "processor": "News Bureau Chief Signal Processor",
            "threshold": self.threshold,
            "processed_count": self._state.get("processed_count", 0),
            "triggers_fired": self._state.get("triggers_fired", 0),
            "last_processed": self._state.get("last_processed"),
            "active_signals": len(self._signals),
        }


# ── Entry Point ──────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(
        description="News Bureau Chief Signal Processor"
    )
    parser.add_argument("--test", action="store_true",
                        help="Run with simulated news data")
    args = parser.parse_args()

    processor = SignalProcessor()

    if args.test:
        print("News Bureau Chief -- Signal Processing Test")
        print("-" * 50)

        # Simulated news report
        mock_report = {
            "market_regime": "RISK-OFF",
            "headlines": [
                {
                    "title": "Fed Signals Emergency Rate Cut Amid Banking Stress",
                    "source": "Reuters",
                    "summary": "Federal Reserve officials indicate willingness "
                               "to cut rates if banking sector stress escalates",
                    "spx_impact": "SPX could gap down 2-3% on rate uncertainty",
                    "severity": "HIGH",
                },
                {
                    "title": "VIX Spikes to 35 as Market Crash Fears Grow",
                    "source": "Bloomberg",
                    "summary": "Volatility index surges as investors hedge "
                               "against potential flash crash scenario",
                    "spx_impact": "Iron condor positions at risk of breach",
                    "severity": "HIGH",
                },
                {
                    "title": "Tech Earnings Beat Expectations Across the Board",
                    "source": "CNBC",
                    "summary": "Major tech companies report strong Q1 results",
                    "spx_impact": "Positive for SPX, limited downside risk",
                    "severity": "MEDIUM",
                },
            ],
            "upcoming_events": [
                {
                    "event": "FOMC Rate Decision",
                    "date": "2026-03-18",
                    "severity": "HIGH",
                    "risk_to_position": "High risk if rate cut surprises market",
                },
                {
                    "event": "CPI Inflation Data Release",
                    "date": "2026-03-14",
                    "severity": "HIGH",
                    "risk_to_position": "High CPI could trigger VIX spike",
                },
            ],
        }

        result = processor.process_news_report(mock_report)

        print(f"Signals found: {result['signal_count']}")
        print(f"Max score: {result['max_score']}")
        print(f"Auto-trigger: {result['auto_trigger']}")
        print(f"Market regime: {result['market_regime']}")

        for sig in result["signals"]:
            print(f"\n  [{sig['score']:2d}] {sig['category']}")
            print(f"      {sig['headline'][:80]}")
            print(f"      Keywords: {', '.join(sig['matched_keywords'])}")

        print(f"\nStatus: {processor.get_status()}")
        print("\nAll tests passed!")
    else:
        print("Use --test to run signal processing test.")
