"""
MWO Production Smoke Test
Target: http://68.183.30.128
Run: python mwo_smoke_test.py
Requires: pip install playwright && playwright install chromium
"""

import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright, expect

BASE_URL = "http://68.183.30.128"

HM_PIN = "1234"
TECH_PIN = "2345"
DM_PIN = "4567"
DM_EMP_ID = "ERP-4000"

results = []

def log(label, status, detail=""):
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    line = f"{icon}  [{status}] {label}"
    if detail:
        line += f"\n        → {detail}"
    print(line)
    results.append({"label": label, "status": status, "detail": detail})

async def test_static_load(page):
    try:
        resp = await page.goto(BASE_URL, timeout=10000)
        await page.wait_for_load_state("networkidle", timeout=10000)
        if resp and resp.status == 200:
            log("Frontend loads at /", "PASS")
        else:
            log("Frontend loads at /", "FAIL", f"HTTP {resp.status if resp else 'no response'}")
    except Exception as e:
        log("Frontend loads at /", "FAIL", str(e))

async def test_dm_login(page):
    # The app has no /dm/login route — /dm/* is protected and bounces to the
    # shared /login page, whose inputs are #mwo_operator_id / #mwo_operator_pin.
    try:
        await page.goto(f"{BASE_URL}/login", timeout=10000)
        await page.wait_for_load_state("networkidle", timeout=8000)
        content = await page.content()
        if "login" not in content.lower() and "employee" not in content.lower():
            log("DM /login renders", "FAIL", "Page content doesn't look like a login page")
            return False
        log("DM /login renders", "PASS")
        emp_input = page.locator("#mwo_operator_id")
        await emp_input.fill(DM_EMP_ID)
        pin_input = page.locator("#mwo_operator_pin")
        await pin_input.fill(DM_PIN)
        submit = page.locator("button[type='submit']").first
        await expect(submit).to_be_enabled(timeout=5000)
        await submit.click()
        await page.wait_for_timeout(2000)
        current_url = page.url
        if "/login" not in current_url:
            log("DM login authenticates", "PASS", f"Redirected to {current_url}")
            return True
        else:
            log("DM login authenticates", "FAIL", "No redirect after PIN submit")
            return False
    except Exception as e:
        log("DM /login", "FAIL", str(e))
        return False


async def test_dm_personnel_api(page):
    """Regression check: /api/dm/personnel must return 200 with personnel,
    not a 404 (missing ERP-4000 DM record) or 500 (swallowed HTTPException)."""
    try:
        login = await page.request.post(
            f"{BASE_URL}/auth/api/v1/auth/login",
            data=json.dumps({"emp_id": DM_EMP_ID, "pin": DM_PIN}),
            headers={"Content-Type": "application/json"},
            timeout=8000,
        )
        token = (await login.json()).get("access_token", "")
        if not token:
            log("DM gateway login (API)", "FAIL", f"HTTP {login.status} — no access_token")
            return
        log("DM gateway login (API)", "PASS")
        resp = await page.request.get(
            f"{BASE_URL}/mwo/api/dm/personnel",
            headers={"Authorization": f"Bearer {token}"},
            timeout=8000,
        )
        body = await resp.json()
        data = body.get("data") if isinstance(body, dict) else None
        if resp.status == 200 and data:
            log("/api/dm/personnel returns personnel", "PASS",
                f"HTTP 200 — {len(data)} record(s): {str(data)[:80]}")
        else:
            log("/api/dm/personnel returns personnel", "FAIL",
                f"HTTP {resp.status} — {str(body)[:100]}")
    except Exception as e:
        log("/api/dm/personnel", "FAIL", str(e))

