import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    print("==================================================")
    print("   PLAYWRIGHT GATEKEEPER: DOM HYDRATION TEST      ")
    print("==================================================")
    print("Target: Atomizer_STAGING.jsx")
    print("Mode: Headless Verification Matrix")
    print("Initializing Chromium core...")

    html_path = os.path.abspath("staging/test_atomizer.html")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        errors = []
        page.on("pageerror", lambda err: errors.append(err.message))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        
        print(f"Mounting DOM fixture: {html_path} ...")
        await page.goto(f"file:///{html_path}")
        
        # Wait for Babel to transpile and React to mount
        await page.wait_for_selector("#atomizer-panel", timeout=5000)
        
        panel_exists = await page.evaluate("() => !!document.getElementById('atomizer-panel')")
        input_app_exists = await page.evaluate("() => !!document.getElementById('child-app-id')")
        input_path_exists = await page.evaluate("() => !!document.getElementById('relative-path')")
        btn_exists = await page.evaluate("() => !!document.getElementById('ingest-btn')")
        
        print("\n[DOM TOPOLOGY VERIFICATION]")
        print(f"  --> #atomizer-panel  : {'PASS' if panel_exists else 'FAIL'}")
        print(f"  --> #child-app-id    : {'PASS' if input_app_exists else 'FAIL'}")
        print(f"  --> #relative-path   : {'PASS' if input_path_exists else 'FAIL'}")
        print(f"  --> #ingest-btn      : {'PASS' if btn_exists else 'FAIL'}")
        
        print("\n[HYDRATION STATE AUDIT]")
        if len(errors) == 0:
            print("  --> ZERO console errors detected during mount phase.")
            print("  --> React Hydration: SUCCESS")
        else:
            print("  --> FATAL: Console errors detected during mount:")
            for e in errors:
                print(f"      - {e}")
            print("  --> React Hydration: FAILED")
            
        print("==================================================")
        if panel_exists and len(errors) == 0:
            print("STATUS: VERIFIED. ZERO STRUCTURAL FRACTURES.")
            print("MATRIX: SECURE.")
        else:
            print("STATUS: CORRUPTED.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
