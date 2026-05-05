import asyncio
from playwright.async_api import async_playwright

async def capture_native():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # Strictly enforce the 800x1000 viewport limit
        page = await browser.new_page(viewport={'width': 800, 'height': 1000})
        await page.goto('http://localhost:5175/login')
        await page.fill('input#mwo_operator_id', 'ERP-1029')
        await page.fill('input#mwo_operator_pin', '1234')
        await page.click('button[type="submit"]')
        
        # Wait for the Admin Console to load completely
        await page.wait_for_selector('text="Admin Command Console"', timeout=5000)
        
        # Specifically click the tab button, not just any text
        await page.click('button:has-text("Dispatch Queue")')
        
        # MUST wait for a Dispatch-Queue-specific element so we don't accidentally screenshot the Ingestion tab
        await page.wait_for_selector('h3:has-text("Central Dispatch Queue")', timeout=5000)
        await page.wait_for_selector('table.erp-data-matrix', timeout=5000)
        
        # Allow React to fully mount the CSS data-labels
        await page.wait_for_timeout(2000)
        
        # Capture the image
        await page.screenshot(path='final_dispatch_queue_telemetry.png', full_page=False)
        await browser.close()

asyncio.run(capture_native())
