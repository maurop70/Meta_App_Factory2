"""
Sentinel Bridge — FastAPI Server  v2.0
========================================
Main application server providing:
- REST API for reminder management (CRUD + archive)
- Calendar poll scheduling (APScheduler)
- Manual reminder creation (text + voice)
- Category override endpoint (ML feedback loop)
- Self-healing wrapper on all pipeline stages
- ntfy push delivery
- Dashboard API for the web UI
- Calendar visualization endpoint
- ngrok heartbeat with dynamic URL notifications

Port: 5009 (configurable via SENTINEL_PORT env)
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
import uuid
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, HTTPException, Query, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ── Local imports ────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))  # Factory root for utils

from fernet_vault import FernetVault
from calendar_poller import CalendarPoller
from aether_ingestion import AetherIngestion
from categorization_engine import CategorizationEngine
from notification_dispatcher import NotificationDispatcher
from intent_extractor import IntentExtractor
from self_heal import SelfHealEngine
from utils.google_auth import GoogleAuth
from utils.tunnel_manager import TunnelManager

# ── Config ───────────────────────────────────────────────────────────
PORT = int(os.environ.get("SENTINEL_PORT", 5009))
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
REMINDERS_FILE = DATA_DIR / "reminders.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sentinel.server")

# ── Singletons ───────────────────────────────────────────────────────
vault = FernetVault()

# ── Factory-level shared modules ─────────────────────────────────────
google_auth = GoogleAuth(
    vault=vault,
    client_id_key="google_client_id",
    client_secret_key="google_client_secret",
    scopes=[
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    ],
    redirect_uri=f"http://localhost:{PORT}/api/auth/google/callback",
)

poller = CalendarPoller(vault=vault, google_auth=google_auth)
aether = AetherIngestion()
categorizer = CategorizationEngine()
dispatcher = NotificationDispatcher(vault=vault)
extractor = IntentExtractor()
healer = SelfHealEngine()

tunnel_mgr = TunnelManager()

# ── Scheduler ────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler()


# ── Reminder Store ───────────────────────────────────────────────────
def load_reminders() -> list[dict]:
    if REMINDERS_FILE.exists():
        try:
            return json.loads(REMINDERS_FILE.read_text())
        except Exception:
            return []
    return []


def save_reminders(reminders: list[dict]) -> None:
    REMINDERS_FILE.write_text(json.dumps(reminders, indent=2))


reminders_store: list[dict] = load_reminders()


# ── Pipeline: Calendar → Categorize → Notify ────────────────────────
async def calendar_pipeline():
    """Full pipeline: poll → ingest → categorize → notify."""
    logger.info("🔄 Running calendar pipeline…")
    try:
        new_events = await poller.poll_new(lookahead_hours=48)
        if not new_events:
            logger.info("No new calendar events.")
            return

        for event in new_events:
            # Aether ingestion
            aether_input = aether.process_calendar_event(event.to_dict())

            # Categorization (with ML engine)
            cat_result = categorizer.categorize(
                aether_input.raw_text,
                hints={"calendar_label": event.calendar_label},
            )

            # Build reminder
            reminder = {
                "id": str(uuid.uuid4())[:8],
                "activity": event.summary,
                "category": cat_result["category"],
                "confidence": cat_result["confidence"],
                "time": event.start,
                "source": "calendar",
                "source_account": event.source_account,
                "priority": aether_input.priority,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            reminders_store.append(reminder)

            # Push notification
            await dispatcher.send_reminder(
                category=cat_result["category"],
                activity=event.summary,
                time_str=_format_time(event.start),
                priority=aether_input.priority,
                reminder_id=reminder["id"],
            )

        save_reminders(reminders_store)
        logger.info("✅ Processed %d new events.", len(new_events))

    except Exception as exc:
        logger.error("Calendar pipeline error: %s", exc)
        # Self-heal will catch this when wrapped
        raise


# Wrap pipeline in self-healing
@healer.protect("calendar_pipeline")
async def safe_calendar_pipeline():
    await calendar_pipeline()


def _format_time(iso_str: str) -> str:
    """Format ISO time to human-readable."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%I:%M %p, %b %d")
    except Exception:
        return iso_str


# ── Pydantic Models ──────────────────────────────────────────────────
class ManualReminderInput(BaseModel):
    text: str
    source: str = "manual"  # "manual" or "voice"


class ReminderEdit(BaseModel):
    activity: str | None = None
    time: str | None = None
    category: str | None = None
    description: str | None = None
    lock_category: bool = False  # if True, skip re-categorization


class CategoryOverride(BaseModel):
    new_category: str


class NewCategoryInput(BaseModel):
    name: str


class CustomRuleInput(BaseModel):
    pattern: str
    category: str


class VaultSecret(BaseModel):
    key: str
    value: str


class SnoozeInput(BaseModel):
    """Configurable snooze duration."""
    minutes: int = 15


