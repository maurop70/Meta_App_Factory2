import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Ensure strict 800x800 viewport
        context = await browser.new_context(viewport={'width': 800, 'height': 800})
        page = await context.new_page()
        
        # Go to login
        await page.goto('http://localhost:5175/login')
        
        # Fill login form using the exact ID attributes from React code
        await page.fill('input#mwo_operator_id', 'ERP-1029')
        await page.fill('input#mwo_operator_pin', '1234') 
        await page.click('button[type="submit"]')
        
        try:
            await page.wait_for_url('**/admin', timeout=5000)
        except Exception:
            print("Login timeout. Checking for error messages...")
            error = await page.evaluate("document.body.innerText")
            print(error)
            raise

        # Let it render the tabs
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
        
        await page.screenshot(path='dispatch_queue_800px_verified.png', full_page=True)
        await browser.close()

asyncio.run(main())
