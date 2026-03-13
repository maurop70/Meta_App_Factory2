"""
Sentinel Bridge — Notification Dispatcher
==========================================
Pushes notifications to Mauro's phone via ntfy.sh with the standard
header format: [Category] Activity Name - Time

Supports:
- Priority levels (urgent → max, high → high, normal → default)
- Action buttons (snooze, mark done)
- Tags/emojis per category
- Delivery confirmation logging
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


import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

# Import Factory-level HTTP safety utilities
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.safe_http import ascii_safe, safe_headers, utf8_body

from fernet_vault import FernetVault

logger = logging.getLogger("sentinel.dispatcher")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── ntfy defaults ────────────────────────────────────────────────────
DEFAULT_NTFY_SERVER = "https://ntfy.sh"
DEFAULT_NTFY_TOPIC = "sentinel_mauro_private"

# ── Category styling ────────────────────────────────────────────────
CATEGORY_CONFIG = {
    "AI": {
        "emoji": "🤖",
        "tags": ["robot", "ai"],
        "color": "#7C3AED",
    },
    "Work": {
        "emoji": "💼",
        "tags": ["briefcase", "work"],
        "color": "#2563EB",
    },
    "Leo's School": {
        "emoji": "📚",
        "tags": ["books", "school"],
        "color": "#059669",
    },
    "Family": {
        "emoji": "👨‍👩‍👦",
        "tags": ["family", "heart"],
        "color": "#DC2626",
    },
    "Uncategorized": {
        "emoji": "📌",
        "tags": ["pushpin"],
        "color": "#6B7280",
    },
}

PRIORITY_MAP = {
    "critical": "5",  # max
    "high": "4",      # high
    "normal": "3",    # default
    "low": "2",       # low
}


class NotificationDispatcher:
    """Push notifications via ntfy with professional formatting."""

    def __init__(self, vault: FernetVault | None = None):
        self.vault = vault or FernetVault()
        self._delivery_log: list[dict] = []
        self._load_log()

    # ── Public API ───────────────────────────────────────────────────
    async def send_reminder(self, *, category: str, activity: str,
                            time_str: str, priority: str = "normal",
                            reminder_id: str = "",
                            extra_body: str = "") -> dict:
        """
        Send a formatted reminder notification.

        Format: [Category] Activity Name - Time
        """
        cat_config = CATEGORY_CONFIG.get(category, CATEGORY_CONFIG["Uncategorized"])
        emoji = cat_config["emoji"]
        tags = cat_config["tags"]

        # Build the notification title (ASCII-safe via Factory utility)
        title = f"[{category}] {ascii_safe(activity)}"
        if time_str:
            title += f" - {time_str}"

        # Build message body
        body = f"{emoji} {activity}"
        if time_str:
            body += f"\n⏰ {time_str}"
        if extra_body:
            body += f"\n\n{extra_body}"

        # Determine ntfy config
        server = self.vault.retrieve("ntfy_server", DEFAULT_NTFY_SERVER)
        topic = self.vault.retrieve("ntfy_topic", DEFAULT_NTFY_TOPIC)
        url = f"{server}/{topic}"

        headers = {
            "Title": title,
            "Priority": PRIORITY_MAP.get(priority, "3"),
            "Tags": ",".join(tags),
        }

        # Add action buttons for snooze and done
        actions = []
        if reminder_id:
            api_base = self.vault.retrieve("sentinel_api_base",
                                            "http://localhost:5009")
            actions.append(
                f"http, Snooze 15m, {api_base}/api/reminders/{reminder_id}/snooze"
            )
            actions.append(
                f"http, Done, {api_base}/api/reminders/{reminder_id}/done"
            )
        if actions:
            headers["Actions"] = "; ".join(actions)

        # Sanitize ALL headers via Factory utility (RFC 7230 ASCII guard)
        headers = safe_headers(headers)

        # Send
        result = {"status": "pending", "reminder_id": reminder_id}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, content=utf8_body(body),
                                         headers=headers)
                resp.raise_for_status()
                result = {
                    "status": "delivered",
                    "reminder_id": reminder_id,
                    "ntfy_status": resp.status_code,
                    "topic": topic,
                    "title": title,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                logger.info("✅ Notification sent: %s", title)
        except Exception as exc:
            result = {
                "status": "failed",
                "reminder_id": reminder_id,
                "error": str(exc),
                "title": title,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            logger.error("❌ Notification failed: %s — %s", title, exc)

        self._delivery_log.append(result)
        self._save_log()
        return result

    async def send_test(self) -> dict:
        """Send a test notification to verify setup."""
        return await self.send_reminder(
            category="AI",
            activity="Sentinel Bridge Connected",
            time_str=datetime.now(timezone.utc).strftime("%I:%M %p"),
            priority="normal",
            reminder_id="test_001",
            extra_body="🛡️ Your Sentinel Bridge is active and monitoring.",
        )

    def get_delivery_stats(self) -> dict:
        """Delivery statistics for telemetry."""
        total = len(self._delivery_log)
        delivered = sum(1 for d in self._delivery_log
                        if d.get("status") == "delivered")
        failed = sum(1 for d in self._delivery_log
                     if d.get("status") == "failed")
        return {
            "total_sent": total,
            "delivered": delivered,
            "failed": failed,
            "success_rate": f"{(delivered/total*100):.1f}%" if total else "N/A",
            "last_sent": self._delivery_log[-1] if self._delivery_log else None,
        }

    # ── Persistence ──────────────────────────────────────────────────
    def _load_log(self) -> None:
        log_file = DATA_DIR / "delivery_log.json"
        if log_file.exists():
            try:
                self._delivery_log = json.loads(log_file.read_text())
            except Exception:
                self._delivery_log = []

    def _save_log(self) -> None:
        log_file = DATA_DIR / "delivery_log.json"
        recent = self._delivery_log[-1000:]
        log_file.write_text(json.dumps(recent, indent=2))
# V3 AUTO-HEAL ACTIVE