# ── Quiet Hours (Master Architect: priority queuing + quiet hours) ────
def _should_notify(priority: str = "normal") -> bool:
    """Skip non-high-priority notifications during quiet hours (10PM-7AM)."""
    from datetime import datetime
    hour = datetime.now().hour
    if priority == "high":
        return True  # Always notify for high priority
    return 7 <= hour < 22  # Quiet hours: 10PM-7AM


async def _notify_state_change(reminder: dict, action: str, detail: str = ""):
    """Send notification for reminder state changes with quiet hours."""
    priority = reminder.get("priority", "normal")
    if not _should_notify(priority):
        logger.info(f"Skipped notification (quiet hours): {action} - {reminder.get('activity', '')}")
        return
    await dispatcher.send_reminder(
        category=reminder.get("category", "Other"),
        activity=f"{action}: {reminder.get('activity', 'Unknown')}",
        time_str=detail or reminder.get("time", "N/A"),
        priority=priority,
        reminder_id=reminder.get("id", ""),
    )


# ── Lifespan ─────────────────────────────────────────────────────────
# ── Category → Calendar mapping ──────────────────────────────────────
CALENDAR_MAP = {
    "Work": "work",
    "AI": "work",
    "Leo's School": "personal",
    "Family": "personal",
}

CALENDAR_EMAILS = {
    "work": "mpetrini@heinleinfoodsusa.com",
    "personal": "mauro@gelatopetrini.com",
}


async def write_to_google_calendar(category: str, summary: str,
                                    start_iso: str, description: str = ""):
    """Write an event to the appropriate Google Calendar based on category."""
    account_id = CALENDAR_MAP.get(category, "personal")
    calendar_email = CALENDAR_EMAILS[account_id]
    token = await google_auth.get_valid_token(account_id)
    if not token:
        logger.warning("Cannot write to calendar — no valid token for %s", account_id)
        return None

    # Parse start time
    try:
        if start_iso:
            start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        else:
            start_dt = datetime.now(timezone.utc) + timedelta(hours=1)
        end_dt = start_dt + timedelta(hours=1)
    except Exception:
        start_dt = datetime.now(timezone.utc) + timedelta(hours=1)
        end_dt = start_dt + timedelta(hours=1)

    event_body = {
        "summary": summary,
        "description": description or f"Created by Sentinel Bridge [{category}]",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "America/New_York"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "America/New_York"},
    }

    import httpx as _httpx
    url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events"
    try:
        async with _httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=event_body,
                                     headers={"Authorization": f"Bearer {token}"})
        if resp.status_code in (200, 201):
            logger.info("📅 Event written to %s calendar: %s", account_id, summary)
            return resp.json()
        else:
            logger.error("Failed to write calendar event (HTTP %d): %s",
                         resp.status_code, resp.text[:200])
            return None
    except Exception as exc:
        logger.error("Calendar write error: %s", exc)
        return None


