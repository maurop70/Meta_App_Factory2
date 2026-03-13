"""
Sentinel Bridge — Aether Ingestion Layer
==========================================
Processes multimodal inputs: manual text, voice-to-text transcriptions,
and background scans for high-stakes items. Extracts intent, timing,
and initial category before passing to the categorization engine.
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
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("sentinel.aether")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── Time pattern recognition ────────────────────────────────────────
TIME_PATTERNS = [
    # "at 3pm", "at 3:30 PM"
    (r'\bat\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))', "absolute_time"),
    # "tomorrow", "next monday"
    (r'\b(tomorrow|today|tonight)\b', "relative_day"),
    (r'\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
     "relative_weekday"),
    # "in 30 minutes", "in 2 hours"
    (r'\bin\s+(\d+)\s*(minutes?|hours?|days?)\b', "relative_offset"),
    # ISO-like dates "2026-03-10", "March 10"
    (r'\b(\d{4}-\d{2}-\d{2})\b', "iso_date"),
    (r'\b(january|february|march|april|may|june|july|august|september|'
     r'october|november|december)\s+(\d{1,2})\b', "month_day"),
]

# ── High-stakes keyword scanning ────────────────────────────────────
HIGH_STAKES_KEYWORDS = {
    "Leo's School": [
        "science project", "homework", "school project", "due date",
        "parent-teacher", "report card", "school meeting", "leo",
        "field trip", "school event", "exam", "test",
    ],
    "Work": [
        "deadline", "quarterly", "budget", "presentation",
        "client meeting", "board meeting", "review", "audit",
        "contract", "shipment", "delivery", "invoice",
    ],
    "Family": [
        "doctor", "dentist", "appointment", "birthday",
        "anniversary", "family dinner", "reservation", "vacation",
    ],
    "AI": [
        "model training", "deployment", "pipeline", "checkpoint",
        "fine-tuning", "api key", "token refresh", "crawl",
    ],
}


class AetherInput:
    """Represents a processed input from any source."""

    def __init__(self, *, raw_text: str, source: str = "manual",
                 extracted_intent: str = "",
                 extracted_time: str = "",
                 initial_category: str = "Uncategorized",
                 priority: str = "normal",
                 confidence: float = 0.0,
                 metadata: dict | None = None):
        self.raw_text = raw_text
        self.source = source  # "manual", "voice", "calendar", "background_scan"
        self.extracted_intent = extracted_intent
        self.extracted_time = extracted_time
        self.initial_category = initial_category
        self.priority = priority  # "normal", "high", "critical"
        self.confidence = confidence
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "raw_text": self.raw_text,
            "source": self.source,
            "extracted_intent": self.extracted_intent,
            "extracted_time": self.extracted_time,
            "initial_category": self.initial_category,
            "priority": self.priority,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class AetherIngestion:
    """Process and enrich raw inputs from multiple modalities."""

    def __init__(self):
        self._inputs_log: list[dict] = []

    # ── Public API ───────────────────────────────────────────────────
    def process_text(self, text: str, source: str = "manual") -> AetherInput:
        """Process a raw text input (manual or voice-to-text)."""
        intent = self._extract_intent(text)
        timing = self._extract_timing(text)
        category, confidence = self._initial_categorize(text)
        priority = self._assess_priority(text, category)

        result = AetherInput(
            raw_text=text,
            source=source,
            extracted_intent=intent,
            extracted_time=timing,
            initial_category=category,
            priority=priority,
            confidence=confidence,
        )

        self._inputs_log.append(result.to_dict())
        self._persist_log()
        logger.info("Aether processed: '%s' → [%s] %s @ %s (%.0f%% conf)",
                     text[:50], category, intent, timing, confidence * 100)
        return result

    def process_calendar_event(self, event_dict: dict) -> AetherInput:
        """Convert a CalendarEvent dict into an AetherInput."""
        summary = event_dict.get("summary", "")
        desc = event_dict.get("description", "")
        combined = f"{summary} {desc}".strip()

        category, confidence = self._initial_categorize(combined)

        # Calendar source gives us better context
        cal_label = event_dict.get("calendar_label", "")
        if cal_label == "Work" and confidence < 0.7:
            category = "Work"
            confidence = max(confidence, 0.6)
        elif cal_label == "Personal":
            # Check for Leo/school keywords
            if any(kw in combined.lower() for kw in ["leo", "school"]):
                category = "Leo's School"
                confidence = max(confidence, 0.8)

        priority = self._assess_priority(combined, category)

        return AetherInput(
            raw_text=combined,
            source="calendar",
            extracted_intent=summary,
            extracted_time=event_dict.get("start", ""),
            initial_category=category,
            priority=priority,
            confidence=confidence,
            metadata={"event_id": event_dict.get("event_id", ""),
                       "source_account": event_dict.get("source_account", "")},
        )

    def background_scan(self, items: list[dict]) -> list[AetherInput]:
        """Scan a batch of items for high-stakes content."""
        flagged: list[AetherInput] = []
        for item in items:
            text = item.get("summary", "") + " " + item.get("description", "")
            if self._is_high_stakes(text):
                inp = self.process_text(text, source="background_scan")
                inp.priority = "high"
                flagged.append(inp)
        return flagged

    # ── Intent Extraction ────────────────────────────────────────────
    def _extract_intent(self, text: str) -> str:
        """Extract the core action/intent from free text."""
        # Strip time references to isolate the intent
        cleaned = text
        for pattern, _ in TIME_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        # Remove common filler words
        fillers = ["remind me to", "don't forget to", "remember to",
                    "please", "need to", "i need to", "make sure to",
                    "i have to", "have to"]
        for filler in fillers:
            cleaned = re.sub(re.escape(filler), "", cleaned,
                             flags=re.IGNORECASE)
        return cleaned.strip().strip(".,!?").strip() or text.strip()

    # ── Time Extraction ──────────────────────────────────────────────
    def _extract_timing(self, text: str) -> str:
        """Extract timing information from free text."""
        for pattern, ptype in TIME_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return ""

    # ── Categorization ───────────────────────────────────────────────
    def _initial_categorize(self, text: str) -> tuple[str, float]:
        """Keyword-based initial categorization with confidence score."""
        text_lower = text.lower()
        scores: dict[str, float] = {}

        for category, keywords in HIGH_STAKES_KEYWORDS.items():
            score = 0.0
            for kw in keywords:
                if kw in text_lower:
                    score += 1.0 / len(keywords)
            if score > 0:
                scores[category] = min(score * 2, 1.0)  # boost but cap at 1.0

        if not scores:
            return "Uncategorized", 0.0

        best = max(scores, key=scores.get)
        return best, scores[best]

    def _assess_priority(self, text: str, category: str) -> str:
        """Determine priority based on category and urgency keywords."""
        text_lower = text.lower()
        urgent_words = ["urgent", "asap", "critical", "emergency",
                        "due today", "overdue", "deadline today"]
        if any(w in text_lower for w in urgent_words):
            return "critical"
        if category in ("Leo's School", "Work"):
            if any(w in text_lower for w in ["tomorrow", "due", "deadline"]):
                return "high"
        return "normal"

    def _is_high_stakes(self, text: str) -> bool:
        """Check if text contains high-stakes keywords."""
        text_lower = text.lower()
        for keywords in HIGH_STAKES_KEYWORDS.values():
            for kw in keywords:
                if kw in text_lower:
                    return True
        return False

    # ── Persistence ──────────────────────────────────────────────────
    def _persist_log(self) -> None:
        log_file = DATA_DIR / "aether_input_log.json"
        # Keep only last 500 entries
        recent = self._inputs_log[-500:]
        log_file.write_text(json.dumps(recent, indent=2))
# V3 AUTO-HEAL ACTIVE
