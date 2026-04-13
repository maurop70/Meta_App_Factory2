"""
chaos_test.py — Chaos Engineering: Hybrid LLM Router Verification
===================================================================
Target: CFO Agent (Port 5070)
Objective: Validate the full audit pipeline -> Pydantic -> Fragility Engine ->
           LLM Router -> Circuit Breaker -> Telemetry persistence.

Uses a VALID FinancialPayload per cfo_logic.py schema.
"""

import sys
import os

# Force UTF-8 output on Windows
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import requests
import json

CFO_URL = "http://localhost:5070"
TELEMETRY_URL = f"{CFO_URL}/api/llm/status"
AUDIT_URL = f"{CFO_URL}/api/audit"

# -- Valid FinancialPayload (low fragility -> forces LOCAL classification) --
# This payload produces fragility_index ~25 (below the 30 threshold),
# which means the LLM Router will classify it as "local" and attempt
# Ollama first -- perfect for testing the circuit breaker path.
PAYLOAD = {
    "cmo_spend": {
        "total": 500000,
        "allocated": 420000,
        "categories": {"Digital": 200000, "Events": 120000, "Brand": 100000}
    },
    "architect_risk": {
        "structural_score": 85.0,
        "logic_score": 80.0,
        "security_score": 70.0,
        "composite_score": 75.0
    },
    "campaign_list": [
        {"name": "Q2 Growth Push", "budget": 150000, "projected_revenue": 380000},
        {"name": "Brand Awareness", "budget": 80000, "projected_revenue": 120000}
    ],
    "cash_on_hand": 1200000,
    "mrr": 95000,
    "opex": 45000,
    "liabilities": 200000
}

SEPARATOR = "=" * 60

def main():
    print("")
    print(SEPARATOR)
    print("  CHAOS TEST -- Hybrid LLM Router Verification")
    print(SEPARATOR)
    print("")

    # -- Step 1: Health Check --
    print("[1/4] Health check...")
    try:
        health = requests.get(f"{CFO_URL}/api/health", timeout=5)
        if health.status_code == 200:
            data = health.json()
            print(f"  [OK] CFO Agent ONLINE -- {data.get('agent', '?')} v{data.get('version', '?')}")
        else:
            print(f"  [FAIL] CFO Agent returned {health.status_code}")
            sys.exit(1)
    except requests.ConnectionError:
        print(f"  [FAIL] CFO Agent OFFLINE (port 5070 unreachable)")
        print(f"         Start it with: python Meta_App_Factory/CFO_Agent/server.py")
        sys.exit(1)

    # -- Step 2: Pre-flight Telemetry --
    print("")
    print("[2/4] Pre-flight telemetry...")
    try:
        pre = requests.get(TELEMETRY_URL, timeout=5).json()
        cb = pre.get("circuit_breaker", {})
        print(f"  Circuit Breaker State:   {cb.get('state', 'N/A')}")
        print(f"  Consecutive Failures:    {cb.get('consecutive_failures', 'N/A')}")
        print(f"  Total Requests (before): {pre.get('total_requests', 0)}")
        print(f"  Local Requests:          {pre.get('local_requests', 0)}")
        print(f"  Cloud Requests:          {pre.get('cloud_requests', 0)}")
        print(f"  Fallback Count:          {pre.get('fallback_count', 0)}")
        print(f"  Ollama Reachable:        {pre.get('ollama_reachable', 'N/A')}")
    except Exception as e:
        print(f"  [WARN] Telemetry fetch failed: {e}")

    # -- Step 3: Fire Audit Request --
    print("")
    print("[3/4] Firing audit request...")
    print(f"  Payload fragility target: ~25 (below threshold 30 -> LOCAL classification)")
    print(f"  Endpoint: POST {AUDIT_URL}")
    print("")

    try:
        res = requests.post(
            AUDIT_URL,
            json=PAYLOAD,
            headers={"Content-Type": "application/json"},
            timeout=60  # LLM generation can take time
        )

        if res.status_code == 200:
            data = res.json()
            provider = data.get("llm_provider", "NOT_FOUND_IN_RESPONSE")
            verdict = data.get("verdict", "?")
            score = data.get("score", "?")
            fragility = None

            # Try to extract fragility from findings
            findings = data.get("findings", [])
            for f in findings:
                details = f.get("details", "")
                if "Fragility" in details:
                    fragility = details

            print(f"  [OK] AUDIT RESPONSE RECEIVED")
            print(f"  +---------------------------------------------")
            print(f"  | Verdict:       {verdict}")
            print(f"  | Score:         {score}")
            print(f"  | LLM Provider:  {provider}")
            if fragility:
                print(f"  | Fragility:     {fragility}")
            print(f"  +---------------------------------------------")

            # Print first 200 chars of narrative if present
            narrative = data.get("cfo_analysis", data.get("narrative", ""))
            if narrative and isinstance(narrative, str):
                preview = narrative[:300].replace("\n", " ")
                print(f"")
                print(f"  Narrative preview: \"{preview}...\"")

        elif res.status_code == 400:
            print(f"  [FAIL] Pydantic validation FAILED (400)")
            print(f"         Response: {res.json()}")
        else:
            print(f"  [FAIL] Unexpected status: {res.status_code}")
            print(f"         Response: {res.text[:300]}")

    except requests.Timeout:
        print(f"  [WARN] Request timed out after 60s (LLM may be generating)")
    except Exception as e:
        print(f"  [FAIL] Request failed: {e}")

    # -- Step 4: Post-flight Telemetry --
    print("")
    print("[4/4] Post-flight telemetry...")
    try:
        post = requests.get(TELEMETRY_URL, timeout=5).json()
        cb = post.get("circuit_breaker", {})
        print(f"  Circuit Breaker State:   {cb.get('state', 'N/A')}")
        print(f"  Consecutive Failures:    {cb.get('consecutive_failures', 'N/A')}")
        print(f"  Fail Threshold:          {cb.get('fail_threshold', 'N/A')}")
        print(f"  Last Failure At:         {cb.get('last_failure_at', 'None')}")
        print(f"  Last Recovery At:        {cb.get('last_recovery_at', 'None')}")
        print(f"  Total Requests (after):  {post.get('total_requests', 0)}")
        print(f"  Local Requests:          {post.get('local_requests', 0)}")
        print(f"  Cloud Requests:          {post.get('cloud_requests', 0)}")
        print(f"  Fallback Count:          {post.get('fallback_count', 0)}")
        print(f"  Circuit Trips (total):   {post.get('circuit_breaker_trips', 0)}")
        print(f"  Ollama Reachable:        {post.get('ollama_reachable', 'N/A')}")
        print(f"  Telemetry Persistent:    {post.get('telemetry_persistent', False)}")
        print(f"  Telemetry File:          {post.get('telemetry_file', 'N/A')}")
    except Exception as e:
        print(f"  [WARN] Telemetry fetch failed: {e}")

    print("")
    print(SEPARATOR)
    print("  CHAOS TEST COMPLETE")
    print(SEPARATOR)
    print("")


if __name__ == "__main__":
    main()
