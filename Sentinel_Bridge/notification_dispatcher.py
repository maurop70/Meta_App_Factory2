"""
Sentinel Bridge — Notification Dispatcher V2
=============================================
Pushes notifications via multi-channel routing with PII masking.

Channels (priority order):
  1. Push (ntfy.sh) — always available
  2. WhatsApp (Business API) — enabled when configured
  3. SMS (Twilio) — enabled when configured

Routing is controlled by routing_rules.json and Urgency_Score.
All outbound payloads pass through PII_Masker before delivery.
"""

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
from pii_masker import PIIMasker

logger = logging.getLogger("sentinel.dispatcher")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
ROUTING_RULES_PATH = Path(__file__).parent / "routing_rules.json"

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
    """Push notifications via multi-channel routing with PII safety."""

    def __init__(self, vault: FernetVault | None = None):
        self.vault = vault or FernetVault()
        self.pii = PIIMasker()
        self.routing_rules = self._load_routing_rules()
        self._delivery_log: list[dict] = []
        self._load_log()

    # ── Routing Rules ───────────────────────────────────────────────

    def _load_routing_rules(self) -> dict:
        """Load multi-channel routing configuration."""
        if ROUTING_RULES_PATH.exists():
            try:
                return json.loads(ROUTING_RULES_PATH.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Could not load routing_rules.json: %s", e)
        return {"channels": {}, "routing_rules": [], "fallback_chain": {"enabled": True, "order": ["push"]}}

    def _get_channels_for_urgency(self, urgency_score: int) -> list[str]:
        """Determine which channels to use based on urgency score."""
        for rule in self.routing_rules.get("routing_rules", []):
            if rule.get("urgency_min", 0) <= urgency_score <= rule.get("urgency_max", 10):
                # Filter to enabled channels only
                channels = []
                for ch in rule.get("channels", ["push"]):
                    ch_config = self.routing_rules.get("channels", {}).get(ch, {})
                    if ch_config.get("enabled", False) or ch == "push":
                        channels.append(ch)
                return channels if channels else ["push"]
        return ["push"]

    # ── Public API ───────────────────────────────────────────────────

    async def route_notification(self, *, category: str, activity: str,
                                  time_str: str, priority: str = "normal",
                                  urgency_score: int = 5,
                                  reminder_id: str = "",
                                  extra_body: str = "",
                                  callback_actions: list[dict] = None) -> dict:
        """
        Route a notification through the appropriate channels
        based on urgency_score and routing_rules.json.
        """
        channels = self._get_channels_for_urgency(urgency_score)
        results = {}
        success = False

        for channel in channels:
            try:
                if channel == "push":
                    result = await self._send_push(
                        category=category, activity=activity,
                        time_str=time_str, priority=priority,
                        reminder_id=reminder_id, extra_body=extra_body,
                        callback_actions=callback_actions,
                    )
                elif channel == "whatsapp":
                    result = await self._send_whatsapp(
                        activity=activity, time_str=time_str,
                        extra_body=extra_body,
                    )
                elif channel == "sms":
                    result = await self._send_sms(
                        activity=activity, time_str=time_str,
                    )
                else:
                    result = {"status": "unsupported", "channel": channel}

                results[channel] = result
                if result.get("status") == "delivered":
                    success = True
                    # If primary delivered and fallback not needed, conditionally break
                    if not self.routing_rules.get("fallback_chain", {}).get("enabled"):
                        break

            except Exception as e:
                results[channel] = {"status": "failed", "error": str(e)}
                logger.error("Channel %s failed: %s", channel, e)

                # Fallback: try next channel
                if self.routing_rules.get("fallback_chain", {}).get("enabled"):
                    logger.info("Falling back to next channel...")
                    continue
                break

        return {
            "overall_status": "delivered" if success else "failed",
            "channels_attempted": list(results.keys()),
            "channel_results": results,
            "urgency_score": urgency_score,
        }

    async def send_reminder(self, *, category: str, activity: str,
                            time_str: str, priority: str = "normal",
                            reminder_id: str = "",
                            extra_body: str = "",
                            urgency_score: int = None) -> dict:
        """
        Send a formatted reminder notification (V2 compatible).
        Routes through multi-channel if urgency_score provided,
        otherwise falls back to push-only for backward compat.
        """
        if urgency_score is not None:
            return await self.route_notification(
                category=category, activity=activity,
                time_str=time_str, priority=priority,
                urgency_score=urgency_score,
                reminder_id=reminder_id, extra_body=extra_body,
            )

        # V1 backward-compatible path: push-only
        return await self._send_push(
            category=category, activity=activity,
            time_str=time_str, priority=priority,
            reminder_id=reminder_id, extra_body=extra_body,
        )

    # ── Channel: Push (ntfy) ─────────────────────────────────────────

    async def _send_push(self, *, category: str, activity: str,
                         time_str: str, priority: str = "normal",
                         reminder_id: str = "",
                         extra_body: str = "",
                         callback_actions: list[dict] = None) -> dict:
        """Send via ntfy push notification."""
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

        # ── PII MASKING: strip sensitive data before external send ──
        body = self.pii.mask(body)
        title = self.pii.mask(title)

        # Determine ntfy config
        server = self.vault.retrieve("ntfy_server", DEFAULT_NTFY_SERVER)
        topic = self.vault.retrieve("ntfy_topic", DEFAULT_NTFY_TOPIC)
        url = f"{server}/{topic}"

        headers = {
            "Title": title,
            "Priority": PRIORITY_MAP.get(priority, "3"),
            "Tags": ",".join(tags),
        }

        # Add action buttons — interactive callbacks if provided
        actions = []
        if callback_actions:
            for cb in callback_actions:
                actions.append(
                    f"http, {cb.get('label', 'Action')}, {cb.get('url', '')}"
                )
        elif reminder_id:
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
        result = {"status": "pending", "channel": "push", "reminder_id": reminder_id}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, content=utf8_body(body),
                                         headers=headers)
                resp.raise_for_status()
                result = {
                    "status": "delivered",
                    "channel": "push",
                    "reminder_id": reminder_id,
                    "ntfy_status": resp.status_code,
                    "topic": topic,
                    "title": title,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                logger.info("✅ Push sent: %s", title)
        except Exception as exc:
            result = {
                "status": "failed",
                "channel": "push",
                "reminder_id": reminder_id,
                "error": str(exc),
                "title": title,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            logger.error("❌ Push failed: %s — %s", title, exc)

        self._delivery_log.append(result)
        self._save_log()
        return result

    # ── Channel: WhatsApp (stub) ─────────────────────────────────────

    async def _send_whatsapp(self, *, activity: str, time_str: str,
                              extra_body: str = "") -> dict:
        """
        WhatsApp Business API channel (stub).
        Enable by setting whatsapp_api_key in the Fernet vault
        and enabling the channel in routing_rules.json.
        """
        api_key = self.vault.retrieve("whatsapp_api_key")
        phone = self.vault.retrieve("whatsapp_phone")

        if not api_key or not phone:
            logger.info("📱 WhatsApp not configured — skipping")
            return {"status": "skipped", "channel": "whatsapp",
                    "reason": "not_configured"}

        # Build message
        message = f"🛡️ Sentinel Bridge\n{activity}"
        if time_str:
            message += f"\n⏰ {time_str}"
        if extra_body:
            message += f"\n{extra_body}"

        # PII Mask
        message = self.pii.mask(message)

        # TODO: Implement WhatsApp Business API call here
        logger.info("📱 WhatsApp delivery queued (stub): %s", activity[:50])
        return {"status": "stub", "channel": "whatsapp",
                "message": "WhatsApp integration pending"}

    # ── Channel: SMS (stub) ──────────────────────────────────────────

    async def _send_sms(self, *, activity: str, time_str: str) -> dict:
        """
        SMS via Twilio (stub).
        Enable by setting twilio_sid, twilio_auth_token, twilio_phone
        in the Fernet vault and enabling the channel in routing_rules.json.
        """
        twilio_sid = self.vault.retrieve("twilio_sid")
        twilio_token = self.vault.retrieve("twilio_auth_token")
        twilio_phone = self.vault.retrieve("twilio_phone")

        if not all([twilio_sid, twilio_token, twilio_phone]):
            logger.info("📲 SMS (Twilio) not configured — skipping")
            return {"status": "skipped", "channel": "sms",
                    "reason": "not_configured"}

        # Build SMS body (concise for 160 char limit)
        sms_body = f"Sentinel: {activity}"
        if time_str:
            sms_body += f" at {time_str}"
        sms_body = sms_body[:160]

        # PII Mask
        sms_body = self.pii.mask(sms_body)

        # TODO: Implement Twilio API call here
        logger.info("📲 SMS delivery queued (stub): %s", activity[:50])
        return {"status": "stub", "channel": "sms",
                "message": "Twilio SMS integration pending"}

    # ── Test & Stats ─────────────────────────────────────────────────

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

        # Per-channel breakdown
        channels = {}
        for d in self._delivery_log:
            ch = d.get("channel", "push")
            if ch not in channels:
                channels[ch] = {"delivered": 0, "failed": 0, "total": 0}
            channels[ch]["total"] += 1
            if d.get("status") == "delivered":
                channels[ch]["delivered"] += 1
            elif d.get("status") == "failed":
                channels[ch]["failed"] += 1

        return {
            "total_sent": total,
            "delivered": delivered,
            "failed": failed,
            "success_rate": f"{(delivered/total*100):.1f}%" if total else "N/A",
            "channel_breakdown": channels,
            "last_sent": self._delivery_log[-1] if self._delivery_log else None,
            "routing_rules_loaded": bool(self.routing_rules.get("channels")),
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
