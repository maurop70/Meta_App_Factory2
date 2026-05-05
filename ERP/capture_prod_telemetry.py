import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('http://localhost:8080')
        await asyncio.sleep(2)
        await page.screenshot(path='C:\\Users\\mpetr\\.gemini\\antigravity\\brain\\8ceb48d2-32c7-4b57-9de9-03fff910aa88\\production_telemetry.png')
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
