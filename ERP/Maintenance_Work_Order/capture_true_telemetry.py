import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Ensure strict 800x1000 viewport
        context = await browser.new_context(viewport={'width': 800, 'height': 1000})
        page = await context.new_page()
        
        # Go to login
        await page.goto('http://localhost:5175/login')
        
        # Fill login form
        await page.fill('input#mwo_operator_id', 'ERP-1029')
        await page.fill('input#mwo_operator_pin', '1234') 
        await page.click('button[type="submit"]')
        
        # Wait for navigation
        await page.wait_for_url('**/admin', timeout=5000)
        
        # Let it render the tabs
        await page.wait_for_selector('text="Dispatch Queue"', timeout=5000)
        await page.click('text="Dispatch Queue"')
        
        # Wait for matrix to render
        await page.wait_for_selector('table.erp-data-matrix td', timeout=5000)
        await page.wait_for_timeout(2000) # give CSS time to settle
        
        # Capture strictly the viewport, NOT the full page width
        await page.screenshot(path='dispatch_queue_true_telemetry.png', full_page=False)
        await browser.close()

asyncio.run(main())
