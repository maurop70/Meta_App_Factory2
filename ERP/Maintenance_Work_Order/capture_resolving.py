from playwright.sync_api import sync_playwright
import time

def capture_resolving():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        
        print("Navigating to login...")
        page.goto("http://localhost:5175/login")
        
        # Login if on login page
        if page.locator("text=Employee ID").count() > 0:
            print("Logging in...")
            page.fill("input[name='mwo_operator_id']", "ERP-1000")
            page.fill("input[name='mwo_operator_pin']", "1234")
            page.click("button:has-text('Authorize Session')")
            page.wait_for_url("**/admin")
            
        print("Clicking Procurement tab...")
        page.click("text=Procurement")
        
        print("Waiting for View Payload...")
        page.wait_for_selector("button:has-text('View Payload')", timeout=10000)
        page.click("button:has-text('View Payload')")
        
        print("Waiting for modal...")
        page.wait_for_selector("text=Authorize Procurement", timeout=10000)
        
        # Fill authorized quantity if it's there
        if page.locator("input[type='number']").count() > 0:
            page.fill("input[type='number']", "10")
            
        print("Clicking EXECUTE STATE SHIFT...")
        page.click("button:has-text('EXECUTE STATE SHIFT')")
        
        print("Taking screenshot immediately...")
        # Waiting 500ms should perfectly capture RESOLVING...
        time.sleep(0.5)
        page.screenshot(path="C:\\Users\\mpetr\\.gemini\\antigravity\\brain\\3ebb2f72-cd27-4713-ac15-e156465c3747\\actuation_resolving_state.png")
        print("Screenshot saved to actuation_resolving_state.png")
        
        browser.close()

if __name__ == "__main__":
    capture_resolving()
