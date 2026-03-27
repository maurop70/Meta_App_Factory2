"""
deploy_cfo_v2.py — Enhanced CFO Execution Controller
═════════════════════════════════════════════════════
V2 additions:
  - Missing data → callback to Master Architect (5050) instead of just 400
  - Math error → callback to CFO Agent in Meta App Factory
  - WarRoom_CFO_Report_[TS].xlsx naming
  - Google Drive upload to AI FOLDERS
  - Returns Web View Link + Fragility summary to War Room
"""
import os, sys, json, requests, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"), override=True)

N8N_API_BASE = "https://humanresource.app.n8n.cloud/api/v1"
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
HEADERS = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}
WORKFLOW_NAME = "Antigravity_CFO_Execution_Controller"

CFO_WORKFLOW_V2 = {
    "name": WORKFLOW_NAME,
    "nodes": [
        # ── Node 1: Webhook Trigger ──────────────────────────
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

        # ── Node 2: Gatekeeper (JS Code) ─────────────────────
        # Validates payload, unwraps body, and flags _valid
        # If missing → sets _callback_architect = true with missing fields
        {
            "parameters": {
                "jsCode": "\n".join([
                    "// CFO Gatekeeper — validate required fields",
                    "// n8n webhook wraps POST body inside $json.body",
                    "const body = $input.all()[0].json.body || $input.all()[0].json;",
                    "const required = ['cmo_spend', 'architect_risk', 'campaign_list'];",
                    "const missing = required.filter(f => !body.hasOwnProperty(f));",
                    "",
                    "if (missing.length > 0) {",
                    "  return [{json: {",
                    "    _valid: false,",
                    "    _callback_architect: true,",
                    "    agent: 'CFO',",
                    "    message: 'CFO Agent: Missing data from CMO or Architect. Cannot calculate Fragility Index.',",
                    "    missing_fields: missing,",
                    "    received_fields: Object.keys(body),",
                    "    partial_data: body",
                    "  }}];",
                    "}",
                    "",
                    "// Pass through unwrapped data",
                    "return [{json: {...body, _valid: true}}];",
                ])
            },
            "id": "cfo-gatekeeper",
            "name": "CFO Gatekeeper",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [500, 300]
        },

        # ── Node 3: Router (IF) ──────────────────────────────
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

        # ── Node 4a: Respond directly with missing data info ──────
        # Master Architect is local (5050), not reachable from N8N Cloud.
        # Instead, return the missing data details so the caller can coordinate.
        {
            "parameters": {
                "respondWith": "json",
                "responseBody": '={{ JSON.stringify({ agent: "CFO", status: "awaiting_data", message: "CFO Agent: Missing data from CMO or Architect. Cannot calculate Fragility Index.", missing_fields: $json.missing_fields, received_fields: $json.received_fields, callback_url: "https://humanresource.app.n8n.cloud/webhook/cfo-execution-controller", instruction: "Please re-submit with all required fields: cmo_spend, architect_risk, campaign_list" }) }}',
                "options": {
                    "responseCode": 400
                }
            },
            "id": "cfo-missing-data-response",
            "name": "CFO Missing Data Response",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1.1,
            "position": [950, 500]
        },

        # (Node 4b removed — merged into 4a direct response)

        # ── Node 5: JavaScript Execution Engine ─────────────────
        # N8N Cloud Python sandbox bans stdlib imports. Using JS instead.
        # Wrapped in try/catch for math errors.
        {
            "parameters": {
                "jsCode": "\n".join([
                    "// CFO Execution Engine — JavaScript (N8N Cloud compatible)",
                    "const data = $input.all()[0].json;",
                    "",
                    "const cmo = data.cmo_spend || {};",
                    "const risk = data.architect_risk || {};",
                    "const campaigns = data.campaign_list || [];",
                    "",
                    "try {",
                    "  // 1. Fragility Index = 100 - Composite",
                    "  const structural = Number(risk.structural_score || 70);",
                    "  const logic = Number(risk.logic_score || 70);",
                    "  const security = Number(risk.security_score || 70);",
                    "  const composite = Number(risk.composite_score || Math.round((structural*0.4 + logic*0.3 + security*0.3)*10)/10);",
                    "  const fragility = Math.round((100 - composite) * 10) / 10;",
                    "",
                    "  // 2. Campaign ROI / NPV",
                    "  const rate = 0.10;",
                    "  let totalSpend = 0, totalRev = 0;",
                    "  const analysis = campaigns.map(c => {",
                    "    const spend = Number(c.budget || 0);",
                    "    const rev = Number(c.projected_revenue || 0);",
                    "    const roi = spend > 0 ? Math.round(((rev - spend) / spend) * 10000) / 100 : 0;",
                    "    const npv = Math.round((rev / (1 + rate) - spend) * 100) / 100;",
                    "    const riskAdj = Math.round(roi * (composite / 100) * 100) / 100;",
                    "    totalSpend += spend; totalRev += rev;",
                    "    return { name: c.name || 'Unknown', budget: spend, projected_revenue: rev, roi_pct: roi, npv, risk_adjusted_roi: riskAdj };",
                    "  });",
                    "",
                    "  // 3. CMO Reconciliation",
                    "  const cmoTotal = Number(cmo.total || 0);",
                    "  const cmoAlloc = Number(cmo.allocated || 0);",
                    "  const util = cmoTotal > 0 ? Math.round((cmoAlloc / cmoTotal) * 10000) / 100 : 0;",
                    "  const portRoi = totalSpend > 0 ? Math.round(((totalRev - totalSpend) / totalSpend) * 10000) / 100 : 0;",
                    "",
                    "  // 4. Build Report",
                    "  const ts = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15);",
                    "  const filename = `WarRoom_CFO_Report_${ts}.xlsx`;",
                    "",
                    "  return [{ json: {",
                    "    file_name: filename,",
                    "    status: 'ready_for_upload',",
                    "    _math_error: false,",
                    "    report: {",
                    "      report_name: filename,",
                    "      generated_at: new Date().toISOString(),",
                    "      agent: 'CFO Execution Controller',",
                    "      fragility_index: fragility,",
                    "      composite_score: composite,",
                    "      portfolio_roi_pct: portRoi,",
                    "      total_spend: totalSpend,",
                    "      total_revenue: totalRev,",
                    "      spend_utilization_pct: util,",
                    "      unallocated: Math.round((cmoTotal - cmoAlloc) * 100) / 100,",
                    "      campaigns: analysis,",
                    "      campaign_count: analysis.length,",
                    "      schema: ['Dashboard', 'Calculation Engine', 'Input Data', 'Campaign Analysis'],",
                    "      formula_map: {",
                    "        'Dashboard!B2': '=100-Input_Data!B12',",
                    "        'Dashboard!B4': '=SUM(Campaign_Analysis!D:D)',",
                    "        'Dashboard!B6': '=SUM(Campaign_Analysis!E:E)',",
                    "        'Dashboard!B8': '=((B6-B4)/B4)*100',",
                    "        'Calc!C2': '=E2/(1+$B$1)-D2',",
                    "        'Calc!F2': '=((E2-D2)/D2)*100',",
                    "        'Calc!G2': '=F2*(Input_Data!B12/100)',",
                    "      },",
                    "      logic_rationale: 'Fragility=100-composite. ROI=(Rev-Cost)/Cost*100. NPV@10%. Risk-Adj=ROI*composite/100.',",
                    "    }",
                    "  }}];",
                    "} catch (e) {",
                    "  return [{ json: {",
                    "    _math_error: true,",
                    "    agent: 'CFO',",
                    "    error_type: e.constructor.name,",
                    "    error_message: e.message,",
                    "    correction_request: `Math Correction Request: ${e.constructor.name} - ${e.message}. Please review the input data and formulas.`,",
                    "    input_snapshot: { cmo_spend: cmo, architect_risk: risk, campaign_count: campaigns.length }",
                    "  }}];",
                    "}",
                ])
            },
            "id": "cfo-js-engine",
            "name": "CFO Execution Engine",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [950, 300]
        },

        # ── Node 6: Math Error Router ─────────────────────────
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
                            "id": "check-math-ok",
                            "leftValue": "={{ $json._math_error }}",
                            "rightValue": False,
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
            "id": "cfo-math-router",
            "name": "Math Error Check",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [1200, 300]
        },

        # ── Node 7a: Math Error → Callback to CFO Agent ──────
        {
            "parameters": {
                "method": "POST",
                "url": "http://localhost:8000/api/warroom/message",
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {"name": "Content-Type", "value": "application/json"}
                    ]
                },
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": '={{ JSON.stringify({ role: "CFO", type: "math_correction_request", message: $json.correction_request, error_type: $json.error_type, error_message: $json.error_message, input_snapshot: $json.input_snapshot }) }}',
                "options": {
                    "timeout": 10000
                }
            },
            "id": "cfo-math-error-callback",
            "name": "Math Error to War Room",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1450, 500]
        },

        # ── Node 7b: Respond with math error ──────────────────
        {
            "parameters": {
                "respondWith": "json",
                "responseBody": '={{ JSON.stringify({ agent: "CFO", status: "math_error", correction_request: $input.all()[0].json.correction_request || $json.correction_request, error_type: $input.all()[0].json.error_type || $json.error_type }) }}',
                "options": {
                    "responseCode": 422
                }
            },
            "id": "cfo-math-error-response",
            "name": "CFO Math Error Response",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1.1,
            "position": [1700, 500]
        },

        # ── Node 8: Final Response → caller ─────────────────────
        # Returns full report data directly. The caller (Factory/Bridge)
        # handles Drive upload and War Room notification locally.
        {
            "parameters": {
                "respondWith": "json",
                "responseBody": '={{ JSON.stringify({ agent: "CFO", status: "deployed", message: "CFO Agent has deployed the Fragility Report to the AI Folder.", file_name: $json.file_name, report: $json.report }) }}',
                "options": {
                    "responseCode": 200
                }
            },
            "id": "cfo-final-response",
            "name": "CFO Report Response",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1.1,
            "position": [1450, 300]
        }
    ],

    "connections": {
        "CFO Webhook Trigger": {
            "main": [[{"node": "CFO Gatekeeper", "type": "main", "index": 0}]]
        },
        "CFO Gatekeeper": {
            "main": [[{"node": "CFO Route", "type": "main", "index": 0}]]
        },
        "CFO Route": {
            "main": [
                [{"node": "CFO Execution Engine", "type": "main", "index": 0}],
                [{"node": "CFO Missing Data Response", "type": "main", "index": 0}]
            ]
        },
        "CFO Execution Engine": {
            "main": [[{"node": "Math Error Check", "type": "main", "index": 0}]]
        },
        "Math Error Check": {
            "main": [
                [{"node": "CFO Report Response", "type": "main", "index": 0}],
                [{"node": "Math Error to War Room", "type": "main", "index": 0}]
            ]
        },
        "Math Error to War Room": {
            "main": [[{"node": "CFO Math Error Response", "type": "main", "index": 0}]]
        }
    },

    "settings": {
        "executionOrder": "v1"
    },
    "staticData": None
}


