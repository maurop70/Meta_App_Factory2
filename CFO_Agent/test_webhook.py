"""Full V2 test suite for CFO Execution Controller"""
import requests, json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

URL = "https://humanresource.app.n8n.cloud/webhook/cfo-execution-controller"

# Test 1: Valid payload — full pipeline
print("=" * 60)
print("TEST 1: Valid payload (full pipeline)")
print("=" * 60)
r = requests.post(URL, json={
    "cmo_spend": {"total": 50000, "allocated": 42000},
    "architect_risk": {"structural_score": 82, "logic_score": 78, "security_score": 85, "composite_score": 81.6},
    "campaign_list": [
        {"name": "Q2 Product Launch", "budget": 15000, "projected_revenue": 45000},
        {"name": "Brand Awareness", "budget": 12000, "projected_revenue": 18000},
        {"name": "Retention Program", "budget": 8000, "projected_revenue": 24000}
    ]
}, timeout=30)
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:600]}")

# Test 2: Missing fields — should callback to Master Architect
print(f"\n{'=' * 60}")
print("TEST 2: Missing fields (Architect callback)")
print("=" * 60)
r2 = requests.post(URL, json={"cmo_spend": {"total": 50000}}, timeout=15)
print(f"Status: {r2.status_code}")
print(f"Body: {r2.text[:400]}")

# Test 3: Zero values — should NOT crash (guarded div by zero)
print(f"\n{'=' * 60}")
print("TEST 3: Zero budget (math safety)")
print("=" * 60)
r3 = requests.post(URL, json={
    "cmo_spend": {"total": 0, "allocated": 0},
    "architect_risk": {"composite_score": 0},
    "campaign_list": [{"name": "Edge Case", "budget": 0, "projected_revenue": 0}]
}, timeout=15)
print(f"Status: {r3.status_code}")
print(f"Body: {r3.text[:400]}")