# ── Tunnel heartbeat check ───────────────────────────────────────────
async def tunnel_heartbeat():
    """Check if ngrok URL changed; notify Mauro via ntfy if so."""
    hb = tunnel_mgr.check_heartbeat("Sentinel_Bridge")
    if not hb["alive"]:
        logger.warning("📡 Tunnel dead — attempting force reconnect")
        new_url = tunnel_mgr.force_reconnect(port=PORT, app_name="Sentinel_Bridge")
        if new_url:
            app.state.ngrok_url = new_url
            # Notify Mauro of the new URL
            await dispatcher.send_reminder(
                category="AI",
                activity="🔗 Sentinel Bridge URL Updated",
                time_str=datetime.now(timezone.utc).strftime("%I:%M %p"),
                priority="high",
                extra_body=f"New link: {new_url}/dashboard\n"
                           f"Update your mobile shortcut.",
            )
    elif hb["changed"]:
        logger.info("📡 URL changed detected via heartbeat")
        await dispatcher.send_reminder(
            category="AI",
            activity="🔗 Sentinel Bridge URL Changed",
            time_str=datetime.now(timezone.utc).strftime("%I:%M %p"),
            priority="high",
            extra_body=f"New link: {hb['url']}/dashboard\n"
                       f"Old link: {hb['old_url']}\n"
                       f"Update your mobile shortcut.",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    logger.info("🛡️ Sentinel Bridge v2.0 starting on port %d…", PORT)
    logger.info("📆 Calendar accounts: %s",
                [a["email"] for a in poller.get_active_accounts()])

    # Schedule calendar polling twice daily: noon and midnight
    scheduler.add_job(safe_calendar_pipeline, "cron", hour="0,12",
                      id="calendar_poll", replace_existing=True)
    # Also run immediately on startup
    scheduler.add_job(safe_calendar_pipeline, "date", id="startup_poll",
                      run_date=datetime.now(timezone.utc))

    # Schedule tunnel heartbeat every 5 minutes
    scheduler.add_job(tunnel_heartbeat, "interval", minutes=5,
                      id="tunnel_heartbeat", replace_existing=True)
    scheduler.start()

    # ── ngrok tunnel — force reconnect to kill stale endpoints ──
    ngrok_url = tunnel_mgr.force_reconnect(port=PORT, app_name="Sentinel_Bridge")
    if not ngrok_url:
        # Fallback to regular open
        ngrok_url = tunnel_mgr.open(port=PORT, app_name="Sentinel_Bridge")
    if ngrok_url:
        logger.info("📱 Mobile access: %s/dashboard", ngrok_url)
    else:
        logger.warning("⚠️ ngrok unavailable — local-only mode")

    # Store ngrok URL for API access
    app.state.ngrok_url = ngrok_url

    yield

    # Cleanup
    tunnel_mgr.close("Sentinel_Bridge")
    scheduler.shutdown()
    save_reminders(reminders_store)
    logger.info("🛡️ Sentinel Bridge shut down cleanly.")


# ── App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Sentinel Bridge",
    description="Autonomous Reminder System by Meta App Factory",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files (dashboard) ────────────────────────────────────────
UI_DIST = Path(__file__).parent / "sentinel_ui" / "dist"
if UI_DIST.exists():
    app.mount("/ui", StaticFiles(directory=str(UI_DIST), html=True),
              name="sentinel-ui")


# ═══════════════════════════════════════════════════════════════════
#  API ROUTES
# ═══════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Health check / welcome."""
    return {
        "app": "Sentinel Bridge",
        "version": "2.0.0",
        "status": "active",
        "port": PORT,
        "dashboard": f"http://localhost:{PORT}/dashboard",
        "ngrok_url": getattr(app.state, "ngrok_url", None),
        "uptime": datetime.now(timezone.utc).isoformat(),
        "endpoints": {
            "dashboard": "/dashboard",
            "reminders": "/api/reminders",
            "add_reminder": "/api/reminders (POST)",
            "edit_reminder": "/api/reminders/{id} (PUT)",
            "archive_reminder": "/api/reminders/{id}/archive (PUT)",
            "calendar_events": "/api/calendar/events",
            "tunnel_status": "/api/tunnel/status",
            "categories": "/api/categories",
            "telemetry": "/api/telemetry",
            "vault": "/api/vault/audit",
        },
    }


@app.get("/manifest.json")
async def manifest():
    """PWA Web App Manifest."""
    return JSONResponse(content={
        "name": "Sentinel Bridge",
        "short_name": "Sentinel",
        "start_url": "/dashboard",
        "display": "standalone",
        "background_color": "#0f0f1a",
        "theme_color": "#0f0f1a",
        "description": "Autonomous Reminder System",
        "icons": [
            {
                "src": "data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🛡️</text></svg>",
                "sizes": "192x192",
                "type": "image/svg+xml"
            },
            {
                "src": "data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🛡️</text></svg>",
                "sizes": "512x512",
                "type": "image/svg+xml"
            }
        ]
    })


@app.get("/sw.js")
async def service_worker():
    """Minimal Service Worker for PWA compliance."""
    sw_content = """
    const CACHE_NAME = 'sentinel-v1';
    self.addEventListener('install', (event) => {
        event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(['/dashboard'])));
    });
    self.addEventListener('fetch', (event) => {
        event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
    });
    """
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=sw_content, media_type="application/javascript")


@app.get("/dashboard")
async def dashboard():
    """Serve the Sentinel Bridge dashboard."""
    dashboard_file = Path(__file__).parent / "dashboard.html"
    if dashboard_file.exists():
        return HTMLResponse(content=dashboard_file.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="Dashboard not found")


# ── Reminders ────────────────────────────────────────────────────────
@app.get("/api/reminders")
async def list_reminders(status: str = Query(None),
                          category: str = Query(None)):
    """List all reminders, optionally filtered."""
    result = reminders_store
    if status:
        result = [r for r in result if r.get("status") == status]
    if category:
        result = [r for r in result if r.get("category") == category]
    return {"reminders": result, "total": len(result)}


