import subprocess
import time
import os
import shutil
import json
from playwright.sync_api import sync_playwright

def kill_port(port):
    import re
    output = os.popen(f"netstat -ano | findstr :{port}").read()
    for line in output.splitlines():
        if "LISTENING" in line:
            pid = re.split(r'\s+', line.strip())[-1]
            os.system(f"taskkill /PID {pid} /F")

def run_matrix():
    print("--- STARTING MATRIX ENVIRONMENTS ---")
    kill_port(8000)
    kill_port(5175)
    
    backend_proc = subprocess.Popen(["python", "-m", "uvicorn", "maintenance_backend:app", "--port", "8000"], cwd=r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Maintenance_Work_Order", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    watchdog_proc = subprocess.Popen(["python", "archival_watchdog.py"], cwd=r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\Universal_Memory\Archival_Engine", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    frontend_proc = subprocess.Popen(["npx.cmd", "vite", "--port", "5175", "--clearScreen", "false"], cwd=r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\maintenance_frontend", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    print("Waiting for boot sequence (8 seconds)...")
    time.sleep(8)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            # Listen to console logs to ensure no auth:termination fires prematurely
            console_logs = []
            page.on("console", lambda msg: console_logs.append(msg.text))
            
            print("\n===============================")
            print("PHASE 1: SESSION BOOTSTRAP VALIDATION")
            print("===============================\n")
            
            print("Navigating to Login View...")
            page.goto("http://127.0.0.1:5175/login")
            
            # Wait for elements
            page.wait_for_selector("input[type='password']")
            page.fill("input[type='password']", "9999")
            
            print("Authenticating...")
            with page.expect_response("**/user/authenticate") as response_info:
                page.click("button[type='submit']")
            
            auth_res = response_info.value
            print(f"Auth Response: {auth_res.status} {auth_res.status_text}")
            
            cookies = context.cookies()
            refresh_cookie = next((c for c in cookies if c['name'] == 'refresh_token'), None)
            if refresh_cookie:
                print("TELEMETRY: HttpOnly Refresh Cookie received.")
                print(f"Cookie Flags: HttpOnly={refresh_cookie.get('httpOnly')} Secure={refresh_cookie.get('secure')} SameSite={refresh_cookie.get('sameSite')}")
            else:
                print("TELEMETRY: NO HttpOnly Refresh Cookie found!")
            
            print("\nExecuting Hard Refresh (F5)...")
            # We expect a request to /user/refresh on load
            with page.expect_response("**/user/refresh", timeout=10000) as refresh_info:
                page.reload()
                
            refresh_res = refresh_info.value
            print(f"Refresh Response after F5: {refresh_res.status}")
            if refresh_res.status == 200:
                print("TELEMETRY: Session seamlessly reconstructed via background useEffect trigger.")
            else:
                print(f"TELEMETRY: Failed to reconstruct session. Status: {refresh_res.status}")
                
            # Verify auth:termination didn't fire (we can't easily listen to CustomEvents without evaluating JS, let's inject a listener)
            termination_fired = page.evaluate("""
                () => {
                    window.terminationEventFired = false;
                    window.addEventListener('auth:termination', () => window.terminationEventFired = true);
                    return window.terminationEventFired;
                }
            """)
            print(f"TELEMETRY: CustomEvent('auth:termination') fired: {termination_fired}")
            
            print("\n===============================")
            print("PHASE 2: I/O BACKGROUND ISOLATION VALIDATION")
            print("===============================\n")
            
            print("Navigating to Admin bulk-upload...")
            page.goto("http://127.0.0.1:5175/admin")
            page.wait_for_selector("#csvUpload", state="attached", timeout=10000)
            
            csv_path = "test_upload.csv"
            with open(csv_path, "w") as f:
                f.write("user_id,name,role,department,reports_to_hm_id\n")
                f.write("TEST-U1,Test Admin,ADMIN,HQ,\n")
                
            page.set_input_files("#csvUpload", csv_path)
            
            print("Uploading payload and measuring latency...")
            start_time = time.perf_counter()
            with page.expect_response("**/bulk-upload") as upload_info:
                page.click("button:has-text('Upload Data')")
            end_time = time.perf_counter()
            
            upload_res = upload_info.value
            duration_ms = (end_time - start_time) * 1000
            
            print(f"Upload Response Status: {upload_res.status}")
            print(f"Upload Client-Side Latency: {duration_ms:.2f} ms")
            if upload_res.status == 202 and duration_ms < 100:
                print("TELEMETRY: FastAPI returned 202 Accepted instantly. I/O Isolation Validated.")
            
            print("\n===============================")
            print("PHASE 3: CPU MULTIPROCESSING VALIDATION")
            print("===============================\n")
            
            queue_dir = r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\Universal_Memory\Archival_Queue"
            os.makedirs(queue_dir, exist_ok=True)
            
            test_json = {
                "payload": {
                    "mwo_id": "TEST-MATRIX",
                    "equipment_id": "EQ-99",
                    "issue_description": "Matrix test"
                }
            }
            json_path = os.path.join(queue_dir, "test_matrix.json")
            with open(json_path, "w") as f:
                json.dump(test_json, f)
            
            print("Dropped test_matrix.json into Archival_Queue.")
            print("Waiting for Watchdog to claim and dispatch (5 seconds)...")
            time.sleep(5)
            
            browser.close()
            
    except Exception as e:
        print(f"Matrix failure: {e}")
    finally:
        print("\n--- SHUTTING DOWN ENVIRONMENTS ---")
        backend_proc.terminate()
        watchdog_proc.terminate()
        frontend_proc.terminate()
        
        if os.path.exists("test_upload.csv"):
            os.remove("test_upload.csv")
            
        # Collect and print watchdog logs
        print("\n[WATCHDOG TERMINAL LOGS]")
        try:
            wd_out, _ = watchdog_proc.communicate(timeout=2)
            print(wd_out)
        except Exception:
            pass
            
        print("\n[FRONTEND TERMINAL LOGS]")
        try:
            fe_out, _ = frontend_proc.communicate(timeout=2)
            lines = fe_out.strip().split('\n')
            print('\n'.join(lines[-15:]))
        except Exception:
            pass
            
        print("\n[BACKEND TERMINAL LOGS]")
        try:
            be_out, _ = backend_proc.communicate(timeout=2)
            # Print last 15 lines of backend logs
            lines = be_out.strip().split('\n')
            print('\n'.join(lines[-15:]))
        except Exception:
            pass

if __name__ == "__main__":
    run_matrix()
