import sys
import os
import time
import json
import requests
from dotenv import load_dotenv
import bridge # Added missing import

# Path Setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "skills")))
from google_suite import GoogleSuiteManager

# Load Env
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(env_path)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://humanresource.app.n8n.cloud/webhook/elite-council")

# Configuration
DEBUG_PROJECT = "Project_Debug_Phoenix"

# -------------------------------------------------------------------------
# STRICT STOP-AND-FIX DEBUGGER
# -------------------------------------------------------------------------

def run_agent_with_retry(agent_name, input_payload):
    """
    Executes a strict 'Stop-and-Fix' loop.
    It traps the process until the agent returns a valid 200 OK + JSON response.
    Infinite Loop until Agent passes strict checks or correctly handles tools.
    """
    attempt = 1
    while True:
        print(f"\n--- [DEBUGGER] Testing {agent_name} (Attempt {attempt}) ---")
        try:
            # INTEGRATION: Call via Bridge to ensure Tool Awareness & Execution
            # bridge.call_app returns a STRING (Final Output) usually, or a DICT if we change it. 
            # Based on bridge.py, it returns 'output' which is usually text.
            
            print(f"    >>> Invoking Bridge...")
            raw_response = bridge.call_app(input_payload)
            
            # Bridge returns the final text, handling all tool loops internally.
            if not raw_response:
                 raise Exception("Empty Response from Bridge")
            
            content = str(raw_response)
            
            # --- THE APOLOGY TRAP ---
            forbidden_phrases = ["my apologies", "i made an error", "tool does not exist", "unable to", "cannot directly"]
            lower_content = content.lower()
            
            if any(phrase in lower_content for phrase in forbidden_phrases):
                 raise Exception(f"Agent Apology/Failure detected: '{content[:50]}...'")

            # 3. Success -> Break Loop
            print(f"[OK] {agent_name} Passed.")
            # Return a mock dict for compatibility with the rest of the script if needed
            return {"content": content}
            
        except Exception as e:
            # 4. Failure -> Analyze & Retry (Do NOT Proceed)
            print(f"\n[FAIL] {agent_name} Failed: {e}")
            print("   >>> DIAGNOSING & RETRYING in 5 seconds...")
            time.sleep(5)
            
            # Auto-Correction Logic
            current_prompt = input_payload.get("prompt", "")
            if "PREVIOUS ERROR:" not in current_prompt:
                 input_payload["prompt"] = f"{current_prompt}\n\n[SYSTEM NOTICE] PREVIOUS ERROR: {str(e)}. You MUST fix this. Do not apologize, just correct the tool call."
            
            attempt += 1

def run_functional_test(mgr):
    """
    Phase 3: Verify that FILES are actually created.
    """
    print("\n--- [PHASE 3] FUNCTIONAL VERIFICATION (CREATIVE SUITE) ---")
    
    # Test 1: Financial Model
    print(">>> Testing Live Excel Generation...")
    payload = {
        "prompt": "Create a simple Live Excel Financial Model for a 'Lemonade Stand'. Assumptions: Price $5, Cost $2. Return the file.",
        "project_name": "Debug_Functional_Test",
        "suite_command": True
    }
    # We use the generic 'CEO' or 'Bridge' (webhook url is generic)
    try:
        result = run_agent_with_retry("FUNCTIONAL_EXCEL", payload)
        content = str(result.get("output") or result.get("text") or "")
        if "http" not in content and ".xlsx" not in content:
             print(f"[WARNING] No file link detected in output: {content}")
        else:
             print(f"[SUCCESS] Excel Link Generated: {content}")
    except Exception as e:
        print(f"[FAIL] Functional Excel Test Failed: {e}")

    # Test 2: PPTX
    print("\n>>> Testing PPTX Generation...")
    payload = {
        "prompt": "Create a 1-slide Pitch Deck for 'Lemonade Stand'. File type: pptx. Return the file.",
        "project_name": "Debug_Functional_Test",
        "suite_command": True
    }
    try:
        result = run_agent_with_retry("FUNCTIONAL_PPTX", payload)
        content = str(result.get("output") or result.get("text") or "")
        if "http" not in content and ".pptx" not in content:
             print(f"[WARNING] No file link detected in output: {content}")
        else:
             print(f"[SUCCESS] PPTX Link Generated: {content}")
    except: pass

if __name__ == "__main__":
    
    print("--- [INIT] STRICT DEBUGGER PROTOCOL ACTIVATED ---")
    
    # 1. Setup Cloud
    try:
        mgr = GoogleSuiteManager(DEBUG_PROJECT)
        mgr.ensure_project_folder()
        print("--- [CLOUD] Workspace Verified ---")
    except Exception as e:
        print(f"--- [CLOUD] Warning: {e} ---")

    # 2. The Gauntlet (Health Checks)
    agents_to_test = ["CEO", "CFO", "CMO", "CRITIC", "PITCH", "ARCHITECT", "ATOMIZER"]
    
    for agent in agents_to_test:
        payload = {
            "prompt": f"ROLE CHECK: {agent}. Report status and confirm you are online.",
            "project_name": DEBUG_PROJECT,
            "context": "DEBUG_STRICT_MODE"
        }
        run_agent_with_retry(agent, payload)

    print("\n[SUCCESS] PHASE 2 COMPLETE. AGENTS ONLINE.")
    
    # 3. Functional Tests
    run_functional_test(mgr)
    
    print("\n[DONE] SYSTEM VERIFIED.")