@app.post("/api/reminders")
async def create_reminder(input_data: ManualReminderInput):
    """Create a reminder from manual text or voice-to-text."""
    # Aether ingestion
    aether_input = aether.process_text(input_data.text, input_data.source)

    # Intent extraction
    intent = extractor.extract(input_data.text)

    # Categorization
    cat_result = categorizer.categorize(aether_input.raw_text)

    # Build reminder
    reminder = {
        "id": str(uuid.uuid4())[:8],
        "activity": intent.activity,
        "category": cat_result["category"],
        "confidence": cat_result["confidence"],
        "time": intent.when.isoformat() if intent.when else aether_input.extracted_time,
        "source": input_data.source,
        "priority": intent.urgency,
        "recurrence": intent.recurrence,
        "status": "pending",
        "raw_text": input_data.text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    reminders_store.append(reminder)
    save_reminders(reminders_store)

    # Push notification
    await dispatcher.send_reminder(
        category=cat_result["category"],
        activity=intent.activity,
        time_str=intent.when_text or _format_time(reminder["time"]),
        priority=intent.urgency,
        reminder_id=reminder["id"],
    )

    # Auto-write to the correct Google Calendar
    cal_result = await write_to_google_calendar(
        category=cat_result["category"],
        summary=intent.activity,
        start_iso=reminder["time"],
        description=f"Category: {cat_result['category']}\nSource: {input_data.source}\n"
                    f"Raw: {input_data.text}",
    )
    reminder["google_event_id"] = (cal_result or {}).get("id")
    reminder["calendar_account"] = CALENDAR_EMAILS.get(
        CALENDAR_MAP.get(cat_result["category"], "personal"), "")
    save_reminders(reminders_store)

    return {
        "status": "created",
        "reminder": reminder,
        "categorization": cat_result,
        "calendar_written": cal_result is not None,
        "calendar_account": reminder.get("calendar_account", ""),
    }


@app.put("/api/reminders/{reminder_id}/category")
async def override_category(reminder_id: str, override: CategoryOverride):
    """Override a reminder's category (triggers ML feedback loop)."""
    reminder = next((r for r in reminders_store if r["id"] == reminder_id), None)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    old_category = reminder["category"]
    raw_text = reminder.get("raw_text", reminder.get("activity", ""))

    # Apply override
    reminder["category"] = override.new_category
    reminder["confidence"] = 1.0  # user-confirmed

    # Feed back to ML engine
    ml_result = categorizer.override_category(
        reminder_id=reminder_id,
        original_text=raw_text,
        old_category=old_category,
        new_category=override.new_category,
    )

    save_reminders(reminders_store)

    # Notification
    await _notify_state_change(reminder, "Category changed",
                                f"{old_category} -> {override.new_category}")

    return {
        "status": "category_updated",
        "old_category": old_category,
        "new_category": override.new_category,
        "ml_feedback": ml_result,
    }


@app.post("/api/reminders/{reminder_id}/snooze")
async def snooze_reminder(reminder_id: str, snooze: SnoozeInput = SnoozeInput()):
    """Snooze a reminder for a configurable number of minutes."""
    reminder = next((r for r in reminders_store if r["id"] == reminder_id), None)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    reminder["status"] = "snoozed"
    snooze_until = datetime.now(timezone.utc) + timedelta(minutes=snooze.minutes)
    reminder["snoozed_until"] = snooze_until.isoformat()
    save_reminders(reminders_store)

    # Notification
    await _notify_state_change(reminder, "Snoozed", f"until {snooze_until.strftime('%I:%M %p')}")

    return {"status": "snoozed", "reminder_id": reminder_id, "snoozed_until": reminder["snoozed_until"]}


@app.post("/api/reminders/{reminder_id}/done")
async def mark_done(reminder_id: str):
    """Mark a reminder as completed and remove from Google Calendar."""
    reminder = next((r for r in reminders_store if r["id"] == reminder_id), None)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    reminder["status"] = "done"
    reminder["completed_at"] = datetime.now(timezone.utc).isoformat()
    save_reminders(reminders_store)

    # Notification
    await _notify_state_change(reminder, "Completed")

    # Delete from Google Calendar if event exists
    event_id = reminder.get("google_event_id")
    if event_id:
        try:
            account_id = CALENDAR_MAP.get(reminder.get("category", ""), "personal")
            token = await google_auth.get_valid_token(account_id)
            if token:
                import httpx as _hx
                url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}"
                async with _hx.AsyncClient(timeout=10) as client:
                    await client.delete(url, headers={"Authorization": f"Bearer {token}"})
                logger.info(f"Deleted calendar event {event_id} for completed reminder")
        except Exception as e:
            logger.warning(f"Calendar delete failed: {e}")

    return {"status": "done", "reminder_id": reminder_id}


