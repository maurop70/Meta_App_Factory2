import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # USE EXACTLY 281x791
        page = await browser.new_page(viewport={'width': 281, 'height': 791})
        await page.goto('http://localhost:5175/login')
        await page.fill('input#mwo_operator_id', 'ERP-1029')
        await page.fill('input#mwo_operator_pin', '1234')
        await page.click('button[type="submit"]')
        await page.wait_for_selector('text="Dispatch Queue"', timeout=5000)
        await page.click('text="Dispatch Queue"')
        await page.wait_for_selector('table.erp-data-matrix', timeout=5000)
        await page.wait_for_timeout(2000)
        
        # Test CSS
        eval_script = """() => {
            const td = document.querySelector('table.erp-data-matrix td');
            if (!td) return null;
            const style = window.getComputedStyle(td);
            const thead = document.querySelector('table.erp-data-matrix thead');
            const theadStyle = window.getComputedStyle(thead);
            
            return {
                tdDisplay: style.display,
                theadPosition: theadStyle.position,
                theadWidth: theadStyle.width,
                theadHeight: theadStyle.height
            };
        }"""
        
        stats = await page.evaluate(eval_script)
        print("CSSOM Validation Results:", stats)

        await page.screenshot(path='true_mobile_telemetry_281.png', full_page=False)
        await browser.close()

asyncio.run(main())
