"""Quick update: push fixed IF conditions to existing N8N workflow"""
import os, sys, json, requests
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"), override=True)

from deploy_cfo_workflow import CFO_WORKFLOW, N8N_API_BASE, HEADERS

# Find existing workflow
r = requests.get(f"{N8N_API_BASE}/workflows?limit=200", headers=HEADERS, timeout=15)
wfs = [w for w in r.json()["data"] if w["name"] == "Antigravity_CFO_Execution_Controller"]
if not wfs:
    print("Workflow not found!"); sys.exit(1)

wf_id = wfs[0]["id"]
print(f"Updating workflow {wf_id}...")

r2 = requests.put(f"{N8N_API_BASE}/workflows/{wf_id}", headers=HEADERS, json=CFO_WORKFLOW, timeout=15)
print(f"Update: {r2.status_code}")

if r2.status_code == 200:
    # Re-activate
    r3 = requests.post(f"{N8N_API_BASE}/workflows/{wf_id}/activate", headers=HEADERS, timeout=10)
    print(f"Activate: {r3.status_code}")

    # Test
    import time; time.sleep(2)
    url = "https://humanresource.app.n8n.cloud/webhook/cfo-execution-controller"
    payload = {
        "cmo_spend": {"total": 50000, "allocated": 42000},
        "architect_risk": {"structural_score": 82, "logic_score": 78, "security_score": 85, "composite_score": 81.6},
        "campaign_list": [
            {"name": "Q2 Launch", "budget": 15000, "projected_revenue": 45000},
            {"name": "Brand Awareness", "budget": 12000, "projected_revenue": 18000}
        ]
    }
    print("\nTesting valid payload...")
    r4 = requests.post(url, json=payload, timeout=30)
    print(f"Status: {r4.status_code}")
    resp = r4.json()
    print(f"Agent: {resp.get('agent')}")
    print(f"File: {resp.get('file_name')}")
    rpt = resp.get('report', {})
    print(f"Fragility Index: {rpt.get('fragility_index')}")
    print(f"Portfolio ROI: {rpt.get('portfolio_roi_pct')}%")
    print(f"Campaigns: {len(rpt.get('campaigns', []))}")

    print("\nTesting missing fields (expect 400)...")
    r5 = requests.post(url, json={"cmo_spend": {}}, timeout=10)
    print(f"Status: {r5.status_code}")
else:
    print(f"Failed: {r2.text[:300]}")
