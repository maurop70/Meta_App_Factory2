# 🛡️ Sentinel Bridge v2.0 — Autonomous Reminder System

> **Owner:** Mauro Petrini  
> **Parent:** Meta App Factory (Aether & Self-Healing Core)  
> **Status:** Active  
> **Version:** 2.0.0  
> **Port:** 5009  
> **Dashboard:** `http://localhost:5009/dashboard`  
> **Mobile:** `https://marylee-unincreased-subgranularly.ngrok-free.dev/dashboard`

---

## Overview

Sentinel Bridge is a fully autonomous reminder and notification system that:

1. **Ingests** calendar events from Google Calendar (multiple accounts), manual text, and voice-to-text inputs via the Aether Layer.
2. **Categorizes** every item into configurable categories (`AI`, `Work`, `Leo's School`, `Family`) with an ML feedback loop that learns from user overrides.
3. **Auto-assigns** new events to the correct Google Calendar based on AI categorization (Work/AI → work calendar, Family/Leo's School → personal calendar).
4. **Delivers** push notifications via [ntfy.sh](https://ntfy.sh) with professional formatting: `[Category] Activity Name - Time`.
5. **Self-heals** — if any pipeline stage fails, the built-in diagnostic engine retries, patches config, and logs the fix.
6. **Encrypts** all credentials and personal data with Fernet AES-128 (Zero-Leak protocol).
7. **Mobile access** — ngrok tunnel with reserved domain for persistent phone/tablet access.
8. **Calendar visualization** — monthly calendar view with color-coded category events.
9. **Tunnel heartbeat** — auto-reconnects ngrok and sends ntfy notification if URL changes.

## Architecture

```text
┌───────────────────────────────────────────────────────┐
│                 Sentinel Bridge v2.0                    │
│                                                        │
│   ┌──────────┐   ┌───────────┐   ┌────────────────┐  │
│   │ Calendar  │──▶│ Aether    │──▶│ Categorization │  │
│   │ Poller    │   │ Ingestion │   │ Engine (ML)    │  │
│   └──────────┘   └───────────┘   └───────┬────────┘  │
│                                           │           │
│   ┌──────────┐   ┌───────────┐   ┌───────▼────────┐  │
│   │ Voice/   │──▶│ Intent    │──▶│ Notification   │  │
│   │ Text In  │   │ Extractor │   │ Dispatcher     │  │
│   └──────────┘   └───────────┘   └───────┬────────┘  │
│                                           │           │
│   ┌──────────────────────────────────────▼────────┐  │
│   │             ntfy Push Gateway                  │  │
│   │  [Category] Activity Name - Time               │  │
│   └────────────────────────────────────────────────┘  │
│                                                        │
│   ┌─────────────┐    ┌──────────────────────────┐     │
│   │ Self-Heal   │    │ Fernet Vault (AES-128)   │     │
│   │ Engine      │    │ Zero-Leak Protocol       │     │
│   └─────────────┘    └──────────────────────────┘     │
│                                                        │
│   ┌─────────────┐    ┌──────────────────────────┐     │
│   │ Tunnel Mgr  │    │ Calendar Visualization   │     │
│   │ + Heartbeat │    │ Monthly/Weekly Grid      │     │
│   └─────────────┘    └──────────────────────────┘     │
└───────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch (vault auto-initializes on first run)
python sentinel_server.py
# — or —
launch_sentinel.bat

# 3. Authorize calendars in your browser
# http://localhost:5009/api/auth/google?account=work
# http://localhost:5009/api/auth/google?account=personal

# 4. Open the dashboard
# http://localhost:5009/dashboard
```

## Dashboard Features

### Reminders Tab
- **Add Reminder** — text input or 🎙 voice (Web Speech API)
- **Reminder List** — color-coded category badges, snooze/done actions
- **Edit Modal** — click any card to edit activity, time, category, and description
- **Swipe-to-Archive** — swipe left on mobile to archive reminders
- **Category Override** — click any badge to reclassify (trains ML engine)
- **Quick Actions** — force poll, test notification, reconnect tunnel, re-authorize

### Calendar Tab
- **Monthly Grid** — visual calendar with color-coded event dots and chips
- **Category Colors** — AI (Purple), Work (Blue), Leo's School (Yellow), Family (Green)
- **Day Detail** — click any day to see full event list below the grid
- **Navigation** — Prev/Today/Next month buttons
- **Unified View** — shows both Google Calendar events and manual/voice reminders

## Calendar Accounts & Auto-Assignment

| Category | Calendar Account | Type | Color |
| --- | --- | --- | --- |
| Work, AI | `mpetrini@heinleinfoodsusa.com` | Work | Blue / Purple |
| Leo's School, Family | `mauro@gelatopetrini.com` | Personal | Yellow / Green |

When you add a reminder, AI categorizes it and **writes it to the matching Google Calendar** automatically.

## Notification Format

```text
[Work] Budget Review Meeting - 2:30 PM
[Leo's School] Science Project Due - Tomorrow 8:00 AM
[Family] Dentist Appointment - Wednesday 10:00 AM
[AI] Model Training Checkpoint - 6:00 PM
```

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/dashboard` | Web dashboard (tabbed UI) |
| GET | `/api/reminders` | List reminders |
| POST | `/api/reminders` | Create reminder (text/voice) |
| PUT | `/api/reminders/:id` | Edit reminder (activity, time, category) |
| PUT | `/api/reminders/:id/category` | Override category |
| PUT | `/api/reminders/:id/archive` | Archive reminder |
| POST | `/api/reminders/:id/snooze` | Snooze 15 min |
| POST | `/api/reminders/:id/done` | Mark complete |
| GET | `/api/categories` | List categories |
| POST | `/api/categories` | Add category |
| GET | `/api/calendar/events` | Calendar events (by month) |
| GET | `/api/auth/google?account=work` | OAuth flow |
| GET | `/api/auth/status` | Auth status |
| POST | `/api/calendar/poll` | Force poll |
| GET | `/api/tunnel/status` | ngrok tunnel status + URL |
| POST | `/api/tunnel/reconnect` | Force tunnel reconnect |
| GET | `/api/telemetry` | Full telemetry |

## Connectivity & Mobile Access

- **Reserved Domain:** `marylee-unincreased-subgranularly.ngrok-free.dev`
- **Heartbeat:** Every 5 minutes, checks if tunnel is alive. If dead, auto-reconnects and pushes ntfy notification with new URL.
- **N8N Guard:** `N8N_SKIP_AUTH_ON_OAUTH_CALLBACK=true` env var ensures OAuth callbacks aren't blocked.

## File Structure

```text
Sentinel_Bridge/
├── README.md                  # This file
├── requirements.txt           # Python dependencies
├── dashboard.html             # Web dashboard (tabbed, single-page)
├── sentinel_server.py         # FastAPI server v2.0 (port 5009)
├── sentinel_config.py         # Configuration wizard
├── calendar_poller.py         # Google Calendar sync (15 min)
├── aether_ingestion.py        # Multimodal input processing
├── categorization_engine.py   # ML-powered tagging
├── notification_dispatcher.py # ntfy push delivery
├── self_heal.py               # Autonomous error recovery
├── fernet_vault.py            # AES-128 credential encryption
├── intent_extractor.py        # NLP intent/timing extraction
├── launch_sentinel.bat        # One-click launcher
├── .gitignore
└── data/                      # Local data store
    ├── reminders.json
    ├── category_overrides.json
    └── heal_log.json
```

## Security

- All credentials stored encrypted in Fernet vault (machine-bound)
- Google OAuth tokens never written to disk in plaintext
- HTTP headers sanitized via factory-level `utils/safe_http.py`
- `.gitignore` excludes vault files, tokens, and data
