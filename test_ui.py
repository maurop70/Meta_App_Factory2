import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('http://localhost:5173')
        await page.wait_for_timeout(2000)
        await page.click('span:has-text("Atomizer")')
        await page.wait_for_timeout(1000)
        opts = await page.evaluate('Array.from(document.querySelectorAll("#child-app-id option")).map(o => o.value)')
        print(opts)
        await browser.close()

asyncio.run(main())
