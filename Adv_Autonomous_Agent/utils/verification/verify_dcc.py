import sys
import os
import time
import threading

sys.stdout.reconfigure(encoding='utf-8')

# Setup Paths to mimic Adv_Autonomous_Agent environment
BASE_DIR = r"c:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Meta_App_Factory\Adv_Autonomous_Agent"
SKILLS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "skills"))
sys.path.append(SKILLS_DIR)

try:
    from sentry_telemetry.observer import SentryObserver
    print("✅ SentryObserver Module Loaded Successfully")
except ImportError as e:
    print(f"❌ Failed to load SentryObserver: {e}")
    sys.exit(1)

def run_dcc_test():
    print("--- STARTING DCC (SENTRY) VERIFICATION FOR ADV_AGENT ---")
    
    # Initialize Observer
    observer = SentryObserver("Adv_Autonomous_Agent", heartbeat_interval=1.0, failure_threshold=3.0)
    observer.start()
    print("✅ Sentry Observer Thread Started")
    
    # Simulate Heartbeats (Healthy)
    for i in range(3):
        time.sleep(1)
        observer.tick({"status": "healthy", "tick": i})
        status = observer.get_status()
        print(f"[{i+1}/3] Heartbeat Sent. Sentry Status: {status}")
        
    # Simulate "Busy" State (No Heartbeat for 2 seconds - Should remain ACTIVE/WARNING)
    print("--- SIMULATING HEAVY LOAD (2s Pause) ---")
    time.sleep(2)
    observer.tick({"status": "recovering"})
    print(f"[Results] Status after pause: {observer.get_status()}")

    # Simulate CRITICAL Failure (No Heartbeat for 4 seconds > 3s threshold)
    print("--- SIMULATING CRASH (4s Pause) ---")
    time.sleep(4)
    status = observer.get_status()
    print(f"[Results] Status after crash simulation: {status}")
    
    if status == "CRITICAL":
        print("✅ SILENT FAILURE DETECTED CORRECTLY")
    else:
        print("❌ FAILED TO DETECT SILENT FAILURE")

    # Access the shared cache to prove persistence
    cache_path = os.path.join(BASE_DIR, ".sentry_cache.json")
    if os.path.exists(cache_path):
        print(f"✅ Telemetry Cache Found at: {cache_path}")
    else:
        print("⚠️ No Telemetry Cache Found (might be first run)")

    observer.running = False
    print("--- DCC VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    run_dcc_test()
