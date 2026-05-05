import asyncio
from playwright.async_api import async_playwright
import sys
sys.path.insert(0, '.')
from maintenance_backend import create_access_token

async def main():
    token = create_access_token(user_id='USR-ADMIN', role='ADMINISTRATOR')
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Force strict 800px width
        context = await browser.new_context(viewport={'width': 800, 'height': 800})
        page = await context.new_page()
        
        # Go to a blank page first to set localStorage
        await page.goto('http://localhost:8000')
        await page.evaluate(f"window.localStorage.setItem('accessToken', '{token}'); window.localStorage.setItem('userRole', 'ADMINISTRATOR');")
        
        # Navigate to admin console
        await page.goto('http://localhost:8000/admin')
        
        # Wait and click Dispatch Queue tab
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