async def test_api_endpoints(page):
    endpoints = [
        ("/mwo/api/system/directive",     "API health (system/directive)"),
        ("/mwo/api/work-orders/queue",    "Dispatch Queue API"),
        ("/mwo/api/mwo",                  "Work Orders API"),
        ("/mwo/api/mwo/archive/list",     "Archive API"),
    ]
    for path, label in endpoints:
        try:
            resp = await page.request.get(f"{BASE_URL}{path}", timeout=8000)
            body = await resp.json()
            if resp.status == 200:
                log(label, "PASS", f"HTTP 200 — {str(body)[:80]}")
            elif resp.status in [401, 403]:
                log(label, "WARN", f"HTTP {resp.status} — auth required")
            else:
                log(label, "FAIL", f"HTTP {resp.status} — {str(body)[:80]}")
        except Exception as e:
            log(label, "FAIL", str(e))

async def test_pdf_serve(page):
    try:
        resp = await page.request.get(f"{BASE_URL}/mwo/api/work-orders/pdf/test", timeout=8000)
        if resp.status in [200, 404, 401, 422]:
            log("PDF serve route reachable", "PASS", f"HTTP {resp.status}")
        else:
            log("PDF serve route reachable", "FAIL", f"Unexpected HTTP {resp.status}")
    except Exception as e:
        log("PDF serve route", "FAIL", str(e))

async def test_nginx_proxy(page):
    try:
        resp = await page.request.get(f"{BASE_URL}/mwo/api/mwo", timeout=8000)
        server_header = resp.headers.get("server", "")
        if resp.status in [200, 401, 403]:
            log("Nginx /api/ proxy", "PASS", f"HTTP {resp.status}, server: {server_header}")
        else:
            log("Nginx /api/ proxy", "FAIL", f"HTTP {resp.status}")
    except Exception as e:
        log("Nginx /api/ proxy", "FAIL", str(e))

async def test_auth_gateway(page):
    try:
        resp = await page.request.post(
            f"{BASE_URL}/auth/api/v1/auth/login",
            data=json.dumps({"pin": "wrongpin", "role": "tech"}),
            headers={"Content-Type": "application/json"},
            timeout=8000
        )
        if resp.status in [400, 401, 403, 422, 200]:
            log("Gateway auth route reachable", "PASS", f"HTTP {resp.status}")
        else:
            log("Gateway auth route reachable", "FAIL", f"HTTP {resp.status}")
    except Exception as e:
        log("Gateway auth route", "FAIL", str(e))

async def test_screenshot(page, path, label, filename):
    try:
        await page.goto(f"{BASE_URL}{path}", timeout=10000)
        await page.wait_for_load_state("networkidle", timeout=8000)
        await page.screenshot(path=filename, full_page=True)
        log(f"Screenshot: {label}", "PASS", filename)
    except Exception as e:
        log(f"Screenshot: {label}", "FAIL", str(e))

async def main():
    print(f"\n{'='*60}")
    print(f"  MWO Production Smoke Test")
    print(f"  Target: {BASE_URL}")
    print(f"  Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("── Frontend ──────────────────────────────────────────")
        await test_static_load(page)

        print("\n── API Endpoints ─────────────────────────────────────")
        await test_nginx_proxy(page)
        await test_api_endpoints(page)
        await test_pdf_serve(page)

        print("\n── Auth Gateway ──────────────────────────────────────")
        await test_auth_gateway(page)

        print("\n── DM Role (Fix 5) ───────────────────────────────────")
        await test_dm_login(page)
        await test_dm_personnel_api(page)

        print("\n── Screenshots ───────────────────────────────────────")
        await test_screenshot(page, "/", "Root", "smoke_root.png")
        await test_screenshot(page, "/dm/login", "DM Login", "smoke_dm_login.png")

        print("\n── Console Errors ────────────────────────────────────")
        if console_errors:
            for err in console_errors:
                log("JS console error", "WARN", err[:120])
        else:
            log("No JS console errors", "PASS")

        await browser.close()

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    warned = sum(1 for r in results if r["status"] == "WARN")

    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed} passed  {failed} failed  {warned} warnings")
    print(f"{'='*60}\n")

    if failed > 0:
        print("FAILURES:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  ❌ {r['label']}: {r['detail']}")

asyncio.run(main())
