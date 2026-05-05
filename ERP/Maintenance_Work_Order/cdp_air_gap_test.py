import asyncio
from playwright.async_api import async_playwright

async def run_audit():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        
        page = await context.new_page()
        await page.bring_to_front()
        
        await page.goto('http://localhost:8080/login')
        await page.evaluate("localStorage.clear()")
        await page.fill('#mwo_operator_id', 'ERP-1000')
        await page.fill('#mwo_operator_pin', '1234')
        await page.click('button[type="submit"]')
        
        await page.wait_for_selector('text=Admin Command Console', timeout=10000)
        await page.click('text=Tech View')
        
        await page.wait_for_selector('text=MWO-OFFLINE-01', timeout=5000)
        
        # Click START if it's ASSIGNED
        start_btn = page.locator('div', has_text='MWO-OFFLINE-01').locator('button', has_text='START').first
        if await start_btn.is_visible():
            await start_btn.click()
            await page.wait_for_selector('button:has-text("COMPLETE")', timeout=5000)
        
        await page.wait_for_timeout(2000)
        
        # Simulate physical air-gap
        await context.set_offline(True)
        async def handle_route(route):
            if 'work-orders' in route.request.url:
                await route.abort('failed')
            else:
                await route.continue_()
                
        await page.route("**/*", handle_route)
        
        await page.locator('button', has_text='COMPLETE').first.click()
        
        await page.wait_for_selector('textarea')
        await page.fill('textarea', 'Biological Execution Sequence: Network manually severed.')
        await page.click('button:has-text("Finalize Completion")')
        
        await page.wait_for_selector('text=SYNC PENDING...', timeout=5000)
        
        await page.screenshot(path='biological_proof.png', full_page=True)
        
        await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(run_audit())
    except Exception as e:
        print(f"Error: {e}")