@app.put("/api/reminders/{reminder_id}")
async def edit_reminder(reminder_id: str, edit: ReminderEdit):
    """
    Edit a reminder's fields. Re-runs Aether pipeline for consistency
    unless lock_category is True.
    """
    reminder = next((r for r in reminders_store if r["id"] == reminder_id), None)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    # Update fields
    if edit.activity is not None:
        reminder["activity"] = edit.activity
    if edit.time is not None:
        reminder["time"] = edit.time
    if edit.description is not None:
        reminder["description"] = edit.description

    # Re-run Aether pipeline for consistency (unless category is locked)
    if not edit.lock_category:
        text = edit.activity or reminder.get("activity", "")
        if edit.category:
            # User explicitly chose a category
            reminder["category"] = edit.category
            reminder["confidence"] = 1.0
            # Feed ML engine
            categorizer.override_category(
                reminder_id=reminder_id,
                original_text=text,
                old_category=reminder.get("category", ""),
                new_category=edit.category,
            )
        else:
            # Re-categorize through Aether
            aether_input = aether.process_text(text, reminder.get("source", "manual"))
            cat_result = categorizer.categorize(aether_input.raw_text)
            reminder["category"] = cat_result["category"]
            reminder["confidence"] = cat_result["confidence"]
    elif edit.category:
        reminder["category"] = edit.category

    reminder["edited_at"] = datetime.now(timezone.utc).isoformat()
    save_reminders(reminders_store)

    # Notification on edits
    await _notify_state_change(reminder, "Updated", f"edited by user")

    # Update Google Calendar if event exists and time changed
    if edit.time and reminder.get("google_event_id"):
        try:
            cal_result = await write_to_google_calendar(
                category=reminder.get("category", "Other"),
                summary=reminder.get("activity", ""),
                start_iso=edit.time,
                description=f"[Sentinel] Updated reminder",
            )
            if cal_result:
                reminder["google_event_id"] = cal_result.get("id")
                save_reminders(reminders_store)
        except Exception as e:
            logger.warning(f"Calendar update failed: {e}")

    return {"status": "updated", "reminder": reminder}


@app.put("/api/reminders/{reminder_id}/archive")
async def archive_reminder(reminder_id: str):
    """Archive a reminder (swipe-to-archive from mobile)."""
    reminder = next((r for r in reminders_store if r["id"] == reminder_id), None)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    reminder["status"] = "archived"
    reminder["archived_at"] = datetime.now(timezone.utc).isoformat()
    save_reminders(reminders_store)

    # Notification
    await _notify_state_change(reminder, "Archived")

    return {"status": "archived", "reminder_id": reminder_id}


# ── Categories ───────────────────────────────────────────────────────
@app.get("/api/categories")
async def list_categories():
    """List all categories and engine stats."""
    stats = categorizer.get_stats()
    return stats


@app.post("/api/categories")
async def add_category(input_data: NewCategoryInput):
    """Add a new user-defined category."""
    added = categorizer.add_category(input_data.name)
    return {"added": added, "category": input_data.name}


@app.post("/api/categories/rules")
async def add_rule(input_data: CustomRuleInput):
    """Add a custom categorization rule."""
    rule = categorizer.add_custom_rule(input_data.pattern, input_data.category)
    return {"rule": rule}


# ── Calendar ─────────────────────────────────────────────────────────
@app.get("/api/calendar/accounts")
async def calendar_accounts():
    """List configured calendar accounts."""
    accounts = poller.get_active_accounts()
    # Add auth status
    for acc in accounts:
        token = vault.retrieve(f"google_token_{acc['id']}")
        acc["authorized"] = token is not None
    return {"accounts": accounts}


@app.post("/api/calendar/poll")
async def trigger_poll():
    """Manually trigger a calendar poll."""
    await safe_calendar_pipeline()
    return {"status": "poll_complete"}


