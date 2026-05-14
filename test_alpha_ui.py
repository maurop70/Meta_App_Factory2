import asyncio
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

async def verify_alpha_dashboard():
    print("[+] Initializing headless Chromium instance...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        print("[+] Attaching network and console interceptors...")
        
        # Intercept console logs
        page.on("console", lambda msg: print(f"    [Console {msg.type}] {msg.text}") if msg.type in ['error', 'warning'] else None)
        
        # Intercept page errors (React hydration crashes, etc)
        page.on("pageerror", lambda err: print(f"    [Page Error] {err.message}"))
        
        # Intercept network responses (4xx/5xx)
        def handle_response(response):
            if response.status >= 400:
                print(f"    [Network {response.status}] {response.url}")
        page.on("response", handle_response)

        print("[+] Navigating to http://localhost:5173...")
        try:
            await page.goto("http://localhost:5173", wait_until="networkidle", timeout=10000)
        except Exception as e:
            print(f"[-] Failed to navigate: {e}")
            await browser.close()
            return

        print("[+] Asserting DOM Nodes...")
        try:
            # 1. System Risk Score
            print("    -> Verifying System Risk Score...")
            risk_score_locator = page.locator("text=System Risk Score").locator("..")
            await risk_score_locator.wait_for(timeout=5000)
            risk_text = await risk_score_locator.inner_text()
            print(f"       [+] Node Hydrated: {risk_text.strip()}")

            # 2. Market Data Matrix (SPX / VIX)
            print("    -> Verifying Market Data Matrix...")
            spx_locator = page.locator("text=SPX PRICE").locator("..")
            await spx_locator.wait_for(timeout=5000)
            spx_text = await spx_locator.inner_text()
            print(f"       [+] SPX Node Hydrated: {spx_text.strip()}")

            vix_locator = page.locator("text=VIX").locator("..")
            await vix_locator.wait_for(timeout=5000)
            vix_text = await vix_locator.inner_text()
            print(f"       [+] VIX Node Hydrated: {vix_text.strip()}")

            # 3. Strategy Ledger
            print("    -> Verifying Strategy Ledger / Active Trade...")
            active_trade_locator = page.locator("text=Active Trade").locator("..")
            try:
                await active_trade_locator.wait_for(timeout=5000)
                trade_text = await active_trade_locator.inner_text()
                print(f"       [+] Active Trade Node Hydrated: {trade_text.strip()}")
            except:
                print("       [-] Active Trade explicit node not found, checking for 'No open positions'...")
                no_pos_locator = page.locator("text=No open positions found")
                await no_pos_locator.wait_for(timeout=5000)
                no_pos_text = await no_pos_locator.inner_text()
                print(f"       [+] Ledger Status: {no_pos_text.strip()}")

            print("\n[================================================]")
            print("[+] ALL DOM NODE ASSERTIONS PASSED SUCCESSFULLY")
            print("[================================================]")

        except Exception as e:
            print("\n[================================================]")
            print("[-] FATAL DOM SCHEMA EXCEPTION DETECTED")
            print(f"{type(e).__name__}: {str(e)}")
            print("[================================================]")
            print("\nRAW DOM EXTRACTION FOR ARCHITECTURAL RESOLUTION:")
            html = await page.content()
            # print first 2000 chars of body to avoid flooding
            import re
            body_match = re.search(r'<body.*?>(.*)</body>', html, re.IGNORECASE | re.DOTALL)
            if body_match:
                print(body_match.group(1)[:2000])
            else:
                print(html[:2000])

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(verify_alpha_dashboard())
