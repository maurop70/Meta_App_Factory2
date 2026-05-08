from playwright.sync_api import sync_playwright
import time

def debug():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        
        page.goto("http://localhost:5175/admin")
        page.wait_for_load_state("networkidle")
        
        if "login" in page.url:
            page.fill("input[name='mwo_operator_id']", "ERP-1000")
            page.fill("input[name='mwo_operator_pin']", "1234")
            page.click("button:has-text('Authorize Session')")
            page.wait_for_url("**/admin")
            
        time.sleep(2)
        page.click("button:has-text('Procurement')")
        time.sleep(3)
        
        page.screenshot(path="C:\\Users\\mpetr\\.gemini\\antigravity\\brain\\3ebb2f72-cd27-4713-ac15-e156465c3747\\debug_ui_2.png")
        print("Captured debug_ui_2.png")
        browser.close()

if __name__ == "__main__":
    debug()
