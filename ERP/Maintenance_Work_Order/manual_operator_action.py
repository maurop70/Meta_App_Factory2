import asyncio
from playwright.async_api import async_playwright

async def manual_input():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1200, 'height': 800})
        await page.goto('http://localhost:8080/login')
        await page.wait_for_timeout(1000)
        
        # Fill the actual fields, not the honeypots
        await page.fill('#mwo_operator_id', 'ERP-1000')
        await page.fill('#mwo_operator_pin', '1234')
        await page.wait_for_timeout(500)
        
        button = page.locator('button[type="submit"]')
        is_disabled = await button.is_disabled()
        
        if is_disabled:
            print("Button is still disabled after correct filling.")
        else:
            print("Clicking Authorize Session...")
            await button.click()
            # Wait for either route transition or error message
            await page.wait_for_timeout(3000)
            
        print("Taking screenshot...")
        await page.screenshot(path='c:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/operator_telemetry.png', full_page=True)
        await browser.close()
        print("Done.")

asyncio.run(manual_input())
