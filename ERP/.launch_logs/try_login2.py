import asyncio
from playwright.async_api import async_playwright

async def try_login():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})

        network_errors = []
        page.on("response", lambda resp: network_errors.append(
            f"{resp.status} {resp.url}"
        ) if resp.status >= 400 else None)

        await page.goto("http://localhost:5175/login", timeout=10000, wait_until="networkidle")

        # Inspect all inputs with their labels
        inputs = await page.query_selector_all("input")
        print(f"Found {len(inputs)} input fields:")
        for i, inp in enumerate(inputs):
            t = await inp.get_attribute("type") or "text"
            p_attr = await inp.get_attribute("placeholder") or ""
            name = await inp.get_attribute("name") or ""
            id_attr = await inp.get_attribute("id") or ""
            visible = await inp.is_visible()
            enabled = await inp.is_enabled()
            print(f"  [{i}] type={t} name={name} id={id_attr} placeholder={p_attr} visible={visible} enabled={enabled}")

        # Check button state
        btn = await page.query_selector("button[type=submit]")
        if btn:
            enabled = await btn.is_enabled()
            visible = await btn.is_visible()
            print(f"\nSubmit button: enabled={enabled} visible={visible}")

        # Get the full form HTML
        form = await page.query_selector("form")
        if form:
            form_html = await form.inner_html()
            print(f"\nForm HTML:\n{form_html[:2000]}")

        # Try filling the VISIBLE inputs (inputs 2 and 3 from biological_operator.ps1)
        print("\n--- Trying with inputs[2] and inputs[3] (as biological_operator does) ---")
        await inputs[2].fill("ERP-3000")
        await inputs[3].fill("3456")
        await page.wait_for_timeout(500)

        btn2 = await page.query_selector("button[type=submit]")
        if btn2:
            print(f"Button enabled after filling [2][3]: {await btn2.is_enabled()}")

        # Also try the first two visible fields
        print("--- Trying inputs[0] and inputs[1] ---")
        await inputs[0].fill("ERP-3000")
        await inputs[1].fill("3456")
        await page.wait_for_timeout(500)

        btn3 = await page.query_selector("button[type=submit]")
        if btn3:
            enabled_now = await btn3.is_enabled()
            print(f"Button enabled after filling all: {enabled_now}")
            if enabled_now:
                await btn3.click()
                await page.wait_for_timeout(3000)
                print(f"After submit URL: {page.url}")
                print(f"Body: {(await page.inner_text('body'))[:400]}")

        await page.screenshot(
            path=r"c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\.launch_logs\login_attempt.png"
        )
        print("\nNetwork errors:")
        for e in network_errors:
            print(" ", e)

        await browser.close()

asyncio.run(try_login())
