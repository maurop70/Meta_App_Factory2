"""
Sentinel Bridge — FastAPI Server
==================================
Main application server providing:
- REST API for reminder management
- Calendar poll scheduling (APScheduler)
- Manual reminder creation (text + voice)
- Category override endpoint (ML feedback loop)
- Self-healing wrapper on all pipeline stages
- ntfy push delivery
- Dashboard API for the web UI

Port: 5009 (configurable via SENTINEL_PORT env)
"""

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

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ── Local imports ────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from fernet_vault import FernetVault
from calendar_poller import CalendarPoller
from aether_ingestion import AetherIngestion
from categorization_engine import CategorizationEngine
from notification_dispatcher import NotificationDispatcher
from intent_extractor import IntentExtractor
from self_heal import SelfHealEngine

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
poller = CalendarPoller(vault=vault)
aether = AetherIngestion()
categorizer = CategorizationEngine()
dispatcher = NotificationDispatcher(vault=vault)
extractor = IntentExtractor()
healer = SelfHealEngine()

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
    token = vault.retrieve(f"google_token_{account_id}")
    if not token:
        logger.warning("Cannot write to calendar — no token for %s", account_id)
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
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_email}/events"
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    logger.info("🛡️ Sentinel Bridge starting on port %d…", PORT)
    logger.info("📆 Calendar accounts: %s",
                [a["email"] for a in poller.get_active_accounts()])

    # Schedule calendar polling every 15 minutes
    scheduler.add_job(safe_calendar_pipeline, "interval", minutes=15,
                      id="calendar_poll", replace_existing=True)
    # Also run immediately on startup
    scheduler.add_job(safe_calendar_pipeline, "date", id="startup_poll",
                      run_date=datetime.now(timezone.utc))
    scheduler.start()

    # ── ngrok tunnel for mobile access ──
    ngrok_url = None
    try:
        ngrok_token = os.environ.get("NGROK_AUTH_TOKEN", "")
        if ngrok_token:
            from pyngrok import ngrok
            ngrok.set_auth_token(ngrok_token)
            tunnel = ngrok.connect(PORT, "http")
            ngrok_url = tunnel.public_url
            logger.info("📱 Mobile access: %s/dashboard", ngrok_url)
            logger.info("🔗 ngrok URL: %s", ngrok_url)
        else:
            logger.warning("⚠️ NGROK_AUTH_TOKEN not set — local-only mode")
    except Exception as exc:
        logger.warning("⚠️ ngrok tunnel failed: %s — local-only mode", exc)

    # Store ngrok URL for API access
    app.state.ngrok_url = ngrok_url

    yield

    # Cleanup
    try:
        from pyngrok import ngrok as _ng
        _ng.disconnect(ngrok_url)
    except Exception:
        pass
    scheduler.shutdown()
    save_reminders(reminders_store)
    logger.info("🛡️ Sentinel Bridge shut down cleanly.")


# ── App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Sentinel Bridge",
    description="Autonomous Reminder System by Meta App Factory",
    version="1.0.0",
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
        "version": "1.0.0",
        "status": "active",
        "port": PORT,
        "dashboard": f"http://localhost:{PORT}/dashboard",
        "uptime": datetime.now(timezone.utc).isoformat(),
        "endpoints": {
            "dashboard": "/dashboard",
            "reminders": "/api/reminders",
            "add_reminder": "/api/reminders (POST)",
            "categories": "/api/categories",
            "telemetry": "/api/telemetry",
            "vault": "/api/vault/audit",
        },
    }


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

    return {
        "status": "category_updated",
        "old_category": old_category,
        "new_category": override.new_category,
        "ml_feedback": ml_result,
    }


@app.post("/api/reminders/{reminder_id}/snooze")
async def snooze_reminder(reminder_id: str):
    """Snooze a reminder for 15 minutes."""
    reminder = next((r for r in reminders_store if r["id"] == reminder_id), None)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    reminder["status"] = "snoozed"
    reminder["snoozed_until"] = (
        datetime.now(timezone.utc).isoformat()
    )
    save_reminders(reminders_store)
    return {"status": "snoozed", "reminder_id": reminder_id}


