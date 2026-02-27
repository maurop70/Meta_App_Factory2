import os
import sys
import json
import time

# Ensure we can import bridge.py
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

import bridge

def run_test():
    print("--- [TEST] Starting Agent Memory Verification ---")
    
    # Use a unique project name for the test to avoid polluting actual project memory
    test_project = "Memory_Test_Bench"
    
    # 1. Starter Prompt
    print(f"\n[STEP 1] Sending Starter Prompt...")
    starter_prompt = "--- MEMORY TEST START (https://humanresource.app.n8n.cloud/webhook/elite-council) ---"
    payload = {
        "prompt": starter_prompt,
        "project_name": test_project,
        "clean_slate": True # Ensure we start fresh
    }
    resp1 = bridge.call_app(payload)
    print(f"Response 1: {resp1[:100]}...")

    # 2. Inject Secret
    print(f"\n[STEP 2] Injecting Secret...")
    secret_prompt = 'The secret project code is "ALBATROSS-2026". Please remember this code for the next turn.'
    payload = {
        "prompt": secret_prompt,
        "project_name": test_project
    }
    resp2 = bridge.call_app(payload)
    print(f"Response 2: {resp2[:100]}...")

    # 3. Retrieve Secret
    print(f"\n[STEP 3] Retrieving Secret...")
    retrieval_prompt = "What is the secret project code I just gave you?"
    payload = {
        "prompt": retrieval_prompt,
        "project_name": test_project
    }
    resp3 = bridge.call_app(payload)
    print(f"\n--- [FINAL RESULT] ---")
    print(f"Agent Response: {resp3}")
    
    if "ALBATROSS-2026" in resp3:
        print("\n[SUCCESS] Memory Verification Passed!")
    else:
        print("\n[FAIL] Memory Verification Failed. Agent did not recall the secret.")

if __name__ == "__main__":
    run_test()
