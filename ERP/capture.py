import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        # User requested: "Show it to me with your onw browser"
        # We will capture a screenshot and present it
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("Navigating to login...")
        await page.goto('http://localhost:5175/login')
        
        print("Filling credentials...")
        await page.fill('#mwo_operator_id', 'ERP-3000')
        await page.fill('#mwo_operator_pin', '3456')
        
        print("Clicking submit...")
        await page.click('.erp-submit-btn')
        
        print("Waiting for dashboard to load...")
        await page.wait_for_selector('text=MWO-003', timeout=10000)
        
        print("Opening MWO-003...")
        # Ascend from the h3 to the card container
        card = page.locator('xpath=//h3[text()="MWO-003"]/../../..')
        await card.locator('text=OPEN MWO DETAILS').click()
        
        await page.wait_for_selector('text=EXECUTE COMPLETION', timeout=5000)
        
        print("Opening completion form...")
        await page.click('text=EXECUTE COMPLETION')
        
        print("Filling manual log...")
        await page.fill('textarea', 'Completed physical inspection and tightened valves on MWO-003.')
        
        print("Severing network connection (Air-Gap)...")
        await browser.contexts[0].set_offline(True)
        
        print("Clicking complete...")
        await page.click('text=Finalize Completion')
        
        print("Waiting for modal to unmount...")
        await page.wait_for_timeout(1000) # Wait a bit for React to teardown the portal
        
        print("Waiting for SYNC PENDING UI lock on MWO-003...")
        # Ensure the overlay is present
        await page.wait_for_selector('text=SYNC PENDING...', timeout=10000)
        
        print("Taking screenshot...")
        await page.screenshot(path='C:/Users/mpetr/.gemini/antigravity/brain/66398479-cfb8-43b0-ad6b-ae577c7ded64/artifacts/real_sync_pending_mwo003.png', full_page=True)
        
        await browser.close()
        print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
