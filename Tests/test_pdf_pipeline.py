import os
import json
import time
import subprocess
import shutil

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    universal_memory_dir = os.path.join(base_dir, "Universal_Memory")
    archival_queue_dir = os.path.join(universal_memory_dir, "Archival_Queue")
    permanent_records_dir = os.path.join(universal_memory_dir, "Permanent_Records")
    
    os.makedirs(archival_queue_dir, exist_ok=True)
    os.makedirs(permanent_records_dir, exist_ok=True)

    # Generate Mock Payload
    payload = {
        "document_type": "MWO_REPORT",
        "payload": {
            "mwo_id": "TEST-001",
            "status": "COMPLETED",
            "description": "Autonomous Test",
            "assigned_tech": "AY-Agent"
        }
    }
    
    payload_path = os.path.join(archival_queue_dir, "TEST-001.json")
    with open(payload_path, 'w') as f:
        json.dump(payload, f, indent=4)
        
    print(f"[TEST] Wrote mock payload to {payload_path}")

    # Boot Archival Watchdog Daemon
    watchdog_script = os.path.join(universal_memory_dir, "Archival_Engine", "archival_watchdog.py")
    print(f"[TEST] Booting daemon: {watchdog_script}")
    daemon_proc = subprocess.Popen(["python", watchdog_script])
    
    print("[TEST] Waiting 10 seconds for payload processing...")
    time.sleep(10)
    
    # Terminate Daemon
    print("[TEST] Terminating daemon subprocess...")
    daemon_proc.terminate()
    daemon_proc.wait()
    
    # Assertions
    pdf_path = os.path.join(permanent_records_dir, "TEST-001.pdf")
    if os.path.exists(pdf_path):
        print(f"[ASSERTION_PASSED] PDF successfully generated and relocated: {pdf_path}")
    else:
        print(f"[ASSERTION_FAILED] PDF missing at expected location: {pdf_path}")

if __name__ == "__main__":
    main()
