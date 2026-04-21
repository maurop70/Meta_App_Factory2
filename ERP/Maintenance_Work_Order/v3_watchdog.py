import subprocess
import time
import sys
import os

def run_server():
    """
    Launches the Maintenance V3 backend with auto-restart watchdog logic.
    """
    cmd = [sys.executable, "-m", "uvicorn", "maintenance_backend:app", "--port", "8000", "--reload"]
    
    print("[WATCHDOG] Starting Maintenance V3 Server...")
    
    while True:
        try:
            # Start uvicorn as a subprocess in a new console to prevent EOF crashes when run headlessly
            # TODO: Remove Windows-specific creationflags during Docker migration as they will crash a Linux Docker daemon
            process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
            
            # Wait for the process to exit
            process.wait()
            
            if process.returncode != 0:
                print(f"[WATCHDOG] Server exited with code {process.returncode}. Restarting in 3 seconds...")
                time.sleep(3)
            else:
                print("[WATCHDOG] Server stopped gracefully. Exiting watchdog.")
                break
                
        except KeyboardInterrupt:
            print("\n[WATCHDOG] Shutting down...")
            process.terminate()
            break
        except Exception as e:
            print(f"[WATCHDOG] Error: {e}. Restarting...")
            time.sleep(5)

if __name__ == "__main__":
    # Ensure we are in the correct directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    run_server()