@app.post("/api/reminders/{reminder_id}/done")
async def mark_done(reminder_id: str):
    """Mark a reminder as completed."""
    reminder = next((r for r in reminders_store if r["id"] == reminder_id), None)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    reminder["status"] = "done"
    reminder["completed_at"] = datetime.now(timezone.utc).isoformat()
    save_reminders(reminders_store)
    return {"status": "done", "reminder_id": reminder_id}


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


# ── Google OAuth2 Web Flow ───────────────────────────────────────────
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",  # read + write events
]


@app.get("/api/auth/google")
async def google_auth_start(account: str = Query("work")):
    """
    Start Google OAuth2 flow. Redirects to Google consent screen.
    
    Usage:
        Open in browser: http://localhost:5009/api/auth/google?account=work
        Or:               http://localhost:5009/api/auth/google?account=personal
    """
    client_id = vault.retrieve("google_client_id")
    if not client_id:
        raise HTTPException(status_code=500,
                            detail="Google client_id not in vault")

    redirect_uri = f"http://localhost:{PORT}/api/auth/google/callback"
    scope = " ".join(GOOGLE_SCOPES)

    # Include account ID in state so callback knows which account to store for
    auth_url = (
        f"{GOOGLE_AUTH_URL}"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={account}"
    )

    from fastapi.responses import RedirectResponse
    logger.info("🔑 OAuth: Redirecting to Google for '%s' account", account)
    return RedirectResponse(url=auth_url)


@app.get("/api/auth/google/callback")
async def google_auth_callback(code: str = Query(...),
                                 state: str = Query("work")):
    """
    OAuth2 callback — exchanges auth code for tokens and stores in vault.
    """
    client_id = vault.retrieve("google_client_id")
    client_secret = vault.retrieve("google_client_secret")
    redirect_uri = f"http://localhost:{PORT}/api/auth/google/callback"

    # Exchange code for tokens
    import httpx as _httpx
    logger.info("🔑 Token exchange: client_id=%s..., redirect_uri=%s",
                client_id[:20], redirect_uri)
    async with _httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })

    if resp.status_code != 200:
        full_error = resp.text
        logger.error("❌ OAuth token exchange failed (HTTP %d): %s",
                      resp.status_code, full_error)
        try:
            error_json = resp.json()
            error_detail = error_json.get("error_description",
                           error_json.get("error", full_error))
        except Exception:
            error_detail = full_error
        return HTMLResponse(
            content=f"<h2>Authorization Failed</h2>"
                    f"<p><b>Error:</b> {error_detail}</p>"
                    f"<p><b>HTTP Status:</b> {resp.status_code}</p>"
                    f"<p><b>Redirect URI sent:</b> {redirect_uri}</p>"
                    f"<p>Make sure this exact URI is in your Google Cloud Console "
                    f"under Authorized redirect URIs.</p>"
                    f"<p><a href='/api/auth/google?account={state}'>Try again</a></p>",
            status_code=400,
        )

    tokens = resp.json()
    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")

    # Store tokens in vault
    vault.store(f"google_token_{state}", access_token)
    if refresh_token:
        vault.store(f"google_refresh_{state}", refresh_token)

    logger.info("✅ OAuth: '%s' account authorized successfully!", state)

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
    """Check authorization status for all calendar accounts."""
    statuses = {}
    for acc in poller.get_active_accounts():
        token = vault.retrieve(f"google_token_{acc['id']}")
        refresh = vault.retrieve(f"google_refresh_{acc['id']}")
        statuses[acc["id"]] = {
            "email": acc["email"],
            "authorized": token is not None,
            "has_refresh_token": refresh is not None,
        }
    return {"accounts": statuses}


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


# ── Telemetry ────────────────────────────────────────────────────────
@app.get("/api/telemetry")
async def telemetry():
    """Unified telemetry dashboard data."""
    return {
        "app": "Sentinel Bridge",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reminders": {
            "total": len(reminders_store),
            "pending": sum(1 for r in reminders_store if r.get("status") == "pending"),
            "done": sum(1 for r in reminders_store if r.get("status") == "done"),
            "snoozed": sum(1 for r in reminders_store if r.get("status") == "snoozed"),
        },
        "categorization": categorizer.get_stats(),
        "notifications": dispatcher.get_delivery_stats(),
        "selfheal": healer.get_heal_stats(),
        "vault": vault.export_audit(),
        "calendar_accounts": poller.get_active_accounts(),
    }


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
