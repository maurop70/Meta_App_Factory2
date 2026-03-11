"""
context_engine.py — Sentinel Bridge Context Engine
═══════════════════════════════════════════════════
Sentinel Bridge | Aether Protocol | Antigravity-AI

Summarizes raw JSON triggers (calendar events, webhook payloads,
system alerts) into human-readable insights with urgency scoring.
"""

import re
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("sentinel.context")

# ── Urgency Score Heuristics ─────────────────────────────

URGENCY_KEYWORDS = {
    10: ["critical", "emergency", "outage", "security breach", "data loss"],
    9:  ["urgent", "deadline", "overdue", "failure", "down"],
    8:  ["important", "meeting in 15", "expiring", "blocked", "production"],
    7:  ["high priority", "asap", "review needed", "approval"],
    6:  ["meeting", "call", "appointment", "interview", "demo"],
    5:  ["reminder", "follow up", "update", "check in"],
    4:  ["scheduled", "weekly", "routine", "sync"],
    3:  ["info", "fyi", "note", "logged"],
    2:  ["low priority", "optional", "when possible"],
    1:  ["archived", "historical", "reference"],
}

# ── Time-of-Day Greetings ────────────────────────────────

def _time_greeting() -> str:
    hour = datetime.now().hour
    if hour < 6:
        return "Late night"
    elif hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    elif hour < 21:
        return "Good evening"
    else:
        return "Late evening"


def _day_context() -> str:
    now = datetime.now()
    day = now.strftime("%A")
    if now.weekday() >= 5:
        return f"Weekend ({day})"
    return day


# ── Summary Templates ────────────────────────────────────

TEMPLATES = {
    "calendar": "📅 {greeting} — {activity} at {time} ({day})",
    "reminder": "🔔 {greeting} — Reminder: {activity}",
    "system":   "⚙️ System Alert: {activity}",
    "webhook":  "🔗 Webhook trigger: {activity}",
    "pipeline": "🔄 Pipeline: {activity}",
    "healing":  "🩹 Self-healing: {activity}",
    "default":  "📌 {greeting} — {activity}",
}


class ContextInsight:
    """Structured insight from a raw trigger."""

    def __init__(self, summary: str, headline: str, urgency_score: int,
                 channel_hint: str, source: str, metadata: dict = None):
        self.summary = summary
        self.headline = headline
        self.urgency_score = urgency_score
        self.channel_hint = channel_hint
        self.source = source
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "headline": self.headline,
            "urgency_score": self.urgency_score,
            "channel_hint": self.channel_hint,
            "source": self.source,
            "metadata": self.metadata,
        }


