# Phantom QA Gate Report — Maintenance_Work_Order
**Date:** 2026-04-20 14:51:38
**Verdict:** ⚠️ **WARN** (Score: 63/100)

## Stage Results

| # | Stage | Score | Status |
|---|-------|-------|--------|
| 1 | Infrastructure | 30/100 | ❌ |
| 2 | Architecture | 100/100 | ✅ |
| 3 | Brand | 60/100 | ✅ |
| 4 | Data Integrity | 100/100 | ✅ |
| 5 | Ui Testing | 43/100 | ❌ |
| 6 | Api Testing | 67/100 | ✅ |
| 7 | Monica Benchmark | 70/100 | ✅ |
| 8 | Critic Review | 30/100 | ✅ |

### Infrastructure

- **verdict:** CLOUD_DOWN
- **watchdog:** red
- **credentials:** missing

### Architecture

No architectural gaps detected.

### Brand

- **files_scanned:** 1
- **passing:** 0
- **failing:** 1
- **brand:** Antigravity-AI

### Data Integrity

- **quarantine:** {'processed': 0, 'repaired': 0, 'failed': 0}
- **data_files_found:** 0
- **reminders_audited:** False
- **schedule_healthy:** None

### Ui Testing

**3/7 passed**

- ❌ Page Load: Loaded but 13 console errors
- ✅ Navigation: No nav elements found — skipped
- ✅ Forms: No form fields found — skipped
- ❌ Responsive: Mobile (375px): Page.goto: Timeout 15000ms exceeded.
Call log:
  - navigating to "http://localhost:5173/", waiting until "networkidle"

- ❌ Responsive: Desktop (1280px): Page.goto: Timeout 15000ms exceeded.
Call log:
  - navigating to "http://localhost:5173/", waiting until "networkidle"

- ✅ Brand Compliance: Score: 80/100 (Grade B) | 3 violation(s): Missing brand font: 'Outfit'; Company name 'Antigravity-AI' not found; Mission statement not present
- ❌ Suite Error: Page.goto: Timeout 15000ms exceeded.
Call log:
  - navigating to "http://localhost:5173/", waiting until "networkidle"


### Api Testing

**6/9 passed**

- ✅ Root Endpoint: HTTP 200
- ✅ OpenAPI: GET /api/hierarchy: HTTP 200
- ❌ OpenAPI: GET /api/user/by-phone/{phone}: HTTP 404
- ✅ OpenAPI: GET /api/users/search: HTTP 200
- ❌ OpenAPI: GET /api/department/{dept_id}/technicians: HTTP 500
- ✅ OpenAPI: GET /api/orders/active: HTTP 200
- ❌ OpenAPI: GET /api/orders/assigned-to/{user_id}: HTTP 500
- ✅ OpenAPI: GET /: HTTP 200
- ✅ OpenAPI: GET /api/admin/roles: HTTP 200

### Monica Benchmark

**Mathematical Mapping Check:** N/A
**Extracted Formula:** `N/A`

### Critic Review

**Verdict:** ERROR
**Feedback:** HTTP 503
