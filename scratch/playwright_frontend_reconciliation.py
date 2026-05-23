import asyncio
from playwright.async_api import async_playwright
import sys

async def run_frontend_e2e():
    print("=== STARTING HEADLESS PLAYWRIGHT FRONTEND RECONCILIATION VERIFICATION ===")
    telemetry = []
    console_errors = []
    success = True

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Capture console errors
        def handle_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)
                print(f"CONSOLE ERROR: {msg.text}")
        page.on("console", handle_console)

        # Capture network telemetry
        def handle_request(request):
            if "/api/" in request.url:
                telemetry.append(f"REQ -> [{request.method}] {request.url}")
        
        def handle_response(response):
            if "/api/" in response.url:
                telemetry.append(f"RES <- [{response.status}] {response.url}")

        page.on("request", handle_request)
        page.on("response", handle_response)

        # 1. Navigate to the live UI
        print("Navigating to http://localhost:5173/...")
        await page.goto("http://localhost:5173/")
        await page.wait_for_timeout(4000)

        # Get initial URL
        initial_url = page.url
        print(f"Initial URL: {initial_url}")
        
        # 2. Assert "Database Error Inception" is purged
        print("ASSERTION 1: Purge of HTTP 500 error alerts...")
        content = await page.content()
        has_db_error = "Database Error Inception" in content or "HTTP error! status: 500" in content
        print(f"Database Error Status found in DOM: {has_db_error}")
        try:
            assert not has_db_error, "FRACTURE: Found 'Database Error Inception' or 500 alerts in the DOM."
            print("Assertion PASSED: Database error alerts completely purged.")
        except AssertionError as ae:
            print(f"Assertion FAILED: {ae}")
            success = False

        # 3. Assert Active Apps renders the live Triad via network payload
        print("\nASSERTION 2: Live Active Apps network hydration...")
        aside_text = await page.locator("aside").inner_text()
        
        has_cfo = "CFO_Agent" in aside_text
        has_cio = "CIO_Agent" in aside_text
        has_adv = "Adv_Autonomous_Agent" in aside_text
        
        print(f"CFO_Agent found in sidebar: {has_cfo}")
        print(f"CIO_Agent found in sidebar: {has_cio}")
        print(f"Adv_Autonomous_Agent found in sidebar: {has_adv}")
        
        # Check that we queried the api
        api_apps_called = any("/api/apps/running" in req for req in telemetry)
        print(f"API endpoint '/api/apps/running' called: {api_apps_called}")
        
        try:
            assert has_cfo, "FRACTURE: CFO_Agent is missing from layout sidebar."
            assert has_cio, "FRACTURE: CIO_Agent is missing from layout sidebar."
            assert has_adv, "FRACTURE: Adv_Autonomous_Agent is missing from layout sidebar."
            assert api_apps_called, "FRACTURE: The Active Apps UI did not query the live network backend."
            print("Assertion PASSED: Active Apps are fully bound and dynamically hydrated from active network telemetry.")
        except AssertionError as ae:
            print(f"Assertion FAILED: {ae}")
            success = False

        # 4. Navigate to CIO Intel
        print("\nASSERTION 3: Click and mount modular CIO Intel view...")
        print("Clicking 'CIO Intel' in the sidebar...")
        await page.locator("aside >> text=CIO Intel").click()
        await page.wait_for_timeout(2000)
        
        current_url = page.url
        print(f"Current URL: {current_url}")
        
        cio_view_content = await page.content()
        has_cio_header = "CIO Strategic Intelligence" in cio_view_content
        print(f"CIO Strategic Intelligence header mounted in DOM: {has_cio_header}")
        
        try:
            assert "#/cio-intel" in current_url, f"FRACTURE: Router failed to transition to #/cio-intel. Current: {current_url}"
            assert has_cio_header, "FRACTURE: Standalone CIOIntel view failed to mount in the central container."
            print("Assertion PASSED: CIOIntel view successfully mounted via client router.")
        except AssertionError as ae:
            print(f"Assertion FAILED: {ae}")
            success = False

        # 5. Navigate to App Registry
        print("\nASSERTION 4: Click and mount modular App Registry view...")
        print("Clicking 'App Registry' in the sidebar...")
        await page.locator("aside >> text=App Registry").click()
        await page.wait_for_timeout(2000)
        
        current_url = page.url
        print(f"Current URL: {current_url}")
        
        registry_view_content = await page.content()
        has_registry_header = "C-Suite App Registry" in registry_view_content
        print(f"C-Suite App Registry header mounted in DOM: {has_registry_header}")
        
        try:
            assert "#/registry" in current_url, f"FRACTURE: Router failed to transition to #/registry. Current: {current_url}"
            assert has_registry_header, "FRACTURE: Standalone AppRegistry view failed to mount in the central container."
            print("Assertion PASSED: AppRegistry view successfully mounted via client router.")
        except AssertionError as ae:
            print(f"Assertion FAILED: {ae}")
            success = False

        # 6. Navigate to Telemetry Dashboard
        print("\nASSERTION 5: Click and mount modular Telemetry Dashboard...")
        print("Clicking 'Telemetry' in the sidebar...")
        await page.locator("aside >> text=Telemetry").click()
        await page.wait_for_timeout(2000)
        
        current_url = page.url
        print(f"Current URL: {current_url}")
        
        telemetry_view_content = await page.content()
        has_telemetry_header = "Live C-Suite Telemetry" in telemetry_view_content
        print(f"Live C-Suite Telemetry header mounted in DOM: {has_telemetry_header}")
        
        try:
            assert "#/telemetry" in current_url, f"FRACTURE: Router failed to transition to #/telemetry. Current: {current_url}"
            assert has_telemetry_header, "FRACTURE: Consolidated TelemetryPanel view failed to mount."
            print("Assertion PASSED: TelemetryPanel view successfully mounted via client router.")
        except AssertionError as ae:
            print(f"Assertion FAILED: {ae}")
            success = False

        await browser.close()

    print("\n--- RAW NETWORK TELEMETRY ---")
    for log_item in telemetry:
        print(log_item)
    print("-----------------------------\n")

    if console_errors:
        print("--- CONSOLE ERRORS CAPTURED ---")
        for err in console_errors:
            print(f"ERR -> {err}")
        print("--------------------------------\n")
        print("E2E FAILED DUE TO CONSOLE RUNTIME ERRORS.")
        sys.exit(1)

    if not success:
        sys.exit(1)
    else:
        print("E2E PLAYWRIGHT FRONTEND ASSERTIONS COMPLETED WITH ZERO ERRORS.")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(run_frontend_e2e())
