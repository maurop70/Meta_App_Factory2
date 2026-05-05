import asyncio
from playwright.async_api import async_playwright

async def manual_input():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1200, 'height': 800})
        await page.goto('http://localhost:8080/login')
        await page.wait_for_timeout(1000)
        
        await page.fill('#mwo_operator_id', 'ERP-1000')
        await page.fill('#mwo_operator_pin', '1234')
        await page.wait_for_timeout(500)
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(3000)
        
        print("Final URL:", page.url)
        content = await page.content()
        if "Admin Command Console" in content:
            print("Admin Console loaded successfully!")
        elif "Invalid credentials" in content or "Not Found" in content or "error" in content.lower():
            print("Error found in page content!")
        else:
            print("Something else loaded.")
        await browser.close()

asyncio.run(manual_input())