@app.get("/api/calendar/freebusy")
async def calendar_freebusy(days: int = Query(7, ge=1, le=14)):
    """
    Smart Scheduling: query Google Calendar free/busy across all accounts,
    find open time slots in the next N days during working hours (8AM-6PM).
    Returns suggested slots for task scheduling.
    """
    import httpx as _hx

    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=days)).isoformat()

    # Collect busy blocks from all calendar accounts
    all_busy = []
    accounts_queried = []

    for account_id, email in CALENDAR_EMAILS.items():
        token = await google_auth.get_valid_token(account_id)
        if not token:
            continue

        try:
            url = "https://www.googleapis.com/calendar/v3/freeBusy"
            body = {
                "timeMin": time_min,
                "timeMax": time_max,
                "items": [{"id": "primary"}],
            }
            async with _hx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url, json=body,
                    headers={"Authorization": f"Bearer {token}",
                             "Content-Type": "application/json"},
                )
            if resp.status_code == 200:
                data = resp.json()
                cal_busy = data.get("calendars", {}).get("primary", {}).get("busy", [])
                for block in cal_busy:
                    all_busy.append({
                        "start": block["start"],
                        "end": block["end"],
                        "account": account_id,
                    })
                accounts_queried.append(account_id)
                logger.info(f"FreeBusy: {account_id} returned {len(cal_busy)} busy blocks")
            else:
                logger.warning(f"FreeBusy failed for {account_id}: HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"FreeBusy error for {account_id}: {e}")

    # Find free slots during working hours (8AM-6PM local time)
    # We'll generate candidate slots and exclude busy ones
    from zoneinfo import ZoneInfo
    local_tz = ZoneInfo("America/New_York")
    suggestions = []

    # Parse all busy periods into datetime ranges
    busy_ranges = []
    for b in all_busy:
        try:
            bs = datetime.fromisoformat(b["start"].replace("Z", "+00:00"))
            be = datetime.fromisoformat(b["end"].replace("Z", "+00:00"))
            busy_ranges.append((bs, be))
        except Exception:
            pass

    # Scan each day for 1-hour free slots during working hours
    for day_offset in range(days):
        day = (now + timedelta(days=day_offset)).astimezone(local_tz).date()
        if day == now.astimezone(local_tz).date():
            # Today: start from next full hour
            start_hour = max(8, now.astimezone(local_tz).hour + 1)
        else:
            start_hour = 8

        for hour in range(start_hour, 18):  # 8AM to 5PM (last slot starts at 5PM)
            slot_start = datetime(day.year, day.month, day.day, hour, 0,
                                  tzinfo=local_tz)
            slot_end = slot_start + timedelta(hours=1)

            # Check if this slot overlaps any busy period
            is_free = True
            for bs, be in busy_ranges:
                if slot_start < be and slot_end > bs:
                    is_free = False
                    break

            if is_free:
                day_label = "Today" if day_offset == 0 else (
                    "Tomorrow" if day_offset == 1 else
                    slot_start.strftime("%A %b %d"))
                suggestions.append({
                    "start": slot_start.isoformat(),
                    "end": slot_end.isoformat(),
                    "label": f"{day_label} {slot_start.strftime('%I:%M %p').lstrip('0')} - {slot_end.strftime('%I:%M %p').lstrip('0')}",
                    "day_offset": day_offset,
                })

        # Limit suggestions per day to top 3
        if len(suggestions) >= 15:
            break

    return {
        "suggestions": suggestions[:15],
        "busy_blocks": len(all_busy),
        "accounts_queried": accounts_queried,
        "range_days": days,
    }


@app.get("/api/calendar/events")
async def calendar_events(month: int = Query(None), year: int = Query(None)):
    """
    Get unified calendar events (reminders + calendar events) for the
    calendar visualization tab. Color-coded by category.
    """
    now = datetime.now(timezone.utc)
    target_month = month or now.month
    target_year = year or now.year

    # Category → color mapping for calendar view
    cat_colors = {
        "AI": "#7c3aed",         # Purple
        "Work": "#2563eb",       # Blue
        "Leo's School": "#eab308",  # Yellow
        "Family": "#10b981",      # Green
    }

    events = []
    for r in reminders_store:
        if r.get("status") == "archived":
            continue
        # Parse the time
        time_str = r.get("time", "")
        try:
            if "T" in str(time_str):
                dt = datetime.fromisoformat(str(time_str).replace("Z", "+00:00"))
            elif time_str:
                dt = datetime.fromisoformat(str(time_str))
            else:
                continue
        except Exception:
            continue

        if dt.month == target_month and dt.year == target_year:
            cat = r.get("category", "Uncategorized")
            events.append({
                "id": r.get("id"),
                "title": r.get("activity", "Untitled"),
                "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%I:%M %p") if "T" in str(time_str) else "All day",
                "datetime": dt.isoformat(),
                "category": cat,
                "color": cat_colors.get(cat, "#6b7280"),
                "source": r.get("source", "manual"),
                "status": r.get("status", "pending"),
                "description": r.get("description", ""),
            })

    # Sort by datetime
    events.sort(key=lambda e: e["datetime"])

    return {
        "month": target_month,
        "year": target_year,
        "events": events,
        "total": len(events),
        "category_colors": cat_colors,
    }


# ── Google OAuth2 Web Flow (via factory GoogleAuth) ──────────────────
@app.get("/api/auth/google")
async def google_auth_start(account: str = Query("work")):
    """
    Start Google OAuth2 flow via factory-level GoogleAuth module.
    
    Usage:
        Open in browser: http://localhost:5009/api/auth/google?account=work
        Or:               http://localhost:5009/api/auth/google?account=personal
    """
    if not google_auth.client_id:
        raise HTTPException(status_code=500,
                            detail="Google client_id not in vault")

    auth_url = google_auth.get_auth_url(account)
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=auth_url)


