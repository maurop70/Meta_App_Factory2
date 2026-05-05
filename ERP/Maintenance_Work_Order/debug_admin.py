import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Ensure strict 800x800 viewport
        context = await browser.new_context(viewport={'width': 800, 'height': 800})
        page = await context.new_page()
        
        # Go to login
        await page.goto('http://localhost:8000/login')
        
        # Fill login form
        await page.fill('input[placeholder="Employee ID"]', 'U-ADMIN')
        await page.fill('input[placeholder="4-Digit PIN"]', '1234') 
        await page.click('button[type="submit"]')
        
        try:
            await page.wait_for_url('**/admin', timeout=5000)
        except Exception:
            await page.fill('input[placeholder="Employee ID"]', 'USR-001')
            await page.fill('input[placeholder="4-Digit PIN"]', '1234')
            await page.click('button[type="submit"]')
            await page.wait_for_url('**/admin', timeout=5000)

        # Let it render
        await page.wait_for_timeout(2000)
        
        # Take a screenshot to see what's on the screen
        await page.screenshot(path='admin_page_screenshot.png', full_page=True)
        
        # Now try to find the tabs container and print its inner text
        html = await page.evaluate("document.body.innerHTML")
        with open('admin_page.html', 'w', encoding='utf-8') as f:
            f.write(html)
            
        await browser.close()

asyncio.run(main())
