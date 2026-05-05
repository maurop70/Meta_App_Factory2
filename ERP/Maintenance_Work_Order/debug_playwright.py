import asyncio
from playwright.async_api import async_playwright

async def run_audit():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()
        
        page.on("console", lambda msg: print(f"Browser Console: {msg.type}: {msg.text}"))
        
        print("Navigating to login...")
        await page.goto('http://localhost:8080/login')
        await page.fill('#mwo_operator_id', 'ERP-1000')
        await page.fill('#mwo_operator_pin', '1234')
        await page.click('button[type="submit"]')
        
        print("Waiting for Admin Console...")
        await page.wait_for_selector('text=Admin Command Console', timeout=10000)
        
        print("Actuating Tech View tab...")
        await page.click('text=Tech View')
        
        print("Waiting to see what renders...")
        await page.wait_for_timeout(3000)
        
        # Log body text to see what is there
        text = await page.locator('body').inner_text()
        print(f"Body text snippet: {text[:500]}")
        
        await page.screenshot(path='c:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/debug_tech_view.png', full_page=True)
        
        await browser.close()
        print("Done.")

asyncio.run(run_audit())
