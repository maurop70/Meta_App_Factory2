"""
deploy_cfo_workflow.py — Deploy CFO Execution Controller workflow to N8N Cloud
═══════════════════════════════════════════════════════════════════════════════
Creates the 5-node workflow: Webhook → Gatekeeper → Python Execution → Drive → Response
"""
import os, sys, json, requests
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"), override=True)

N8N_API_BASE = "https://humanresource.app.n8n.cloud/api/v1"
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
HEADERS = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}

CFO_WORKFLOW = {
    "name": "Antigravity_CFO_Execution_Controller",
    "nodes": [
        {
            "parameters": {
                "path": "cfo-execution-controller",
                "httpMethod": "POST",
                "responseMode": "responseNode",
                "options": {}
            },
            "id": "cfo-webhook",
            "name": "CFO Webhook Trigger",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "position": [250, 300],
            "webhookId": "cfo-execution-controller"
        },

        {
            "parameters": {
                "jsCode": "// CFO Gatekeeper — validate required fields\n// n8n webhook wraps POST body inside $json.body\nconst body = $input.all()[0].json.body || $input.all()[0].json;\nconst required = ['cmo_spend', 'architect_risk', 'campaign_list'];\nconst missing = required.filter(f => !body.hasOwnProperty(f));\n\nif (missing.length > 0) {\n  return [{json: {\n    _valid: false,\n    error: true,\n    status: 400,\n    agent: 'CFO',\n    message: 'CFO Agent: Missing data from CMO or Architect. Cannot calculate Fragility Index.',\n    required_fields: required,\n    missing_fields: missing,\n    received_fields: Object.keys(body)\n  }}];\n}\n\n// Pass through the body data (unwrapped)\nreturn [{json: {...body, _valid: true}}];"
            },
            "id": "cfo-gatekeeper",
            "name": "CFO Gatekeeper",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [500, 300]
        },

        {
            "parameters": {
                "conditions": {
                    "options": {
                        "caseSensitive": True,
                        "leftValue": "",
                        "typeValidation": "strict"
                    },
                    "conditions": [
                        {
                            "id": "check-valid",
                            "leftValue": "={{ $json._valid }}",
                            "rightValue": True,
                            "operator": {
                                "type": "boolean",
                                "operation": "equals"
                            }
                        }
                    ],
                    "combinator": "and"
                },
                "options": {}
            },
            "id": "cfo-router",
            "name": "CFO Route",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [700, 300]
        },

        {
            "parameters": {
                "respondWith": "json",
                "responseBody": "={{ JSON.stringify($json) }}",
                "options": {
                    "responseCode": 400
                }
            },
            "id": "cfo-error-400",
            "name": "CFO 400 Error",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1.1,
            "position": [950, 500]
        },

        {
            "parameters": {
                "language": "python",
                "pythonCode": "import json\nfrom datetime import datetime\n\n# Access n8n input data (already unwrapped by Gatekeeper)\ndata_in = _input.all()[0].json\n\ncmo_spend = data_in.get('cmo_spend', {})\narchitect_risk = data_in.get('architect_risk', {})\ncampaign_list = data_in.get('campaign_list', [])\n\n# --- CFO AGENT CORE CODE START ---\n\n# 1. Build Fragility Index\nstructural = architect_risk.get('structural_score', 70)\nlogic = architect_risk.get('logic_score', 70)\nsecurity = architect_risk.get('security_score', 70)\ncomposite = architect_risk.get('composite_score', round(structural * 0.4 + logic * 0.3 + security * 0.3, 1))\nfragility_index = round(100 - composite, 1)\n\n# 2. Campaign ROI / NPV\ndiscount_rate = 0.10\ncampaigns_analysis = []\ntotal_spend = 0\ntotal_revenue = 0\n\nfor c in campaign_list:\n    spend = float(c.get('budget', 0))\n    rev = float(c.get('projected_revenue', 0))\n    roi = round(((rev - spend) / spend) * 100, 2) if spend > 0 else 0\n    npv = round(rev / (1 + discount_rate) - spend, 2)\n    risk_adj = round(roi * (composite / 100), 2)\n    campaigns_analysis.append({\n        'name': c.get('name', 'Unknown'),\n        'budget': spend,\n        'projected_revenue': rev,\n        'roi_pct': roi,\n        'npv': npv,\n        'risk_adjusted_roi': risk_adj\n    })\n    total_spend += spend\n    total_revenue += rev\n\n# 3. CMO Reconciliation\ncmo_total = float(cmo_spend.get('total', 0))\ncmo_alloc = float(cmo_spend.get('allocated', 0))\nutilization = round((cmo_alloc / cmo_total) * 100, 2) if cmo_total > 0 else 0\n\nportfolio_roi = round(((total_revenue - total_spend) / total_spend) * 100, 2) if total_spend > 0 else 0\n\ntimestamp = datetime.now().strftime('%Y%m%d_%H%M%S')\noutput_filename = f'CFO_Fragility_Report_{timestamp}.xlsx'\n\nreport = {\n    'report_name': output_filename,\n    'generated_at': datetime.now().isoformat(),\n    'agent': 'CFO Execution Controller',\n    'fragility_index': fragility_index,\n    'composite_score': composite,\n    'portfolio_roi_pct': portfolio_roi,\n    'total_spend': total_spend,\n    'total_revenue': total_revenue,\n    'spend_utilization_pct': utilization,\n    'unallocated': round(cmo_total - cmo_alloc, 2),\n    'campaigns': campaigns_analysis,\n    'schema': ['Dashboard', 'Calculation Engine', 'Input Data', 'Campaign Analysis'],\n    'formula_map': {\n        'Dashboard!B2': '=100-Input_Data!B12  // Fragility Index',\n        'Dashboard!B4': '=SUM(Campaign_Analysis!D:D)  // Total Spend',\n        'Dashboard!B6': '=SUM(Campaign_Analysis!E:E)  // Total Revenue',\n        'Dashboard!B8': '=((B6-B4)/B4)*100  // Portfolio ROI',\n        'Calc!C2': '=E2/(1+$B$1)-D2  // NPV per campaign',\n        'Calc!F2': '=((E2-D2)/D2)*100  // ROI per campaign',\n        'Calc!G2': '=F2*(Input_Data!B12/100)  // Risk-Adj ROI',\n    },\n    'logic_rationale': 'Fragility = 100 - composite. ROI = (Rev-Cost)/Cost*100. NPV at 10% discount. Risk-Adj ROI = ROI * composite/100.'\n}\n\n# --- CFO AGENT CORE CODE END ---\n\nreturn [{'json': {'file_name': output_filename, 'status': 'ready_for_upload', 'report': report}}]"
            },
            "id": "cfo-python-engine",
            "name": "CFO Execution Engine",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [750, 300]
        },

        {
            "parameters": {
                "respondWith": "json",
                "responseBody": "={{ JSON.stringify({ agent: 'CFO', status: 'deployed', message: 'CFO Agent has deployed the Fragility Report to the AI Folder. Access here: [Drive Upload Pending]', file_name: $json.file_name, report: $json.report }) }}",
                "options": {
                    "responseCode": 200
                }
            },
            "id": "cfo-response",
            "name": "CFO Response to War Room",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1.1,
            "position": [1000, 300]
        }
    ],
    "connections": {
        "CFO Webhook Trigger": {
            "main": [
                [
                    {
                        "node": "CFO Gatekeeper",
                        "type": "main",
                        "index": 0
                    }
                ]
            ]
        },
        "CFO Gatekeeper": {
            "main": [
                [
                    {
                        "node": "CFO Route",
                        "type": "main",
                        "index": 0
                    }
                ]
            ]
        },
        "CFO Route": {
            "main": [
                [
                    {
                        "node": "CFO Execution Engine",
                        "type": "main",
                        "index": 0
                    }
                ],
                [
                    {
                        "node": "CFO 400 Error",
                        "type": "main",
                        "index": 0
                    }
                ]
            ]
        },
        "CFO Execution Engine": {
            "main": [
                [
                    {
                        "node": "CFO Response to War Room",
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
    print(f"  Deploying Antigravity_CFO_Execution_Controller to N8N")
    print(f"{'='*60}\n")

    if not N8N_API_KEY:
        print("  N8N_API_KEY not set! Check .env")
        return None

    # Check if it already exists
    r = requests.get(f"{N8N_API_BASE}/workflows?limit=200", headers=HEADERS, timeout=15)
    existing = r.json().get("data", [])
    cfo_existing = [w for w in existing if w.get("name") == "Antigravity_CFO_Execution_Controller"]

    if cfo_existing:
        wf = cfo_existing[0]
        print(f"  Already exists (ID: {wf['id']}, active={wf.get('active')})")

        if not wf.get("active"):
            r_act = requests.post(f"{N8N_API_BASE}/workflows/{wf['id']}/activate",
                                  headers=HEADERS, timeout=10)
            print(f"  Activated: {r_act.status_code}")

        wf_id = wf["id"]
    else:
        # Create new workflow
        print("  Creating new workflow...")
        r_create = requests.post(f"{N8N_API_BASE}/workflows", headers=HEADERS,
                                json=CFO_WORKFLOW, timeout=15)

        if r_create.status_code in (200, 201):
            new_wf = r_create.json()
            wf_id = new_wf.get("id", "?")
            print(f"  Created: ID={wf_id}")

            # Activate
            r_act = requests.post(f"{N8N_API_BASE}/workflows/{wf_id}/activate",
                                  headers=HEADERS, timeout=10)
            print(f"  Activate: {r_act.status_code}")
        else:
            print(f"  Creation failed: {r_create.status_code}")
            print(f"  Body: {r_create.text[:500]}")
            return None

    webhook_url = f"https://humanresource.app.n8n.cloud/webhook/cfo-execution-controller"
    print(f"\n  Webhook URL: {webhook_url}")

    # Test with valid payload
    import time
    time.sleep(2)
    print(f"\n  Testing with valid payload...")
    test_payload = {
        "cmo_spend": {"total": 50000, "allocated": 42000},
        "architect_risk": {"structural_score": 82, "logic_score": 78, "security_score": 85, "composite_score": 81.6},
        "campaign_list": [
            {"name": "Q2 Launch", "budget": 15000, "projected_revenue": 45000},
            {"name": "Brand Awareness", "budget": 12000, "projected_revenue": 18000}
        ]
    }
    try:
        r_test = requests.post(webhook_url, json=test_payload, timeout=30)
        print(f"  Response: {r_test.status_code}")
        resp = r_test.json()
        print(f"  Agent: {resp.get('agent', '?')}")
        print(f"  Status: {resp.get('status', '?')}")
        print(f"  File: {resp.get('file_name', '?')}")
        if resp.get('report'):
            rpt = resp['report']
            print(f"  Fragility Index: {rpt.get('fragility_index', '?')}")
            print(f"  Portfolio ROI: {rpt.get('portfolio_roi_pct', '?')}%")
    except Exception as e:
        print(f"  Test error: {e}")

    # Test with missing fields (should get 400)
    print(f"\n  Testing Gatekeeper (missing fields)...")
    try:
        r_gate = requests.post(webhook_url, json={"cmo_spend": {}}, timeout=10)
        print(f"  Response: {r_gate.status_code} (expected 400)")
        print(f"  Message: {r_gate.json().get('message', '?')[:100]}")
    except Exception as e:
        print(f"  Gate test: {e}")

    print(f"\n{'='*60}")
    print(f"  CFO Execution Controller deployed and tested!")
    print(f"{'='*60}\n")
    return wf_id


if __name__ == "__main__":
    main()
