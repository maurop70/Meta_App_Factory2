import asyncio
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

async def test():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page()
        await page.goto('http://localhost:5173', wait_until='load')
        await page.wait_for_timeout(3000)
        html = await page.content()
        print('NATIVE' in html)
        print('CACHED' in html)
        await b.close()

if __name__ == '__main__':
    asyncio.run(test())
