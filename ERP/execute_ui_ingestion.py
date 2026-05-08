from playwright.sync_api import sync_playwright
import json

def execute_ui_ingestion():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        telemetry = {}
        
        def handle_response(response):
            if "inventory/skus" in response.url and response.request.method == "POST":
                telemetry["url"] = response.url
                telemetry["status"] = response.status
                try:
                    telemetry["payload"] = response.json()
                except:
                    telemetry["payload"] = response.text()
                    
        page.on("response", handle_response)
        
        try:
            # Login
            page.goto("http://localhost:5175/login")
            page.fill("input[name='mwo_operator_id']", "ERP-1000")
            page.fill("input[name='mwo_operator_pin']", "1234")
            page.click("button[type='submit']")
            page.wait_for_url("**/admin*", timeout=5000)
            page.wait_for_timeout(1000)
            
            # Click Data Ingestion
            page.locator("text=Data Ingestion").click(timeout=3000)
            page.wait_for_timeout(500)
            
            # Click SKU SCHEMA
            page.locator("text=SKU SCHEMA").click(timeout=3000)
            page.wait_for_timeout(500)
            
            # Click Ingest New SKU
            page.locator("button:has-text('[+ Ingest New SKU]')").click(timeout=3000)
            page.wait_for_timeout(500)
            
            # Fill form
            page.fill("input[name='sku_id']", "SKU-9902")
            page.fill("input[name='nomenclature']", "UI Synthesized Valve")
            page.fill("input[name='unit_cost']", "55.00")
            page.fill("input[name='reorder_threshold']", "20")
            
            # Submit
            page.click("button[type='submit']")
            page.wait_for_timeout(2000)
            
            print(json.dumps(telemetry, indent=2))
        except Exception as e:
            print("Error during execution:", e)
        finally:
            browser.close()

if __name__ == "__main__":
    execute_ui_ingestion()
