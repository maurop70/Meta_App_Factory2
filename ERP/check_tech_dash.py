import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        print("Navigating to login page...")
        await page.goto("http://localhost:5173")
        
        print("Logging in as ERP-1000...")
        await page.fill("input[type='text']", "ERP-1000")
        await page.fill("input[type='password']", "1234")
        await page.click("button:has-text('Login')")
        
        await page.wait_for_timeout(2000)
        
        print("Navigating to Tech Dashboard...")
        await page.click("button:has-text('Tech Execution')") # assuming there is a button or we can just go to /tech
        await page.wait_for_timeout(2000)
        
        # take screenshot
        screenshot_path = os.path.join(os.getcwd(), 'tech_dash_test.png')
        await page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")
        
        # Evaluate local storage token
        token = await page.evaluate("localStorage.getItem('erp_token')")
        print("Token:", token)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