class ContextEngine:
    """
    Transforms raw JSON triggers into human-readable insights
    with urgency scoring and channel routing hints.
    """

    def summarize(self, raw_trigger: dict) -> ContextInsight:
        """
        Main entry point. Takes a raw trigger dict and returns
        a ContextInsight with summary, urgency, and routing hint.
        """
        source = self._detect_source(raw_trigger)
        activity = self._extract_activity(raw_trigger)
        time_str = self._extract_time(raw_trigger)
        priority = raw_trigger.get("priority", "normal")

        # Calculate urgency score
        urgency = self._calculate_urgency(activity, priority, raw_trigger)

        # Build summary from template
        greeting = _time_greeting()
        day = _day_context()
        template = TEMPLATES.get(source, TEMPLATES["default"])
        summary = template.format(
            greeting=greeting,
            activity=activity,
            time=time_str or "unscheduled",
            day=day,
        )

        # Generate headline
        headline = self._generate_headline(activity, urgency, source)

        # Channel hint based on urgency
        channel_hint = self._suggest_channel(urgency)

        return ContextInsight(
            summary=summary,
            headline=headline,
            urgency_score=urgency,
            channel_hint=channel_hint,
            source=source,
            metadata={
                "raw_activity": activity,
                "time": time_str,
                "day": day,
                "greeting": greeting,
                "priority": priority,
            },
        )

    # ── Source Detection ─────────────────────────────────

    def _detect_source(self, trigger: dict) -> str:
        """Detect the source type from trigger keys."""
        source = trigger.get("source", "").lower()
        if source in ("calendar", "google_calendar"):
            return "calendar"
        if source in ("manual", "voice", "text"):
            return "reminder"
        if source in ("webhook", "n8n"):
            return "webhook"
        if source in ("pipeline", "cron"):
            return "pipeline"
        if source in ("healing", "self_heal", "nerve_center"):
            return "healing"
        if source in ("system", "alert", "sentinel"):
            return "system"

        # Heuristic detection from keys
        if "calendar_id" in trigger or "event_id" in trigger:
            return "calendar"
        if "webhook_url" in trigger:
            return "webhook"
        if "heal_action" in trigger:
            return "healing"

        return "default"

    def _extract_activity(self, trigger: dict) -> str:
        """Extract the primary activity/summary from the trigger."""
        for key in ("activity", "summary", "title", "subject", "message",
                     "text", "description", "name"):
            val = trigger.get(key)
            if val and isinstance(val, str):
                return val.strip()
        return "Unknown activity"

    def _extract_time(self, trigger: dict) -> Optional[str]:
        """Extract and format a time from the trigger."""
        for key in ("time", "start", "when", "scheduled_at", "created_at"):
            val = trigger.get(key)
            if val and isinstance(val, str):
                try:
                    dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    return dt.strftime("%I:%M %p, %b %d")
                except (ValueError, TypeError):
                    return val
        return None

    # ── Urgency Scoring ──────────────────────────────────

    def _calculate_urgency(self, activity: str, priority: str,
                           trigger: dict) -> int:
        """
        Calculate urgency score (1-10) from activity text,
        priority field, and trigger context.
        """
        score = 5  # Default baseline

        # Priority field boost
        priority_scores = {
            "critical": 10, "urgent": 9, "high": 7,
            "normal": 5, "low": 3, "info": 2,
        }
        score = priority_scores.get(priority.lower(), score)

        # Keyword boost (highest matching keyword wins)
        combined = f"{activity} {trigger.get('description', '')}".lower()
        for level in sorted(URGENCY_KEYWORDS.keys(), reverse=True):
            for keyword in URGENCY_KEYWORDS[level]:
                if keyword in combined:
                    score = max(score, level)
                    break

        # Time proximity boost
        time_str = self._extract_time(trigger)
        if time_str:
            try:
                raw = trigger.get("time") or trigger.get("start", "")
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                delta = (dt - now).total_seconds()
                if 0 < delta < 900:       # Next 15 min
                    score = max(score, 9)
                elif 0 < delta < 3600:    # Next hour
                    score = max(score, 7)
                elif delta < 0:           # Overdue
                    score = max(score, 8)
            except (ValueError, TypeError):
                pass

        return min(max(score, 1), 10)

    def _generate_headline(self, activity: str, urgency: int,
                           source: str) -> str:
        """Generate a concise headline for the notification title."""
        if urgency >= 9:
            prefix = "🚨 URGENT"
        elif urgency >= 7:
            prefix = "⚡ Important"
        elif urgency >= 5:
            prefix = "📋"
        else:
            prefix = "ℹ️"

        # Truncate activity for headline
        short = activity[:60] + "…" if len(activity) > 60 else activity
        return f"{prefix} {short}"

    def _suggest_channel(self, urgency: int) -> str:
        """Suggest notification channel(s) based on urgency score."""
        if urgency >= 8:
            return "push+whatsapp+sms"
        elif urgency >= 5:
            return "push+whatsapp"
        else:
            return "push"


if __name__ == "__main__":
    engine = ContextEngine()

    # Test samples
    tests = [
        {"source": "calendar", "activity": "Team standup", "time": "2026-03-11T10:00:00Z", "priority": "normal"},
        {"source": "system", "activity": "Production database failure detected", "priority": "critical"},
        {"source": "manual", "text": "Pick up Leo from school at 3pm", "priority": "high"},
        {"source": "webhook", "title": "New PR review requested", "priority": "normal"},
    ]

    for t in tests:
        insight = engine.summarize(t)
        print(f"[U:{insight.urgency_score}] {insight.headline}")
        print(f"  → {insight.summary}")
        print(f"  → Channel: {insight.channel_hint}")
        print()
