import subprocess
import time
import os
import json
from playwright.sync_api import sync_playwright

def kill_port(port):
    import re
    output = os.popen(f"netstat -ano | findstr :{port}").read()
    for line in output.splitlines():
        if "LISTENING" in line:
            pid = re.split(r'\s+', line.strip())[-1]
            os.system(f"taskkill /PID {pid} /F")

def run_termination_test():
    print("--- STARTING MATRIX ENVIRONMENTS ---")
    kill_port(8000)
    kill_port(5175)
    
    backend_proc = subprocess.Popen(["python", "-m", "uvicorn", "maintenance_backend:app", "--port", "8000"], cwd=r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Maintenance_Work_Order", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    frontend_proc = subprocess.Popen(["npx.cmd", "vite", "--port", "5175", "--clearScreen", "false"], cwd=r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\maintenance_frontend", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    print("Waiting for boot sequence (8 seconds)...")
    time.sleep(8)
    
    # Pre-inject a test user so we have something to terminate without breaking the DB
    import sqlite3
    db_path = r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Maintenance_Work_Order\data\maintenance_erp.db"
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT OR REPLACE INTO users (user_id, name, role, department, is_active, token_version) VALUES ('TERM-100', 'Termination Target', 'TECH', 'Maintenance', 1, 1)")
    conn.execute("INSERT OR IGNORE INTO users (user_id, name, role, department, is_active, token_version) VALUES ('9999', 'System Administrator', 'ADMIN', 'HQ', 1, 1)")
    conn.commit()
    conn.close()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            print("Navigating to Login View...")
            page.goto("http://127.0.0.1:5175/login")
            
            page.wait_for_selector("input[type='password']")
            page.fill("input[type='password']", "9999")
            page.click("button[type='submit']")
            
            # Wait for matrix to render
            page.wait_for_selector(".erp-data-matrix", timeout=10000)
            print("TELEMETRY: Active enterprise matrix rendered on React UI.")
            
            # Wait for target user
            page.wait_for_selector("td:has-text('TERM-100')")
            
            # Click INSPECT
            row = page.locator("tr", has_text="TERM-100")
            row.locator("button:has-text('INSPECT')").click()
            print("TELEMETRY: Triggered INSPECT actuation.")
            
            # Wait for modal
            page.wait_for_selector(".modal-overlay")
            # Wait for contextual telemetry
            page.wait_for_selector("h3:has-text('Contextual History')")
            print("TELEMETRY: Contextual telemetry payload ingested cleanly.")
            
            # Type confirm ID
            page.fill("input[placeholder='Type TERM-100 to confirm']", "TERM-100")
            
            # Setup interceptor for Axios network telemetry
            with page.expect_response(lambda r: "TERM-100" in r.url and r.request.method == "DELETE") as del_info:
                page.locator("button:has-text('TERMINATE SYSTEM ACCESS')").click()
                print("TELEMETRY: Executed terminal DELETE actuation utilizing strict string-matching guardrail.")
                
            res = del_info.value
            print(f"Axios Network Telemetry - DELETE Response: {res.status}")
            
            # Wait for success UI state
            page.wait_for_selector("div:has-text('Access terminated successfully.')")
            print("TELEMETRY: Modal UI state transitioned to success confirmation.")
            
            # Wait for auto-unmount
            page.wait_for_selector(".modal-overlay", state="hidden", timeout=5000)
            print("TELEMETRY: Modal automatically unmounted.")
            
            # Verify physically purged from UI without reload
            page.wait_for_timeout(1000)
            if row.count() == 0 or not row.is_visible():
                print("TELEMETRY: Parent <EnterpriseDataMatrix /> physically purged the terminated operator from the UI without manual refresh.")
            else:
                print("TELEMETRY ERROR: Row is still visible.")

            browser.close()
            
    except Exception as e:
        print(f"Matrix failure: {e}")
    finally:
        print("\n--- SHUTTING DOWN ENVIRONMENTS ---")
        backend_proc.terminate()
        frontend_proc.terminate()
        
        print("\n[BACKEND TERMINAL LOGS]")
        try:
            be_out, _ = backend_proc.communicate(timeout=2)
            lines = be_out.strip().split('\n')
            print('\n'.join(lines[-25:]))
        except Exception:
            pass

if __name__ == "__main__":
    run_termination_test()
