"""
unified_eq_engine.py -- Resonance Unified EQ Engine
=====================================================
Meta App Factory | Resonance | Antigravity-AI

Synthesizes the best EQ patterns from Resonance 1-4:
  - NerveCenter: Severity-based triage & remedy matching
  - ActionPlan: Risk classification & agent feedback loops
  - CircuitBreaker: Stress from failure cascades
  - ErrorAggregator: Tone calibration from error frequency

Core capabilities:
  - Assess emotional state (stress level 0-10)
  - Calibrate notification tone based on stress
  - Record user feedback to adapt tone over time
  - Leitner Level 5 escalation for rejected tones
  - PII masking on all emotional logs
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("resonance.eq")

SCRIPT_DIR = Path(__file__).resolve().parent
FACTORY_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(FACTORY_DIR))
sys.path.insert(0, str(FACTORY_DIR / "Sentinel_Bridge"))

STATE_DIR = FACTORY_DIR / ".Gemini_state"
EQ_STATE_PATH = STATE_DIR / "eq_state.json"
MASTER_INDEX_PATH = FACTORY_DIR / "MASTER_INDEX.md"

# Lazy imports
_pii = None
_leitner = None


def _get_pii():
    global _pii
    if _pii is None:
        try:
            from pii_masker import PIIMasker
            _pii = PIIMasker()
        except ImportError:
            logger.warning("PIIMasker not available")
    return _pii


def _get_leitner():
    global _leitner
    if _leitner is None:
        try:
            from leitner_architect import LeitnerArchitect
            _leitner = LeitnerArchitect()
        except ImportError:
            logger.warning("LeitnerArchitect not available")
    return _leitner


# ── Tone Templates ───────────────────────────────────────

TONE_PROFILES = {
    "neutral": {
        "prefix": "",
        "style": "clear and factual",
        "urgency_words": ["update", "notice", "info"],
    },
    "professional": {
        "prefix": "Status Update: ",
        "style": "concise and business-like",
        "urgency_words": ["action needed", "attention", "priority"],
    },
    "calming": {
        "prefix": "Gentle reminder: ",
        "style": "warm, supportive, and reassuring",
        "urgency_words": ["when you have a moment", "no rush", "for your awareness"],
    },
    "supportive": {
        "prefix": "Hey -- just a heads up: ",
        "style": "friendly, empathetic, low-pressure",
        "urgency_words": ["take your time", "whenever ready", "just FYI"],
    },
    "urgent": {
        "prefix": "IMPORTANT: ",
        "style": "direct and action-oriented",
        "urgency_words": ["immediately", "critical", "requires action now"],
    },
}


class UnifiedEQEngine:
    """
    Emotional intelligence engine that assesses operator stress,
    calibrates notification tone, and learns from feedback.
    """

    def __init__(self):
        self._state = self._load_state()
        self._pii = _get_pii()

    # ── State Persistence ────────────────────────────────

    def _load_state(self) -> dict:
        if EQ_STATE_PATH.exists():
            try:
                return json.loads(EQ_STATE_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "stress_level": 3.0,
            "stress_history": [],
            "tone_feedback": [],
            "rejected_tones": [],
            "preferred_tone": "professional",
            "assessment_count": 0,
            "last_assessment": None,
        }

    def _save_state(self) -> None:
        STATE_DIR.mkdir(exist_ok=True)
        try:
            # PII-mask before saving
            safe_state = dict(self._state)
            if self._pii:
                for key in ("stress_history", "tone_feedback"):
                    if key in safe_state:
                        masked = []
                        for entry in safe_state[key][-50:]:
                            if isinstance(entry, dict):
                                masked.append({
                                    k: self._pii.mask(str(v)) if isinstance(v, str) else v
                                    for k, v in entry.items()
                                })
                            else:
                                masked.append(entry)
                        safe_state[key] = masked

            EQ_STATE_PATH.write_text(json.dumps(safe_state, indent=2))
        except Exception as e:
            logger.error("Could not save EQ state: %s", e)

    # ── Core: Assess Emotional State ─────────────────────

    def assess_emotional_state(self, signals: dict = None) -> dict:
        """
        Compute stress level (0-10) from system signals.

        Signals considered:
        - error_rate: errors per hour from ErrorAggregator
        - circuit_breakers_open: count of open circuits
        - failed_heals: NerveCenter failed heal attempts
        - time_of_day: late night = higher stress weight
        - notification_frequency: high freq = higher stress
        - user_feedback_negative: recent negative reactions
        """
        signals = signals or {}
        stress = 3.0  # baseline

        # Error rate contribution (from NerveCenter pattern)
        error_rate = signals.get("error_rate", 0)
        if error_rate > 10:
            stress += 3.0
        elif error_rate > 5:
            stress += 2.0
        elif error_rate > 2:
            stress += 1.0

        # Circuit breaker stress (from CircuitBreaker pattern)
        cb_open = signals.get("circuit_breakers_open", 0)
        stress += min(cb_open * 1.5, 3.0)

        # Failed heals amplify stress
        failed_heals = signals.get("failed_heals", 0)
        stress += min(failed_heals * 0.5, 2.0)

        # Time of day (late hours = amplify)
        hour = datetime.now().hour
        if hour >= 22 or hour < 6:
            stress += 1.0

        # Notification frequency
        notif_freq = signals.get("notification_frequency", 0)
        if notif_freq > 10:
            stress += 1.5
        elif notif_freq > 5:
            stress += 0.5

        # Recent negative feedback
        recent_neg = len([
            f for f in self._state.get("tone_feedback", [])[-10:]
            if f.get("reaction") == "negative"
        ])
        stress += min(recent_neg * 0.5, 2.0)

        # Clamp to 0-10
        stress = max(0.0, min(10.0, stress))

        # Update state
        self._state["stress_level"] = round(stress, 1)
        self._state["assessment_count"] = self._state.get("assessment_count", 0) + 1
        self._state["last_assessment"] = datetime.now(timezone.utc).isoformat()
        self._state.setdefault("stress_history", []).append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": round(stress, 1),
            "signals": {k: v for k, v in (signals or {}).items()},
        })
        # Keep last 100 entries
        self._state["stress_history"] = self._state["stress_history"][-100:]
        self._save_state()

        return {
            "stress_level": round(stress, 1),
            "tone_recommended": self._recommend_tone(stress),
            "signals_used": signals or {},
        }

    def _recommend_tone(self, stress: float) -> str:
        """Pick tone based on stress level and learned preferences."""
        # Check rejected tones
        rejected = set(self._state.get("rejected_tones", []))

        if stress >= 8:
            tone = "supportive"
        elif stress >= 6:
            tone = "calming"
        elif stress >= 4:
            tone = "professional"
        elif stress >= 2:
            tone = "neutral"
        else:
            tone = self._state.get("preferred_tone", "professional")

        # Fallback if recommended tone was rejected
        if tone in rejected:
            fallback_order = ["calming", "supportive", "professional", "neutral"]
            for fb in fallback_order:
                if fb not in rejected:
                    tone = fb
                    break

        return tone

    # ── Core: Calibrate Tone ─────────────────────────────

    def calibrate_tone(self, message: str, stress_level: float = None,
                       force_tone: str = None) -> dict:
        """
        Rewrite a notification message for the appropriate tone.

        If stress is high (>7), forces calming/supportive tone.
        Returns the rewritten message and metadata.
        """
        if stress_level is None:
            stress_level = self._state.get("stress_level", 3.0)

        tone_name = force_tone or self._recommend_tone(stress_level)
        profile = TONE_PROFILES.get(tone_name, TONE_PROFILES["neutral"])

        # Apply tone transformation
        rewritten = self._apply_tone(message, profile, stress_level)

        # PII mask the output
        if self._pii:
            rewritten = self._pii.mask(rewritten)

        return {
            "original": message[:200],
            "rewritten": rewritten,
            "tone": tone_name,
            "stress_level": stress_level,
            "style": profile["style"],
        }

    def _apply_tone(self, message: str, profile: dict,
                    stress: float) -> str:
        """Transform message text based on tone profile."""
        prefix = profile.get("prefix", "")

        if stress >= 8:
            # High stress: soften urgency words
            softened = message
            urgency_replacements = {
                "CRITICAL": "needs attention",
                "URGENT": "when you can",
                "IMMEDIATELY": "at your convenience",
                "FAILURE": "issue detected",
                "ERROR": "something to check",
                "ALERT": "heads up",
                "WARNING": "note",
            }
            for harsh, gentle in urgency_replacements.items():
                softened = softened.replace(harsh, gentle)
                softened = softened.replace(harsh.lower(), gentle)
                softened = softened.replace(harsh.title(), gentle)

            return f"{prefix}{softened}"

        elif stress >= 5:
            # Medium stress: add calming prefix, keep content
            return f"{prefix}{message}"

        else:
            # Low stress: pass through with light prefix
            return f"{prefix}{message}" if prefix else message

    # ── Core: Record Feedback ────────────────────────────

    def record_feedback(self, reaction: str, tone_used: str = "",
                        message_context: str = "") -> dict:
        """
        Record user reaction to a notification tone.

        reaction: "positive", "negative", "neutral"
        If negative, escalates to Leitner Level 5.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # PII-mask context before storing
        safe_context = self._pii.mask(message_context) if self._pii else message_context

        feedback = {
            "timestamp": timestamp,
            "reaction": reaction,
            "tone_used": tone_used,
            "context": safe_context[:200],
        }

        self._state.setdefault("tone_feedback", []).append(feedback)
        self._state["tone_feedback"] = self._state["tone_feedback"][-200:]

        escalated = False

        if reaction == "negative" and tone_used:
            # Add to rejected tones
            rejected = self._state.setdefault("rejected_tones", [])
            if tone_used not in rejected:
                rejected.append(tone_used)

            # Escalate to Leitner Level 5
            escalated = self._escalate_tone_error(tone_used, safe_context)

        elif reaction == "positive" and tone_used:
            # Learn preference
            self._state["preferred_tone"] = tone_used
            # Remove from rejected if previously rejected
            rejected = self._state.get("rejected_tones", [])
            if tone_used in rejected:
                rejected.remove(tone_used)

        self._save_state()

        return {
            "recorded": True,
            "reaction": reaction,
            "tone": tone_used,
            "escalated": escalated,
        }

    def _escalate_tone_error(self, tone: str, context: str) -> bool:
        """Tag rejected tone as Level 5 error in MASTER_INDEX."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        entry = (
            f"\n### ERROR_ENTRY\n"
            f"- **Timestamp:** {timestamp}\n"
            f"- **App:** Resonance_EQ_Engine\n"
            f"- **Error_Complexity:** 5\n"
            f"- **Description:** Tone '{tone}' rejected by user\n"
            f"- **Root_Cause:** Negative reaction to notification style\n"
            f"- **Resolution:** pending_deep_review\n"
            f"- **Status:** OPEN\n"
            f"- **Last_Reviewed:** {timestamp}\n"
        )

        try:
            with open(MASTER_INDEX_PATH, "a", encoding="utf-8", newline="\n") as f:
                f.write(entry)
            logger.info("Leitner Level 5: tone '%s' flagged", tone)
            return True
        except Exception as e:
            logger.error("Leitner escalation failed: %s", e)
            return False

    # ── Dashboard Data ───────────────────────────────────

    def get_tone_profile(self) -> dict:
        """Current tone settings for dashboards."""
        return {
            "stress_level": self._state.get("stress_level", 3.0),
            "preferred_tone": self._state.get("preferred_tone", "professional"),
            "rejected_tones": self._state.get("rejected_tones", []),
            "assessment_count": self._state.get("assessment_count", 0),
            "last_assessment": self._state.get("last_assessment"),
            "available_tones": list(TONE_PROFILES.keys()),
            "recent_feedback_count": len(self._state.get("tone_feedback", [])),
        }

    def get_stress_history(self, limit: int = 20) -> list:
        """Return recent stress history."""
        return self._state.get("stress_history", [])[-limit:]


# ── Entry Point ──────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(description="Resonance Unified EQ Engine")
    parser.add_argument("--test", action="store_true", help="Run self-test")
    args = parser.parse_args()

    engine = UnifiedEQEngine()

    if args.test:
        print("Unified EQ Engine -- Self-Test")
        print("-" * 50)

        # Test 1: Assess stress
        result = engine.assess_emotional_state({
            "error_rate": 3,
            "circuit_breakers_open": 1,
            "notification_frequency": 6,
        })
        print(f"1. Stress Assessment: {result['stress_level']}/10")
        print(f"   Tone: {result['tone_recommended']}")

        # Test 2: Calibrate normal message
        cal = engine.calibrate_tone("System update deployed successfully")
        print(f"\n2. Normal message:")
        print(f"   Original: {cal['original']}")
        print(f"   Rewritten: {cal['rewritten']}")
        print(f"   Tone: {cal['tone']}")

        # Test 3: Calibrate high-stress message
        cal_stress = engine.calibrate_tone(
            "CRITICAL FAILURE: Database connection lost!",
            stress_level=9.0,
        )
        print(f"\n3. High-stress message:")
        print(f"   Original: {cal_stress['original']}")
        print(f"   Rewritten: {cal_stress['rewritten']}")
        print(f"   Tone: {cal_stress['tone']}")

        # Test 4: Record feedback
        fb = engine.record_feedback("positive", "calming", "test context")
        print(f"\n4. Feedback: {fb}")

        # Test 5: Profile
        profile = engine.get_tone_profile()
        print(f"\n5. Profile: stress={profile['stress_level']}, "
              f"preferred={profile['preferred_tone']}")

        print("\nAll tests passed!")
    else:
        print("Unified EQ Engine loaded.")
        profile = engine.get_tone_profile()
        print(f"  Stress: {profile['stress_level']}/10")
        print(f"  Tone: {profile['preferred_tone']}")
        print("Use --test for self-test.")
