import sys
import os
import time
import json

# Set up paths to import sentry_telemetry
SKILLS_PATH = r"c:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\skills"
sys.path.append(SKILLS_PATH)

from sentry_telemetry.observer import SentryObserver

print("--- TELEMETRY TEST: Start ---")

# 1. Start Observer (Short timeout for test)
observer = SentryObserver("TEST_APP", failure_threshold=2.0)
observer.start()

# 2. Simulate Healthy App (3 seconds)
for i in range(3):
    print(f"Main Thread: Work {i}")
    observer.tick({"iteration": i, "status": "HEALTHY"})
    time.sleep(0.5)
    
print("\n--- TELEMETRY TEST: Simulating Freezing (Silent Failure) ---")
print("Main Thread: FROZEN (Sleeping for 4s - Should trigger Alert after 2s)")
time.sleep(4)

# 3. Check Result
print("\n--- TELEMETRY TEST: Checking Results ---")
print(f"Observer Status: {observer.get_status()}")

cache_file = os.path.join(os.getcwd(), ".sentry_cache.json")
if os.path.exists(cache_file):
    with open(cache_file, "r") as f:
        data = json.load(f)
        print("Snapshot Found:")
        print(json.dumps(data, indent=2))
else:
    print("TEST FAILED: No Snapshot found.")

observer.stop()
time.sleep(1) # Cleanup
print("--- TELEMETRY TEST: End ---")
