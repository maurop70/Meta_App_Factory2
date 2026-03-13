from auto_heal import healed_post, auto_heal, diagnose

"""
deploy_watchdog.py — Deploy SYSTEM_Watchdog_Ping workflow to n8n Cloud
═══════════════════════════════════════════════════════════════════════
Creates a simple Webhook → Respond to Webhook (200 OK) workflow
as the primary health-check target for all heartbeat scripts.
"""

import os, sys, json, requests
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

N8N_API_BASE = "https://humanresource.app.n8n.cloud/api/v1"
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
HEADERS = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}
PROJECT_ID = os.getenv("N8N_DEFAULT_PROJECT_ID", "")

WATCHDOG_WORKFLOW = {
    "name": "SYSTEM_Watchdog_Ping",
    "nodes": [
        {
            "parameters": {
                "path": "system-watchdog-ping",
                "responseMode": "responseNode",
                "options": {}
            },
            "id": "watchdog-webhook",
            "name": "Watchdog Webhook",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "position": [250, 300],
            "webhookId": "system-watchdog-ping"
        },
        {
            "parameters": {
                "respondWith": "json",
                "responseBody": "={{ JSON.stringify({ status: 'ok', timestamp: new Date().toISOString(), service: 'SYSTEM_Watchdog_Ping' }) }}",
                "options": {
                    "responseCode": 200
                }
            },
            "id": "watchdog-respond",
            "name": "Respond OK",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1,
            "position": [470, 300]
        }
    ],
    "connections": {
        "Watchdog Webhook": {
            "main": [
                [
                    {
                        "node": "Respond OK",
                        "type": "main",
                        "index": 0
                    }
                ]
            ]
        }
    },
    "settings": {
        "executionOrder": "v1"
    },
    "staticData": None
}


def main():
    print(f"\n{'='*60}")
    print(f"  🐕 Deploying SYSTEM_Watchdog_Ping")
    print(f"{'='*60}\n")

    # Check if it already exists
    r = requests.get(f"{N8N_API_BASE}/workflows?limit=200", headers=HEADERS, timeout=15)
    existing = r.json().get("data", [])
    watchdog_existing = [w for w in existing if w.get("name") == "SYSTEM_Watchdog_Ping"]
    
    if watchdog_existing:
        wf = watchdog_existing[0]
        print(f"  ℹ️ SYSTEM_Watchdog_Ping already exists (ID: {wf['id']}, active={wf.get('active')})")
        
        if not wf.get("active"):
            # Activate it
            r_act = requests.post(f"{N8N_API_BASE}/workflows/{wf['id']}/activate", 
                                 headers=HEADERS, timeout=10)
            print(f"  Activated: {r_act.status_code}")
        
        webhook_url = f"https://humanresource.app.n8n.cloud/webhook/system-watchdog-ping"
        print(f"\n  Webhook URL: {webhook_url}")
        
        # Test it
        print(f"  Testing...")
        try:
            r_test = requests.get(webhook_url, timeout=5)
            print(f"  Response: {r_test.status_code} — {r_test.text[:100]}")
        except Exception as e:
            print(f"  Test failed: {e}")
        
        return wf["id"]
    
    # Create new workflow
    print("  Creating new SYSTEM_Watchdog_Ping workflow...")
    r_create = requests.post(f"{N8N_API_BASE}/workflows", headers=HEADERS, 
                            json=WATCHDOG_WORKFLOW, timeout=15)
    
    if r_create.status_code in (200, 201):
        new_wf = r_create.json()
        wf_id = new_wf.get("id", "?")
        print(f"  ✅ Created: ID={wf_id}")
        
        # Activate
        r_act = requests.post(f"{N8N_API_BASE}/workflows/{wf_id}/activate",
                             headers=HEADERS, timeout=10)
        print(f"  Activate: {r_act.status_code}")
        
        webhook_url = f"https://humanresource.app.n8n.cloud/webhook/system-watchdog-ping"
        print(f"\n  Webhook URL: {webhook_url}")
        
        # Test
        import time
        time.sleep(2)
        print(f"  Testing...")
        try:
            r_test = requests.get(webhook_url, timeout=5)
            print(f"  Response: {r_test.status_code} — {r_test.text[:100]}")
        except Exception as e:
            print(f"  Test failed: {e}")
        
        return wf_id
    else:
        print(f"  ❌ Creation failed: {r_create.status_code}")
        print(f"  Body: {r_create.text[:300]}")
        return None


if __name__ == "__main__":
    wf_id = main()
    print(f"\n{'='*60}\n")

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
