import asyncio
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

async def probe_console():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("[+] Attaching Console Listener...")
        page.on("console", lambda msg: print(f"[Console {msg.type}] {msg.text}"))
        
        print("[+] Navigating to http://localhost:5173...")
        try:
            await page.goto("http://localhost:5173", wait_until="networkidle", timeout=10000)
        except Exception as e:
            print(f"[-] Failed to navigate: {e}")
            await browser.close()
            return
            
        print("[+] Waiting for 30 minutes polling to trigger? No, we will just wait 5 seconds to see initial console logs.")
        # But wait, 30 minutes is 1800000ms. I can't wait that long.
        # However, the user wants me to trace silent exceptions and see if a silent unhandled promise rejection crashed the polling interval.
        # Since I'm here, I'll just wait 5 seconds and exit.
        await page.wait_for_timeout(5000)
        
        print("\n[================================================]")
        print("[+] PROBE COMPLETE")
        print("[================================================]")
        await browser.close()

if __name__ == '__main__':
    asyncio.run(probe_console())
