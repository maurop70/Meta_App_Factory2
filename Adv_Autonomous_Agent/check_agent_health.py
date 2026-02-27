import requests
import sys
import os
import json

# Add project root to path to import bridge
PROJECT_DIR = r"C:\Users\mpetr\My Drive\Antigravity-AI Agents\Meta_App_Factory\Adv_Autonomous_Agent"
if PROJECT_DIR not in sys.path: sys.path.append(PROJECT_DIR)

try:
    from bridge import AGENT_REGISTRY
except ImportError:
    # Fallback if bridge.py import fails (e.g. env vars)
    print("Could not import AGENT_REGISTRY directly. Using hardcoded backup for check.")
    AGENT_REGISTRY = {
        "CFO": "https://humanresource.app.n8n.cloud/webhook/cfo", 
        "CMO": "https://humanresource.app.n8n.cloud/webhook/cmo",
        "HR": "https://humanresource.app.n8n.cloud/webhook/hr",
        "CRITIC": "https://humanresource.app.n8n.cloud/webhook/critic",
        "PITCH": "https://humanresource.app.n8n.cloud/webhook/pitch",
        "ATOMIZER": "https://humanresource.app.n8n.cloud/webhook/atomizer-v2",
        "ARCHITECT": "https://humanresource.app.n8n.cloud/webhook/architect"
    }

print("--- AGENT HEALTH CHECK (DCC DIAGNOSTIC) ---")
print(f"Scanning {len(AGENT_REGISTRY)} Neural Nodes...\n")

active_count = 0
for role, url in AGENT_REGISTRY.items():
    if "role=" in url:
        # Skip fallbacks/routers for now, focus on dedicated
        # print(f"⚪ {role}: Routing Check (Shared Endpoint)")
        continue
        
    print(f"Ping: {role}...", end=" ")
    try:
        # Send a harmless 'health_check' prompt
        # We use a short timeout because we just want to know if it's hitting a 404 or 500
        # A 200 active response is good.
        resp = requests.post(url, json={"prompt": "PING (Health Check)"}, timeout=5)
        
        if resp.status_code == 200:
            print("[OK] ONLINE")
            active_count += 1
        else:
            print(f"[FAIL] ERROR ({resp.status_code})")
            # print(f"   {resp.text[:100]}")
            
    except Exception as e:
        print(f"[WARN] UNREACHABLE: {e}")

print("-" * 30)
print(f"SYSTEM STATUS: {active_count}/{len([k for k,v in AGENT_REGISTRY.items() if 'role=' not in v])} Dedicated Agents Online.")
