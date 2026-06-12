import asyncio
from playwright.async_api import async_playwright

async def try_login():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})

        console_msgs = []
        network_errors = []
        page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))
        page.on("response", lambda resp: network_errors.append(
            f"{resp.status} {resp.url}"
        ) if resp.status >= 400 else None)

        await page.goto("http://localhost:5175/login", timeout=10000, wait_until="networkidle")
        print("=== BEFORE LOGIN ===")
        print("URL:", page.url)

        # Fill in credentials
        inputs = await page.query_selector_all("input")
        print(f"Found {len(inputs)} input fields:")
        for i, inp in enumerate(inputs):
            t = await inp.get_attribute("type") or "text"
            p_attr = await inp.get_attribute("placeholder") or ""
            print(f"  [{i}] type={t} placeholder={p_attr}")

        # Employee ID is input[0], Authorization Code is input[1]
        await inputs[0].fill("ERP-3000")
        await inputs[1].fill("3456")

        await page.screenshot(
            path=r"c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\.launch_logs\before_submit.png"
        )

        # Submit
        btn = await page.query_selector("button[type=submit]")
        await btn.click()
        await page.wait_for_timeout(3000)

        print("\n=== AFTER SUBMIT ===")
        print("URL:", page.url)
        body = await page.inner_text("body")
        print("Body:", body[:500])

        await page.screenshot(
            path=r"c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\.launch_logs\after_submit.png"
        )

        print("\n=== NETWORK ERRORS ===")
        for e in network_errors:
            print(" ", e)

        print("\n=== CONSOLE ===")
        for m in console_msgs:
            print(" ", m)

        await browser.close()

asyncio.run(try_login())
