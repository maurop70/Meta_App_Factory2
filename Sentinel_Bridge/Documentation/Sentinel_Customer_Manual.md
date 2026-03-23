# Sentinel Bridge — User Guide
### Your AI-Powered Task Manager
**Version:** 2.0 | **Date:** March 23, 2026
**By:** Antigravity-AI

---

## What is Sentinel Bridge?

Sentinel Bridge is a **smart task manager** that goes beyond simple to-do lists. It connects to your Google Calendar, reads your documents, and uses artificial intelligence to organize your life — automatically.

**Think of it as a personal assistant that:**
- 📅 Watches your calendars and turns events into trackable tasks
- 📄 Reads your documents and extracts action items
- 🧠 Categorizes everything automatically (Work, Family, School, etc.)
- ⏰ Suggests the best times to schedule tasks based on your actual availability
- 📲 Sends push notifications to your phone when things are due

---

## Getting Started

### 1. Open the Dashboard
Navigate to your Sentinel Bridge dashboard in any browser. It works on desktop, tablet, and phone.

### 2. Connect Your Calendars
Click **Calendars** in the top right → authorize your Google accounts. Sentinel syncs:
- **Work calendar** (e.g., office@company.com)
- **Personal calendar** (e.g., you@gmail.com)

### 3. Start Adding Tasks
You have **three ways** to add tasks:

| Method | How |
|--------|-----|
| **Type it** | Type naturally: *"Pick up Leo at 4pm tomorrow"* → Sentinel extracts the time, category, and priority |
| **Speak it** | Tap the 🎤 button → speak your reminder → done |
| **Upload a document** | Click "Upload & Parse Document" → drop a PDF or Word doc → Sentinel extracts all action items |

---

## Key Features

### 🧠 Smart Scheduling
When you click **+ New Task**, Sentinel checks your calendar availability and shows **green time suggestion pills**:

> *Today 9:00 AM - 10:00 AM* · *Today 2:00 PM - 3:00 PM* · *Tomorrow 8:00 AM - 9:00 AM*

**Tap any pill** to instantly schedule your task at that time. No more guessing when you're free.

---

### ⚡ Active / Done / All Filters
At the top of your reminders list, use the filter tabs:
- **⚡ Active** — Tasks you need to do (default view)
- **✅ Done** — Completed tasks
- **📋 All** — Everything including done tasks

**Search bar:** Type to filter by task name or category.

---

### 🏷️ Auto-Categorization
Sentinel automatically assigns categories based on keywords:

| Category | Example Tasks |
|----------|--------------|
| **Work** | Meetings, interviews, vendor reviews |
| **Family** | Dentist appointments, school pickup |
| **Leo's School** | Parent-teacher conferences, homework |
| **AI** | Model training, API integration |
| **Legal** | FDA audits, contract reviews |

**Teach it:** If Sentinel categorizes something wrong, click the category badge → pick the correct one. Sentinel **learns** from your correction and gets smarter over time.

---

### 📄 Document Parser
Upload any PDF or Word document. Sentinel's AI reads it and extracts all actionable items:
- Due dates
- Priorities
- Categories
- Responsible parties

Each extracted task is added to your list and synced to your calendar.

---

### 📲 Push Notifications
Sentinel sends reminders to your phone via **ntfy**:
1. Install the [ntfy app](https://ntfy.sh) on your phone
2. Subscribe to your private topic
3. Get notifications for upcoming tasks, overdue items, and completed tasks

**Quiet Hours:** Sentinel won't ping you between 10 PM and 7 AM (unless it's high priority).

---

### 📅 Calendar Sync
Every task you create automatically appears in the right Google Calendar:
- Work tasks → Work calendar
- Family tasks → Personal calendar

When you mark a task **done**, the calendar event is automatically removed. Everything stays in sync.

---

### ⏰ Overdue Detection
Tasks past their due date show:
- 🔴 Red dot indicator
- **OVERDUE** badge (pulsing)
- Red left border

You can't miss them.

---

### 📋 Task Actions

| Action | How | What Happens |
|--------|-----|-------------|
| **Done** | Tap ✅ | Task moves to Done tab, calendar event deleted, notification sent |
| **Snooze** | Tap 😴 | Task delayed, notification rescheduled |
| **Edit** | Tap ✏️ | Change title, due date |
| **Archive** | Swipe left (mobile) | Task hidden from all views |
| **Change Category** | Tap category badge | Pick new category, ML learns your preference |

---

## Why Sentinel Bridge vs. Other Apps?

| | Todoist | Google Tasks | **Sentinel** |
|--|:-------:|:------------:|:------------:|
| Auto-categorize tasks | ❌ | ❌ | **✅** |
| Read documents for tasks | ❌ | ❌ | **✅** |
| Suggest free times | ❌ | ❌ | **✅** |
| Sync multiple calendars | ❌ | ⚠️ One only | **✅ All** |
| Learn from your corrections | ❌ | ❌ | **✅** |
| Voice input with AI | ❌ | ⚠️ Basic | **✅ Smart** |
| Quiet hours | ❌ | ❌ | **✅** |

---

## Tips & Tricks

1. **Natural language works:** Type *"Call dentist next Tuesday at 2pm"* — Sentinel understands.
2. **Bulk import:** Upload meeting agendas or project plans as PDFs — get all tasks instantly.
3. **Category shortcuts:** The ML engine learns fast. After 3-5 corrections, it auto-categorizes accurately.
4. **Mobile-friendly:** Sentinel is a PWA — add it to your home screen for app-like experience.
5. **Force refresh:** Pull down on mobile to refresh all data.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Calendar not syncing | Go to Calendars → Re-authorize your account |
| Not receiving notifications | Check ntfy app → verify you're subscribed to the right topic |
| Task not showing | Check if you're on the "Active" tab — it might be in "Done" or "All" |
| Wrong category | Tap the category badge to correct it — Sentinel learns |

---

*Sentinel Bridge — Your AI assistant that schedules, organizes, and reminds. So you can focus on what matters.*
