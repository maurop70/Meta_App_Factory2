import asyncio
from playwright.async_api import async_playwright

async def run_audit():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()
        
        page.on("console", lambda msg: print(f"Browser Console: {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"Page Error: {err}"))
        
        await page.goto('http://localhost:8080/login')
        await page.evaluate("localStorage.clear()")
        await page.fill('#mwo_operator_id', 'ERP-1000')
        await page.fill('#mwo_operator_pin', '1234')
        await page.click('button[type="submit"]')
        
        await page.wait_for_selector('text=Admin Command Console', timeout=10000)
        
        await page.click('text=Tech View')
        await page.wait_for_timeout(3000)
        
        html = await page.locator('body').inner_html()
        with open('debug_body.html', 'w', encoding='utf-8') as f:
            f.write(html)
        
        await browser.close()

asyncio.run(run_audit())
