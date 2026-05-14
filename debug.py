import sys
from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.on("console", lambda msg: print(f"Browser Console: {msg.text}"))
        page.on("pageerror", lambda exc: print(f"Browser Error: {exc}"))
        
        print("Navigating to 5175/login...")
        response = page.goto("http://localhost:5175/login")
        print(f"Response status: {response.status}")
        
        try:
            page.wait_for_selector("input", timeout=5000)
            print("Found input!")
        except Exception as e:
            print(f"Timeout waiting for input: {e}")
            
        page.screenshot(path="debug_screenshot.png")
        print(page.content())
        browser.close()

if __name__ == "__main__":
    run()
