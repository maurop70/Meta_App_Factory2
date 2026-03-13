"""
Sentinel Bridge — Intent Extractor
====================================
NLP-lite extraction of intent, timing, and urgency from free-form
text inputs (manual text or voice-to-text transcriptions).
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


import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("sentinel.intent")

# ── Day name mapping ─────────────────────────────────────────────────
DAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


class ExtractedIntent:
    """Structured extraction result."""

    def __init__(self, *, activity: str, when: datetime | None = None,
                 when_text: str = "", urgency: str = "normal",
                 recurrence: str = "", raw_text: str = ""):
        self.activity = activity
        self.when = when
        self.when_text = when_text
        self.urgency = urgency      # normal, high, critical
        self.recurrence = recurrence  # "", "daily", "weekly", "monthly"
        self.raw_text = raw_text

    def to_dict(self) -> dict:
        return {
            "activity": self.activity,
            "when": self.when.isoformat() if self.when else None,
            "when_text": self.when_text,
            "urgency": self.urgency,
            "recurrence": self.recurrence,
            "raw_text": self.raw_text,
        }


class IntentExtractor:
    """Parse free-form reminder text into structured intents."""

    def extract(self, text: str) -> ExtractedIntent:
        """Full extraction pipeline."""
        activity = self._extract_activity(text)
        when, when_text = self._extract_when(text)
        urgency = self._extract_urgency(text)
        recurrence = self._extract_recurrence(text)

        return ExtractedIntent(
            activity=activity,
            when=when,
            when_text=when_text,
            urgency=urgency,
            recurrence=recurrence,
            raw_text=text,
        )

    # ── Activity extraction ──────────────────────────────────────────
    def _extract_activity(self, text: str) -> str:
        """Strip time/urgency markers to isolate the activity."""
        cleaned = text

        # Remove common reminder prefixes
        prefixes = [
            r"(?i)remind\s+me\s+(?:to\s+)?",
            r"(?i)don'?t\s+forget\s+(?:to\s+)?",
            r"(?i)remember\s+(?:to\s+)?",
            r"(?i)i\s+(?:need|have)\s+to\s+",
            r"(?i)make\s+sure\s+(?:to\s+)?",
            r"(?i)please\s+",
        ]
        for prefix in prefixes:
            cleaned = re.sub(prefix, "", cleaned, count=1)

        # Remove time expressions
        time_patterns = [
            r"(?i)\bat\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?",
            r"(?i)\b(?:tomorrow|today|tonight)\b",
            r"(?i)\bnext\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"(?i)\bin\s+\d+\s*(?:minutes?|hours?|days?)\b",
            r"(?i)\b\d{4}-\d{2}-\d{2}\b",
            r"(?i)\bevery\s+(?:day|week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        ]
        for pattern in time_patterns:
            cleaned = re.sub(pattern, "", cleaned)

        # Remove urgency markers
        urgency_words = [
            r"(?i)\b(?:urgently?|asap|critical(?:ly)?|immediately)\b",
        ]
        for pattern in urgency_words:
            cleaned = re.sub(pattern, "", cleaned)

        # Clean up whitespace/punctuation
        cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".,!?;:-")
        return cleaned if cleaned else text.strip()

    # ── Time extraction ──────────────────────────────────────────────
    def _extract_when(self, text: str) -> tuple[datetime | None, str]:
        """Extract datetime from text. Returns (datetime, raw_match)."""
        now = datetime.now(timezone.utc)
        text_lower = text.lower()

        # "in X minutes/hours/days"
        match = re.search(r"in\s+(\d+)\s*(minutes?|hours?|days?)",
                          text_lower)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if "minute" in unit:
                dt = now + timedelta(minutes=amount)
            elif "hour" in unit:
                dt = now + timedelta(hours=amount)
            else:
                dt = now + timedelta(days=amount)
            return dt, match.group(0)

        # "today/tonight/tomorrow"
        if "tomorrow" in text_lower:
            # Check for time
            time_match = re.search(
                r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))", text_lower)
            dt = now + timedelta(days=1)
            if time_match:
                dt = self._set_time(dt, time_match.group(1))
                return dt, f"tomorrow {time_match.group(1)}"
            return dt.replace(hour=9, minute=0, second=0), "tomorrow"

        if "tonight" in text_lower:
            return now.replace(hour=20, minute=0, second=0), "tonight"

        if "today" in text_lower:
            time_match = re.search(
                r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))", text_lower)
            if time_match:
                dt = self._set_time(now, time_match.group(1))
                return dt, f"today {time_match.group(1)}"
            return now.replace(hour=17, minute=0, second=0), "today"

        # "next Monday", etc.
        match = re.search(
            r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            text_lower)
        if match:
            target_day = DAY_NAMES[match.group(1)]
            days_ahead = (target_day - now.weekday() + 7) % 7 or 7
            dt = now + timedelta(days=days_ahead)
            time_match = re.search(
                r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))", text_lower)
            if time_match:
                dt = self._set_time(dt, time_match.group(1))
            else:
                dt = dt.replace(hour=9, minute=0, second=0)
            return dt, match.group(0)

        # "at 3pm", "at 3:30 PM"
        match = re.search(r"at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))",
                          text_lower)
        if match:
            dt = self._set_time(now, match.group(1))
            if dt < now:
                dt += timedelta(days=1)  # assume next occurrence
            return dt, match.group(0)

        # ISO date "2026-03-10"
        match = re.search(r"(\d{4}-\d{2}-\d{2})", text_lower)
        if match:
            try:
                dt = datetime.fromisoformat(
                    match.group(1)).replace(tzinfo=timezone.utc)
                return dt, match.group(0)
            except ValueError:
                pass

        return None, ""

    def _set_time(self, dt: datetime, time_str: str) -> datetime:
        """Parse '3pm', '3:30 PM' and set on datetime."""
        time_str = time_str.strip().lower()
        is_pm = "pm" in time_str
        is_am = "am" in time_str
        time_str = time_str.replace("am", "").replace("pm", "").strip()

        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0

        if is_pm and hour < 12:
            hour += 12
        elif is_am and hour == 12:
            hour = 0

        return dt.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # ── Urgency extraction ───────────────────────────────────────────
    def _extract_urgency(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in
               ["urgent", "asap", "critical", "emergency", "immediately"]):
            return "critical"
        if any(w in text_lower for w in
               ["important", "priority", "due soon", "deadline"]):
            return "high"
        return "normal"

    # ── Recurrence extraction ────────────────────────────────────────
    def _extract_recurrence(self, text: str) -> str:
        text_lower = text.lower()
        if re.search(r"every\s+day|daily", text_lower):
            return "daily"
        if re.search(r"every\s+week|weekly", text_lower):
            return "weekly"
        if re.search(r"every\s+month|monthly", text_lower):
            return "monthly"
        if re.search(
            r"every\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            text_lower):
            return "weekly"
        return ""
# V3 AUTO-HEAL ACTIVE
