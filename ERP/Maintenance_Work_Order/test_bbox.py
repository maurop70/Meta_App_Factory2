import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 800, 'height': 800})
        await page.goto('http://localhost:5175/login')
        await page.fill('input#mwo_operator_id', 'ERP-1029')
        await page.fill('input#mwo_operator_pin', '1234')
        await page.click('button[type="submit"]')
        await page.wait_for_selector('text="Dispatch Queue"', timeout=5000)
        await page.click('text="Dispatch Queue"')
        await page.wait_for_selector('table.erp-data-matrix thead', timeout=5000)
        await page.wait_for_timeout(2000)
        box = await page.evaluate("() => document.querySelector('table.erp-data-matrix thead').getBoundingClientRect()")
        print('THEAD BBOX:', box)
        
        td_display = await page.evaluate("() => window.getComputedStyle(document.querySelector('table.erp-data-matrix td')).display")
        print('TD DISPLAY:', td_display)
        await browser.close()

asyncio.run(main())
