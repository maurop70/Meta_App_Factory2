import os
import sys
import time
import subprocess
import sqlite3
from playwright.sync_api import sync_playwright

def reset_db():
    print("[E2E] Resetting database state for test...")
    db_path = r"C:\erp_local_data\maintenance_erp.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE work_orders SET status = 'ASSIGNED' WHERE mwo_id = 'MWO-2026-002'")
        conn.commit()
        conn.close()
    except Exception as e:
        print("[E2E] DB reset error:", e)

def main():
    reset_db()
    print("[E2E] Starting E2E Autonomous Browser Simulation")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backend_dir = os.path.join(base_dir, "ERP", "Maintenance_Work_Order")
    frontend_dir = os.path.join(base_dir, "ERP", "maintenance_frontend")
    
    # Start Backend
    print("[E2E] Launching FastAPI Backend...")
    env = os.environ.copy()
    # Note: Using uvicorn module execution
    backend_proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "maintenance_backend:app", "--host", "127.0.0.1", "--port", "8000"], cwd=backend_dir, env=env)
    
    # Start Frontend
    print("[E2E] Launching React Frontend (Vite) on port 5173...")
    frontend_proc = subprocess.Popen(["npm", "run", "dev", "--", "--port", "5173", "--strictPort"], cwd=frontend_dir, shell=True)
    
    print("[E2E] Waiting 10s for servers to boot...")
    time.sleep(10)
    
    try:
        with sync_playwright() as p:
            print("[E2E] Launching Chromium...")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            print("[E2E] Navigating to http://localhost:5173")
            page.goto("http://localhost:5173", wait_until="networkidle")
            
            # Step 1: Inject Tech-Alpha
            print("[E2E] Injecting Tech-Alpha persona...")
            page.get_by_role("button", name="Inject Tech-Alpha").click()
            time.sleep(2)
            
            # Step 2: Locate Ammonia leak MWO and change to PENDING_REVIEW
            print("[E2E] Locating Ammonia leak MWO and updating status...")
            row = page.locator("tr").filter(has_text="Ammonia leak").first
            row.locator("select").select_option("PENDING_REVIEW")
            
            page.once("dialog", lambda dialog: dialog.accept())
            row.get_by_role("button", name="Update Work Order").click()
            time.sleep(2)
            
            # Step 3: Inject HM (Admin)
            print("[E2E] Injecting HM (Admin) persona...")
            page.get_by_role("button", name="Inject HM (Admin)").click()
            time.sleep(1)
            page.goto("http://localhost:5173/")
            time.sleep(2)
            
            # Step 4: Click Reject & Return
            print("[E2E] Clicking Reject & Return...")
            admin_row = page.locator("tr").filter(has_text="Ammonia leak").first
            page.once("dialog", lambda dialog: dialog.accept())
            admin_row.get_by_role("button", name="Reject & Return").click()
            time.sleep(2)
            
            # Step 5: Toggle back to Tech-Alpha
            print("[E2E] Injecting Tech-Alpha persona again...")
            page.get_by_role("button", name="Inject Tech-Alpha").click()
            time.sleep(1)
            page.goto("http://localhost:5173/")
            time.sleep(2)
            
            # Step 6: Verify DOM renders exact string
            print("[E2E] Verifying DOM renders exact string 'IN PROGRESS (REWORK REQUIRED)'...")
            tech_row = page.locator("tr").filter(has_text="Ammonia leak").first
            text_content = tech_row.inner_text()
            if "IN PROGRESS (REWORK REQUIRED)" in text_content:
                print("[E2E] VERIFIED: 'IN PROGRESS (REWORK REQUIRED)' is present in the DOM.")
            else:
                print("[E2E] FAILED: Could not find rework string. Found:", text_content)
                
            # Step 7: Resubmit to PENDING_REVIEW
            print("[E2E] Resubmitting to PENDING_REVIEW...")
            tech_row.locator("select").select_option("PENDING_REVIEW")
            page.once("dialog", lambda dialog: dialog.accept())
            tech_row.get_by_role("button", name="Update Work Order").click()
            time.sleep(2)
            
            # Step 8: Toggle to HM (Admin) and approve
            print("[E2E] Injecting HM (Admin) persona for final approval...")
            page.get_by_role("button", name="Inject HM (Admin)").click()
            time.sleep(1)
            page.goto("http://localhost:5173/")
            time.sleep(2)
            
            print("[E2E] Clicking Approve & Complete...")
            admin_row_final = page.locator("tr").filter(has_text="Ammonia leak").first
            page.once("dialog", lambda dialog: dialog.accept())
            admin_row_final.get_by_role("button", name="Approve & Complete").click()
            
            # Wait for the backend atomic drop to complete
            time.sleep(3)
            
            print("[E2E] Terminating browser session.")
            browser.close()
            
    finally:
        print("[E2E] Terminating background servers...")
        backend_proc.terminate()
        frontend_proc.terminate()
        
    # Step 9: Verify Atomic Drop
    print("[E2E] Verifying Atomic Drop...")
    queue_dir = os.path.join(base_dir, "Universal_Memory", "Archival_Queue")
    if os.path.exists(queue_dir):
        files = [f for f in os.listdir(queue_dir) if f.endswith(".json")]
        if len(files) > 0:
            print(f"[E2E] SUCCESS: Atomic Drop verified. Found {len(files)} JSON payload(s) in Archival_Queue.")
        else:
            print(f"[E2E] WARNING: Archival_Queue directory exists, but no JSON files found.")
    else:
        print(f"[E2E] FAILURE: Archival_Queue directory does not exist at {queue_dir}")

if __name__ == "__main__":
    main()
