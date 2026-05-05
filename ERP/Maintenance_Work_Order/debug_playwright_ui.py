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
        # We try USR-001 or U-ADMIN, whichever works. Usually the demo script uses U-ADMIN
        await page.fill('input[placeholder="Employee ID"]', 'U-ADMIN')
        await page.fill('input[placeholder="4-Digit PIN"]', '1234') # usually 1234
        await page.click('button[type="submit"]')
        
        try:
            await page.wait_for_url('**/admin', timeout=5000)
        except Exception:
            # If U-ADMIN fails, try USR-001
            await page.fill('input[placeholder="Employee ID"]', 'USR-001')
            await page.fill('input[placeholder="4-Digit PIN"]', '1234')
            await page.click('button[type="submit"]')
            await page.wait_for_url('**/admin', timeout=5000)

        # Click Dispatch Queue tab
        await page.wait_for_selector('text="Dispatch Queue"', timeout=5000)
        await page.click('text="Dispatch Queue"')
        
        # Wait for matrix to render
        await page.wait_for_selector('table.erp-data-matrix td', timeout=5000)
        
        # Measure computed style and layout
        eval_script = """() => {
            const td = document.querySelector('table.erp-data-matrix td');
            if (!td) return null;
            const style = window.getComputedStyle(td);
            const beforeStyle = window.getComputedStyle(td, '::before');
            const table = document.querySelector('table.erp-data-matrix');
            
            return {
                tdDisplay: style.display,
                beforeContent: beforeStyle.content,
                tableWidth: table.getBoundingClientRect().width,
                windowWidth: window.innerWidth
            };
        }"""
        
        stats = await page.evaluate(eval_script)
        print("CSSOM Validation Results:", stats)
        
        await page.screenshot(path='debug_reflow_800px.png', full_page=True)
        await browser.close()

asyncio.run(main())
