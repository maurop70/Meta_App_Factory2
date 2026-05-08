from playwright.sync_api import sync_playwright
import json

def extract_telemetry():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        telemetry = {}
        
        def handle_response(response):
            if "users" in response.url and response.request.method == "GET":
                telemetry["url"] = response.url
                telemetry["status"] = response.status
                try:
                    telemetry["payload"] = response.json()
                except:
                    telemetry["payload"] = response.text()
                    
        page.on("response", handle_response)
        
        # Login
        page.goto("http://localhost:5175/login")
        page.fill("input[type='text']", "ERP-1000")
        page.fill("input[type='password']", "1234")
        page.click("button[type='submit']")
        
        # Wait for navigation
        page.wait_for_url("**/admin*")
        
        # Sometimes there's a tab to click
        try:
            page.wait_for_selector("text=Data Ingestion", timeout=3000)
            page.click("text=Data Ingestion")
        except:
            pass
            
        page.wait_for_timeout(3000)
        
        print(json.dumps(telemetry, indent=2))
        browser.close()

if __name__ == "__main__":
    extract_telemetry()
