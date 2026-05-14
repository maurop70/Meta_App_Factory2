import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto('http://localhost:5173/', timeout=5000)
            print("TITLE 5173:", await page.title())
        except Exception as e:
            print("5173 Error:", e)
            
        try:
            await page.goto('http://localhost:5174/', timeout=5000)
            print("TITLE 5174:", await page.title())
        except Exception as e:
            print("5174 Error:", e)
        await browser.close()

asyncio.run(run())
