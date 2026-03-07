# 📊 AETHER MASTER DASHBOARD — Deployment Guide & Link
### Filed: 2026-03-07 | By: Data Architect + CFO + The Librarian

---

## Quick Deploy (3 Steps)

### Step 1: Create the Sheet
1. Go to [sheets.new](https://sheets.new) to create a blank Google Sheet

### Step 2: Paste the Script
1. In the new sheet, go to **Extensions → Apps Script**
2. Delete any existing code in `Code.gs`
3. Open the file: `Meta_App_Factory/Project_Aether/dashboard_generator.gs`
4. Copy the entire contents and paste into the Apps Script editor
5. Click **💾 Save** (Ctrl+S)

### Step 3: Run Setup
1. Click the function dropdown → select **`setupDashboard`**
2. Click **▶ Run**
3. Authorize the script when prompted (first-time only)
4. Wait for the "✅ Dashboard Deployed!" confirmation

---

## Dashboard Tabs

| Tab | Owner | Data Source | Contents |
|---|---|---|---|
| **⚡ Command Center** | Data Architect | Aether_System_Map.json | Agent statuses, KPIs, division breakdown |
| **💰 Fiscal Oversight** | CFO | Resource tracking | Monthly costs, annual projections, agent consumption |
| **📋 Project Index** | The Librarian | MASTER_INDEX.md | All projects, status, ports, infrastructure components |
| **📢 Boardroom Feed** | CEO | Boardroom_Exchange/ | All 5 filed reports with verdicts and key findings |
| **🏥 System Health** | CTO | Infrastructure monitor | Service endpoints, security status, compliance blocks |

## Auto-Refresh
After deploying, set up automatic refresh:
1. In Apps Script, go to **⏰ Triggers** (clock icon, left sidebar)
2. Click **+ Add Trigger**
3. Function: `autoRefresh` → Event: Time-driven → Every 15 minutes
4. Save

## Custom Menu
After setup, a **🔄 Aether Controls** menu appears in the sheet:
- **Refresh All Tabs** — manual sync
- **Rebuild Dashboard** — full reset
- **About** — version info

---

## Sheet Link
> ⚠️ **After creating the sheet, paste the URL below:**
>
> `[PASTE YOUR SHEET URL HERE AFTER DEPLOYMENT]`

---

*Filed by: Data Architect — Project Aether*
*Collaborators: CFO (Fiscal tab), The Librarian (Index sync)*
*Script location: `Meta_App_Factory/Project_Aether/dashboard_generator.gs`*
