from playwright.sync_api import sync_playwright

def capture_success():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        
        print("Navigating to admin...")
        page.goto("http://localhost:5175/admin")
        
        page.wait_for_load_state("networkidle")
        
        # Check if we need to login
        if "login" in page.url:
            print("Logging in...")
            page.fill("input[name='mwo_operator_id']", "ERP-1000")
            page.fill("input[name='mwo_operator_pin']", "1234")
            page.click("button:has-text('Authorize Session')")
            page.wait_for_url("**/admin")
            
        print("Clicking Procurement tab...")
        page.click("button:has-text('Procurement')")
        
        print("Waiting for PRQ-TEST-001 row...")
        page.wait_for_selector("text=PRQ-TEST-001", timeout=10000)
        
        print("Clicking View Payload on PRQ-TEST-001...")
        row = page.locator("tr:has-text('PRQ-TEST-001')")
        row.locator("button", has_text="View Payload").click()
        
        print("Waiting for modal...")
        page.wait_for_selector("text=Authorize Procurement", timeout=10000)
        
        print("Clicking EXECUTE STATE SHIFT...")
        page.click("button:has-text('EXECUTE STATE SHIFT')")
        
        print("Waiting for modal to close...")
        page.wait_for_selector("text=Authorize Procurement", state="hidden", timeout=10000)
        
        print("Modal closed. Waiting for table refresh...")
        page.wait_for_selector("tr:has-text('PRQ-TEST-001'):has-text('FULFILLED')", timeout=10000)
        
        print("Taking final screenshot...")
        page.screenshot(path="C:\\Users\\mpetr\\.gemini\\antigravity\\brain\\3ebb2f72-cd27-4713-ac15-e156465c3747\\final_ui_resolution.png")
        print("Screenshot saved to final_ui_resolution.png")
        
        browser.close()

if __name__ == "__main__":
    capture_success()