@app.get("/api/auth/google/callback")
async def google_auth_callback(code: str = Query(...),
                                 state: str = Query("work")):
    """
    OAuth2 callback — delegates to factory GoogleAuth for token exchange.
    N8N_SKIP_AUTH_ON_OAUTH_CALLBACK: when set, bypass any n8n auth
    middleware that might block the callback (fixes 401 errors).
    """
    # N8N auth bypass guard
    skip_n8n = os.environ.get("N8N_SKIP_AUTH_ON_OAUTH_CALLBACK", "true").lower()
    if skip_n8n == "true":
        logger.info("OAuth callback — N8N auth bypass active")

    try:
        await google_auth.exchange_code(code, state)
    except RuntimeError as exc:
        return HTMLResponse(
            content=f"<h2>Authorization Failed</h2>"
                    f"<p>{exc}</p>"
                    f"<p><a href='/api/auth/google?account={state}'>Try again</a></p>",
            status_code=400,
        )

    # Find account email
    account_email = state
    for acc in poller.get_active_accounts():
        if acc["id"] == state:
            account_email = acc["email"]
            break

    return HTMLResponse(content=f"""
    <html>
    <head><title>Sentinel Bridge — Authorized</title></head>
    <body style="font-family: system-ui; max-width: 600px; margin: 80px auto; text-align: center;">
        <h1>✅ Calendar Authorized!</h1>
        <p><strong>{account_email}</strong> is now connected to Sentinel Bridge.</p>
        <p>Calendar events will be polled every 15 minutes.</p>
        <br>
        <p>
            <a href="/api/auth/google?account={'personal' if state == 'work' else 'work'}"
               style="padding: 10px 24px; background: #2563EB; color: white; 
                      text-decoration: none; border-radius: 6px;">
                Authorize {'Personal' if state == 'work' else 'Work'} Calendar
            </a>
        </p>
        <br>
        <p><a href="/api/calendar/accounts">View all accounts</a> |
           <a href="/api/telemetry">Telemetry</a></p>
    </body>
    </html>
    """)


@app.get("/api/auth/status")
async def auth_status():
    """Check authorization status via factory GoogleAuth module."""
    accounts = poller.get_active_accounts()
    return google_auth.get_status(accounts)


# ── Notifications ────────────────────────────────────────────────────
@app.post("/api/notifications/test")
async def test_notification():
    """Send a test notification to ntfy."""
    result = await dispatcher.send_test()
    return result


@app.get("/api/notifications/stats")
async def notification_stats():
    """Delivery statistics."""
    return dispatcher.get_delivery_stats()


# ── Vault (admin) ────────────────────────────────────────────────────
@app.get("/api/vault/audit")
async def vault_audit():
    """Non-sensitive vault audit info."""
    return vault.export_audit()


@app.post("/api/vault/store")
async def vault_store(secret: VaultSecret):
    """Store a secret in the encrypted vault."""
    vault.store(secret.key, secret.value)
    return {"status": "stored", "key": secret.key}


# ── Tunnel Status ────────────────────────────────────────────────────
@app.get("/api/tunnel/status")
async def tunnel_status():
    """Current ngrok tunnel status and URL."""
    hb = tunnel_mgr.check_heartbeat("Sentinel_Bridge")
    return {
        "url": getattr(app.state, "ngrok_url", None) or hb.get("url"),
        "alive": hb["alive"],
        "changed": hb["changed"],
        "old_url": hb.get("old_url"),
        "checked_at": hb["checked_at"],
    }


@app.post("/api/tunnel/reconnect")
async def tunnel_reconnect():
    """Force-reconnect the ngrok tunnel."""
    new_url = tunnel_mgr.force_reconnect(port=PORT, app_name="Sentinel_Bridge")
    if new_url:
        app.state.ngrok_url = new_url
        return {"status": "reconnected", "url": new_url}
    return {"status": "failed", "url": None}


# ── Telemetry ────────────────────────────────────────────────────────
@app.get("/api/telemetry")
async def telemetry():
    """Unified telemetry dashboard data."""
    return {
        "app": "Sentinel Bridge",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ngrok_url": getattr(app.state, "ngrok_url", None),
        "reminders": {
            "total": len(reminders_store),
            "pending": sum(1 for r in reminders_store if r.get("status") == "pending"),
            "done": sum(1 for r in reminders_store if r.get("status") == "done"),
            "snoozed": sum(1 for r in reminders_store if r.get("status") == "snoozed"),
            "archived": sum(1 for r in reminders_store if r.get("status") == "archived"),
        },
        "categorization": categorizer.get_stats(),
        "notifications": dispatcher.get_delivery_stats(),
        "selfheal": healer.get_heal_stats(),
        "vault": vault.export_audit(),
        "calendar_accounts": poller.get_active_accounts(),
    }

# ── Manual Task Creation (with Calendar write-back) ──────────────────
class TaskCreate(BaseModel):
    """Request body for manual task creation."""
    activity: str
    category: str = "Ops"
    due_date: str | None = None          # ISO date: 2026-04-15 or 2026-04-15T09:00:00
    priority: str = "normal"             # high | normal | low
    description: str = ""


