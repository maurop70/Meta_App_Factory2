from playwright.sync_api import sync_playwright
import json

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Handle alerts automatically
        page.on("dialog", lambda dialog: dialog.accept())
        
        intercepted_payload = None
        
        def handle_request(request):
            nonlocal intercepted_payload
            if request.method == "PATCH" and "MWO-1004" in request.url:
                intercepted_payload = request.post_data
                
        page.on("request", handle_request)
        
        print("Navigating to dashboard...")
        page.goto("http://localhost:5175/tech")
        
        page.wait_for_selector("text=MWO-1004")
        print("Found MWO-1004. Clicking COMPLETE...")
        
        card = page.locator("div", has=page.locator("h4", has_text="MWO-1004")).last
        card.locator("button:has-text('COMPLETE')").click()
        
        page.wait_for_timeout(2000)
        
        print("INTERCEPTED_PAYLOAD:", intercepted_payload)
        
        browser.close()

if __name__ == "__main__":
    run()
