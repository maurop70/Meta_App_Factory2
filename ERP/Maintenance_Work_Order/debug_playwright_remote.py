from playwright.sync_api import sync_playwright

def debug():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        
        try:
            page.on("response", lambda response: print(f"<< {response.status} {response.url}"))
            print("Navigating to production URL...")
            page.goto("http://68.183.30.128", wait_until="load")
            page.wait_for_timeout(2000)
            
            print("Checking current page state...")
            if "login" in page.url or page.locator("input[name='mwo_operator_id']").is_visible():
                print("Logging in...")
                page.fill("input[name='mwo_operator_id']", "ERP-1000")
                page.fill("input[name='mwo_operator_pin']", "1234")
                page.click("button:has-text('Authorize Session')")
                page.wait_for_timeout(3000)
                print("Login sequence completed. Checking URL...")
                print("Current URL:", page.url)
            else:
                print("Already logged in or unexpected URL:", page.url)
                
            print("Navigating to Procurement...")
            page.goto("http://68.183.30.128/admin")
            page.wait_for_timeout(2000)
            
            proc_button = page.locator("button:has-text('Procurement')")
            if proc_button.is_visible():
                proc_button.click()
            else:
                print("Procurement button not found, maybe we're already there?")
            page.wait_for_timeout(3000) # Give it 3s to load data
            
            # Screenshot to see what is actually rendered
            page.screenshot(path="C:\\Users\\mpetr\\.gemini\\antigravity\\artifacts\\production_telemetry.png")
            print("Saved production_telemetry.png to artifacts folder.")
        except Exception as e:
            page.screenshot(path="C:\\Users\\mpetr\\.gemini\\antigravity\\artifacts\\production_error.png")
            print("Error:", e)
        finally:
            browser.close()

if __name__ == "__main__":
    debug()
