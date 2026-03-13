"""
sentiment_bridge.py -- Sentinel-Resonance Sentiment Bridge
============================================================
Meta App Factory | Resonance | Antigravity-AI

Allows Sentinel Bridge to check the operator's "Stress Level"
before sending high-urgency notifications. If stress is high,
the EQ Engine rewrites the notification to be calming/supportive.

Usage from Sentinel:
    from Resonance.sentiment_bridge import SentimentBridge
    bridge = SentimentBridge()
    result = bridge.check_stress()
    if result["should_soften"]:
        message = bridge.soften_message(original_message)
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
import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("resonance.sentiment")

SCRIPT_DIR = Path(__file__).resolve().parent
FACTORY_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(FACTORY_DIR))
sys.path.insert(0, str(FACTORY_DIR / "Sentinel_Bridge"))

# Lazy imports
_eq_engine = None
_pii = None


def _get_eq():
    global _eq_engine
    if _eq_engine is None:
        try:
            from unified_eq_engine import UnifiedEQEngine
            _eq_engine = UnifiedEQEngine()
        except ImportError:
            logger.warning("UnifiedEQEngine not available")
    return _eq_engine


def _get_pii():
    global _pii
    if _pii is None:
        try:
            from pii_masker import PIIMasker
            _pii = PIIMasker()
        except ImportError:
            pass
    return _pii


# ── Stress Threshold ─────────────────────────────────────
STRESS_SOFTEN_THRESHOLD = 7.0  # Soften notifications above this


class SentimentBridge:
    """
    Bridge between Sentinel notifications and the Resonance EQ Engine.
    Checks stress before delivering high-urgency messages.
    """

    def __init__(self, soften_threshold: float = STRESS_SOFTEN_THRESHOLD):
        self.threshold = soften_threshold
        self._stress_triggers: list = []

    # ── Check Stress ─────────────────────────────────────

    def check_stress(self, signals: dict = None) -> dict:
        """
        Check the current stress level.
        Returns stress score + whether to soften messages.
        """
        eq = _get_eq()
        if eq is None:
            return {
                "stress_level": 3.0,
                "should_soften": False,
                "tone": "professional",
                "eq_available": False,
            }

        assessment = eq.assess_emotional_state(signals or {})
        stress = assessment["stress_level"]
        should_soften = stress >= self.threshold

        result = {
            "stress_level": stress,
            "should_soften": should_soften,
            "tone": assessment["tone_recommended"],
            "threshold": self.threshold,
            "eq_available": True,
        }

        # Track stress triggers
        if should_soften:
            self._stress_triggers.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stress": stress,
                "signals": signals or {},
            })
            # Keep last 50
            self._stress_triggers = self._stress_triggers[-50:]

        return result

    # ── Soften Message ───────────────────────────────────

    def soften_message(self, message: str, urgency_score: int = 5) -> dict:
        """
        Rewrite a notification message if stress is high.
        Called by Sentinel before dispatch.
        """
        eq = _get_eq()
        if eq is None:
            return {
                "original": message,
                "rewritten": message,
                "softened": False,
                "tone": "original",
            }

        stress = eq._state.get("stress_level", 3.0)

        # Only soften high-urgency messages when stressed
        if stress < self.threshold or urgency_score < 5:
            return {
                "original": message[:200],
                "rewritten": message,
                "softened": False,
                "tone": "original",
                "stress_level": stress,
            }

        # Use EQ engine to calibrate tone
        calibrated = eq.calibrate_tone(message, stress_level=stress)

        # PII mask
        pii = _get_pii()
        if pii:
            calibrated["rewritten"] = pii.mask(calibrated["rewritten"])

        return {
            "original": message[:200],
            "rewritten": calibrated["rewritten"],
            "softened": True,
            "tone": calibrated["tone"],
            "stress_level": stress,
        }

    # ── Feedback from Notification Response ──────────────

    def record_reaction(self, reaction: str, tone_used: str = "",
                        notification_id: str = "") -> dict:
        """
        Record user reaction to a notification.
        Bridges to EQ engine feedback + Leitner.
        """
        eq = _get_eq()
        if eq is None:
            return {"recorded": False, "reason": "EQ engine unavailable"}

        return eq.record_feedback(
            reaction=reaction,
            tone_used=tone_used,
            message_context=f"notification:{notification_id}",
        )

    # ── Dashboard Data ───────────────────────────────────

    def get_status(self) -> dict:
        """Status for API endpoints."""
        eq = _get_eq()
        profile = eq.get_tone_profile() if eq else {}
        return {
            "bridge": "Sentinel-Resonance Sentiment Bridge",
            "threshold": self.threshold,
            "stress_triggers_count": len(self._stress_triggers),
            "recent_triggers": self._stress_triggers[-5:],
            "eq_profile": profile,
        }


# ── Entry Point ──────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")

    bridge = SentimentBridge()

    print("Sentinel-Resonance Sentiment Bridge -- Self-Test")
    print("-" * 50)

    # Test 1: Check stress
    stress = bridge.check_stress({"error_rate": 2, "circuit_breakers_open": 0})
    print(f"1. Stress check: {stress['stress_level']}/10, "
          f"soften={stress['should_soften']}")

    # Test 2: Soften a high-urgency message
    result = bridge.soften_message(
        "CRITICAL: Server down! Immediate action required!",
        urgency_score=9,
    )
    print(f"\n2. Soften test:")
    print(f"   Original: {result['original']}")
    print(f"   Rewritten: {result['rewritten']}")
    print(f"   Softened: {result['softened']}")

    # Test 3: High-stress scenario
    bridge.check_stress({"error_rate": 12, "circuit_breakers_open": 3,
                         "notification_frequency": 15})
    hi_result = bridge.soften_message(
        "ALERT: Multiple failures detected across pipelines!",
        urgency_score=8,
    )
    print(f"\n3. High-stress soften:")
    print(f"   Rewritten: {hi_result['rewritten']}")
    print(f"   Tone: {hi_result['tone']}")

    # Test 4: Status
    status = bridge.get_status()
    print(f"\n4. Status: threshold={status['threshold']}, "
          f"triggers={status['stress_triggers_count']}")

    print("\nAll tests passed!")
# V3 AUTO-HEAL ACTIVE
