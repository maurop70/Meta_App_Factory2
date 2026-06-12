import asyncio
from playwright.async_api import async_playwright

async def diagnose():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})

        console_errors = []
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warn") else None)

        # Navigate and wait
        try:
            resp = await page.goto("http://localhost:5175", timeout=12000, wait_until="networkidle")
            print(f"Status: {resp.status if resp else 'none'}")
        except Exception as e:
            print(f"Navigation error: {e}")

        print(f"URL: {page.url}")
        print(f"Title: {await page.title()}")

        # DOM snapshot
        body_text = await page.inner_text("body")
        print(f"Body text (first 400 chars): {body_text[:400]}")

        # Visible inputs/buttons
        inputs = await page.query_selector_all("input, button")
        print(f"Inputs/buttons found: {len(inputs)}")
        for el in inputs[:6]:
            tag = await el.evaluate("e => e.tagName")
            typ = await el.get_attribute("type") or ""
            placeholder = await el.get_attribute("placeholder") or ""
            text = (await el.inner_text())[:40]
            print(f"  <{tag.lower()} type={typ} placeholder={placeholder}> text={text}")

        # Probe backend directly
        try:
            api_page = await browser.new_page()
            api_resp = await api_page.goto("http://localhost:8000/system/directive", timeout=5000)
            api_body = await api_page.inner_text("body")
            print(f"Backend /system/directive: HTTP {api_resp.status} | {api_body[:200]}")
            await api_page.close()
        except Exception as e:
            print(f"Backend probe error: {e}")

        # Screenshot
        await page.screenshot(
            path=r"c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\.launch_logs\mwo_state.png",
            full_page=False
        )
        print("Screenshot saved.")

        print(f"Console errors ({len(console_errors)}):")
        for err in console_errors[:8]:
            print(f"  {err}")

        await browser.close()

asyncio.run(diagnose())
