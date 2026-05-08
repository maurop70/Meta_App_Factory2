from playwright.sync_api import sync_playwright

def debug():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        
        try:
            page.goto("http://localhost:5175/admin")
            page.wait_for_load_state("networkidle")
            
            if "login" in page.url:
                page.fill("input[name='mwo_operator_id']", "ERP-1000")
                page.fill("input[name='mwo_operator_pin']", "1234")
                page.click("button:has-text('Authorize Session')")
                page.wait_for_url("**/admin")
                
            page.click("button:has-text('Procurement')")
            page.wait_for_timeout(3000) # Give it 3s to load data
            
            # Screenshot to see what is actually rendered
            page.screenshot(path="C:\\Users\\mpetr\\.gemini\\antigravity\\brain\\3ebb2f72-cd27-4713-ac15-e156465c3747\\debug_ui.png")
            print("Saved debug_ui.png")
        except Exception as e:
            page.screenshot(path="C:\\Users\\mpetr\\.gemini\\antigravity\\brain\\3ebb2f72-cd27-4713-ac15-e156465c3747\\debug_ui_error.png")
            print("Error:", e)
        finally:
            browser.close()

if __name__ == "__main__":
    debug()
