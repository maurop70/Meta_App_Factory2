"""
Sentinel Bridge — Calendar Poller
==================================
Continuously polls Google Calendar for events on configured accounts.
Supports multiple calendar IDs with independent poll intervals.

Events are normalised into SentinelReminder objects and forwarded to
the categorization engine.
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

from fernet_vault import FernetVault

logger = logging.getLogger("sentinel.calendar")

# ── Data directory ───────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── Calendar configuration ───────────────────────────────────────────
CALENDAR_ACCOUNTS = [
    {
        "id": "work",
        "email": "mpetrini@heinleinfoodsusa.com",
        "label": "Work",
        "poll_interval_minutes": 15,
    },
    {
        "id": "personal",
        "email": "mauro@gelatopetrini.com",
        "label": "Personal",
        "poll_interval_minutes": 15,
    },
]


class CalendarEvent:
    """Normalised calendar event."""

    def __init__(self, *, event_id: str, summary: str, start: str, end: str,
                 description: str = "", location: str = "",
                 source_account: str = "", calendar_label: str = "",
                 all_day: bool = False, raw: dict | None = None):
        self.event_id = event_id
        self.summary = summary
        self.start = start
        self.end = end
        self.description = description
        self.location = location
        self.source_account = source_account
        self.calendar_label = calendar_label
        self.all_day = all_day
        self.raw = raw or {}

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "summary": self.summary,
            "start": self.start,
            "end": self.end,
            "description": self.description,
            "location": self.location,
            "source_account": self.source_account,
            "calendar_label": self.calendar_label,
            "all_day": self.all_day,
        }


class CalendarPoller:
    """Polls Google Calendar API for events across multiple accounts."""

    GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"

    def __init__(self, vault: FernetVault | None = None):
        self.vault = vault or FernetVault()
        self._seen_events: set[str] = set()
        self._load_seen()

    # ── Public API ───────────────────────────────────────────────────
    async def poll_all(self, lookahead_hours: int = 48) -> list[CalendarEvent]:
        """Poll all configured calendars for upcoming events."""
        all_events: list[CalendarEvent] = []
        for account in CALENDAR_ACCOUNTS:
            try:
                events = await self._poll_account(account, lookahead_hours)
                all_events.extend(events)
            except Exception as exc:
                logger.error("Poll failed for %s: %s", account["email"], exc)
        return all_events

    async def poll_new(self, lookahead_hours: int = 48) -> list[CalendarEvent]:
        """Return only events not previously seen."""
        all_events = await self.poll_all(lookahead_hours)
        new_events = [e for e in all_events if e.event_id not in self._seen_events]
        for e in new_events:
            self._seen_events.add(e.event_id)
        self._save_seen()
        return new_events

    def get_active_accounts(self) -> list[dict]:
        """Return list of configured calendar accounts."""
        return CALENDAR_ACCOUNTS

    # ── Internal ─────────────────────────────────────────────────────
    async def _poll_account(self, account: dict,
                            lookahead_hours: int) -> list[CalendarEvent]:
        """Fetch events from a single Google Calendar account."""
        token = self.vault.retrieve(f"google_token_{account['id']}")
        if not token:
            logger.warning("No Google token for account '%s' — "
                           "run sentinel_config.py to authorize", account["id"])
            # Return demo events for initial setup / testing
            return self._demo_events(account)

        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(hours=lookahead_hours)).isoformat()

        url = (f"{self.GOOGLE_CALENDAR_API}/calendars/"
               f"{account['email']}/events")
        params = {
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 50,
        }
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        events: list[CalendarEvent] = []
        for item in data.get("items", []):
            start_info = item.get("start", {})
            end_info = item.get("end", {})
            events.append(CalendarEvent(
                event_id=item["id"],
                summary=item.get("summary", "(No title)"),
                start=start_info.get("dateTime", start_info.get("date", "")),
                end=end_info.get("dateTime", end_info.get("date", "")),
                description=item.get("description", ""),
                location=item.get("location", ""),
                source_account=account["email"],
                calendar_label=account["label"],
                all_day="date" in start_info and "dateTime" not in start_info,
                raw=item,
            ))
        return events

    def _demo_events(self, account: dict) -> list[CalendarEvent]:
        """Generate sample events for development / first-run testing."""
        now = datetime.now(timezone.utc)
        demos = []
        if account["id"] == "work":
            demos = [
                CalendarEvent(
                    event_id="demo_work_1",
                    summary="Budget Review Meeting",
                    start=(now + timedelta(hours=2)).isoformat(),
                    end=(now + timedelta(hours=3)).isoformat(),
                    source_account=account["email"],
                    calendar_label="Work",
                ),
                CalendarEvent(
                    event_id="demo_work_2",
                    summary="Quarterly Planning Session",
                    start=(now + timedelta(hours=24)).isoformat(),
                    end=(now + timedelta(hours=26)).isoformat(),
                    source_account=account["email"],
                    calendar_label="Work",
                ),
            ]
        elif account["id"] == "personal":
            demos = [
                CalendarEvent(
                    event_id="demo_personal_1",
                    summary="Leo Science Project Due",
                    start=(now + timedelta(hours=18)).isoformat(),
                    end=(now + timedelta(hours=18, minutes=30)).isoformat(),
                    source_account=account["email"],
                    calendar_label="Personal",
                    description="Leo's school science project submission deadline",
                ),
                CalendarEvent(
                    event_id="demo_personal_2",
                    summary="Family Dinner Reservation",
                    start=(now + timedelta(hours=30)).isoformat(),
                    end=(now + timedelta(hours=32)).isoformat(),
                    source_account=account["email"],
                    calendar_label="Personal",
                ),
            ]
        return demos

    # ── Persistence ──────────────────────────────────────────────────
    def _load_seen(self) -> None:
        seen_file = DATA_DIR / "seen_events.json"
        if seen_file.exists():
            try:
                self._seen_events = set(json.loads(seen_file.read_text()))
            except Exception:
                self._seen_events = set()

    def _save_seen(self) -> None:
        seen_file = DATA_DIR / "seen_events.json"
        seen_file.write_text(json.dumps(list(self._seen_events), indent=2))