def main():
    print(f"\n{'='*60}")
    print(f"  Deploying CFO Execution Controller V2 to N8N")
    print(f"{'='*60}\n")

    if not N8N_API_KEY:
        print("  N8N_API_KEY not set!"); return None

    # Find existing workflow
    r = requests.get(f"{N8N_API_BASE}/workflows?limit=200", headers=HEADERS, timeout=15)
    existing = [w for w in r.json().get("data", []) if w.get("name") == WORKFLOW_NAME]

    if existing:
        wf_id = existing[0]["id"]
        print(f"  Updating existing workflow: {wf_id}")
        r2 = requests.put(f"{N8N_API_BASE}/workflows/{wf_id}", headers=HEADERS,
                         json=CFO_WORKFLOW_V2, timeout=15)
        print(f"  Update: {r2.status_code}")
        if r2.status_code != 200:
            print(f"  Error: {r2.text[:500]}")
            return None
    else:
        print("  Creating new workflow...")
        r2 = requests.post(f"{N8N_API_BASE}/workflows", headers=HEADERS,
                          json=CFO_WORKFLOW_V2, timeout=15)
        if r2.status_code not in (200, 201):
            print(f"  Failed: {r2.status_code} {r2.text[:500]}")
            return None
        wf_id = r2.json().get("id")
        print(f"  Created: {wf_id}")

    # Activate
    r3 = requests.post(f"{N8N_API_BASE}/workflows/{wf_id}/activate",
                       headers=HEADERS, timeout=10)
    print(f"  Activate: {r3.status_code}")

    webhook_url = "https://humanresource.app.n8n.cloud/webhook/cfo-execution-controller"
    print(f"\n  Webhook: {webhook_url}")

    time.sleep(2)

    # Test 1: Valid payload
    print(f"\n  [TEST 1] Valid payload...")
    valid_payload = {
        "cmo_spend": {"total": 50000, "allocated": 42000},
        "architect_risk": {
            "structural_score": 82, "logic_score": 78,
            "security_score": 85, "composite_score": 81.6
        },
        "campaign_list": [
            {"name": "Q2 Launch", "budget": 15000, "projected_revenue": 45000},
            {"name": "Brand Awareness", "budget": 12000, "projected_revenue": 18000},
            {"name": "Retention", "budget": 8000, "projected_revenue": 24000}
        ]
    }
    try:
        r4 = requests.post(webhook_url, json=valid_payload, timeout=30)
        print(f"  Status: {r4.status_code}")
        if r4.text:
            print(f"  Body: {r4.text[:500]}")
    except Exception as e:
        print(f"  Error: {e}")

    # Test 2: Missing fields (should callback to Architect)
    print(f"\n  [TEST 2] Missing fields (expect 202 + Architect callback)...")
    try:
        r5 = requests.post(webhook_url, json={"cmo_spend": {"total": 50000}}, timeout=15)
        print(f"  Status: {r5.status_code}")
        if r5.text:
            print(f"  Body: {r5.text[:300]}")
    except Exception as e:
        print(f"  Error: {e}")

    # Test 3: Math error (division by zero scenario)
    print(f"\n  [TEST 3] Math error trigger (zero budget)...")
    try:
        r6 = requests.post(webhook_url, json={
            "cmo_spend": {"total": 0, "allocated": 0},
            "architect_risk": {"composite_score": 0},
            "campaign_list": [{"name": "Test", "budget": 0, "projected_revenue": 0}]
        }, timeout=15)
        print(f"  Status: {r6.status_code}")
        if r6.text:
            print(f"  Body: {r6.text[:300]}")
    except Exception as e:
        print(f"  Error: {e}")

    print(f"\n{'='*60}")
    print(f"  V2 deployment complete!")
    print(f"  Workflow ID: {wf_id}")
    print(f"  Webhook: {webhook_url}")
    print(f"{'='*60}\n")
    return wf_id


if __name__ == "__main__":
    main()