@app.post("/api/tasks")
async def create_task(task: TaskCreate):
    """
    Create a manual task/reminder and sync it to Google Calendar.

    Usage (dashboard form or API):
        POST /api/tasks
        { "activity": "Board meeting", "category": "Ops",
          "due_date": "2026-04-15T09:00:00", "priority": "high" }
    """
    now = datetime.now(timezone.utc)

    reminder = {
        "id": str(uuid.uuid4())[:8],
        "activity": task.activity[:120],
        "description": task.description[:300],
        "category": task.category,
        "confidence": 1.0,
        "time": task.due_date or now.isoformat(),
        "source": "manual",
        "priority": task.priority,
        "status": "pending",
        "raw_text": task.description or task.activity,
        "created_at": now.isoformat(),
    }

    reminders_store.append(reminder)
    save_reminders(reminders_store)

    # ── Calendar write-back ──
    if task.due_date:
        try:
            cal_result = await write_to_google_calendar(
                category=task.category,
                summary=task.activity,
                start_iso=task.due_date,
                description=f"[Sentinel] {task.description}" if task.description else f"[Sentinel] Manual task",
            )
            reminder["google_event_id"] = (cal_result or {}).get("id")
            save_reminders(reminders_store)
        except Exception as cal_exc:
            logger.warning(f"Calendar write-back failed for '{task.activity}': {cal_exc}")

    # ── Push notification for high-priority ──
    if task.priority == "high":
        await dispatcher.send_reminder(
            category=task.category,
            activity=task.activity,
            time_str=task.due_date or "No due date",
            priority="high",
            reminder_id=reminder["id"],
        )

    logger.info(f"Manual task created: '{task.activity}' (due: {task.due_date}, cal_synced: {'google_event_id' in reminder})")

    return {
        "status": "created",
        "reminder": reminder,
        "calendar_synced": "google_event_id" in reminder,
    }


# ── Document Parser Upload ───────────────────────────────────────────
try:
    from document_parser_service import DocumentParserService
    from document_router import DocumentRouter
    _doc_parser = DocumentParserService()
    _doc_router = DocumentRouter()
    PARSER_AVAILABLE = True
    logger.info("DocumentParserService loaded.")
except ImportError:
    PARSER_AVAILABLE = False
    logger.warning("DocumentParserService not available — upload/parse disabled.")


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Parse an uploaded document, extract all activities, and
    create a separate reminder for each one.
    """
    if not PARSER_AVAILABLE:
        raise HTTPException(status_code=503, detail="DocumentParserService not available")

    upload_dir = DATA_DIR / "uploads"
    upload_dir.mkdir(exist_ok=True)
    dest = upload_dir / file.filename

    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)

    # Step 1: Standard parse (category, summary, routing)
    result = _doc_parser.parse(str(dest), source_app="Sentinel_Bridge")
    if result.get("status") != "parsed":
        return result

    result = _doc_router.route(result)
    _doc_parser.log_to_master_index(result)

    # Step 2: Extract individual activities from document text
    raw_text = result["extracted"].get("raw_text_preview", "")
    # Re-read full text for activity extraction
    try:
        with open(dest, "r", encoding="utf-8", errors="replace") as f:
            full_text = f.read()
    except Exception:
        full_text = raw_text

    activities = _doc_parser.extract_activities(full_text, file_name=file.filename)

    # Step 3: Create one reminder per activity
    created_reminders = []
    now = datetime.now(timezone.utc)

    for act in activities:
        reminder = {
            "id": str(uuid.uuid4())[:8],
            "activity": act["activity"],
            "description": act.get("description", ""),
            "category": act.get("category", result.get("category", "AI")),
            "confidence": result.get("confidence", 0.0),
            "time": act.get("due_date") or now.isoformat(),
            "source": "document_parser",
            "priority": act.get("priority", "normal"),
            "status": "pending",
            "raw_text": act.get("description", act["activity"]),
            "created_at": now.isoformat(),
            "parse_id": result["parse_id"],
            "source_file": file.filename,
        }
        reminders_store.append(reminder)
        created_reminders.append(reminder)

        # Push notification for high-priority activities
        if act.get("priority") == "high":
            await dispatcher.send_reminder(
                category=act.get("category", "AI"),
                activity=act["activity"],
                time_str=act.get("due_date", "No due date"),
                priority="high",
                reminder_id=reminder["id"],
            )

        # Calendar write-back for activities with due dates
        if act.get("due_date"):
            try:
                cal_result = await write_to_google_calendar(
                    category=reminder["category"],
                    summary=reminder["activity"],
                    start_iso=act["due_date"],
                    description=f"[Sentinel] Parsed from: {file.filename}\n{act.get('description', '')}",
                )
                reminder["google_event_id"] = (cal_result or {}).get("id")
            except Exception as cal_exc:
                logger.warning(f"Calendar write-back failed for '{act['activity']}': {cal_exc}")

    save_reminders(reminders_store)

    result["activities_extracted"] = len(created_reminders)
    result["reminders_created"] = created_reminders

    return result


# ── Self-Heal Dashboard ─────────────────────────────────────────────
@app.get("/api/selfheal")
async def selfheal_status():
    """Self-healing engine status."""
    return {
        "stats": healer.get_heal_stats(),
        "recent": healer.get_recent_heals(10),
    }


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "sentinel_server:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        log_level="info",
    )
# V3 AUTO-HEAL ACTIVE
