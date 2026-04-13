"""
cmo_live_fire.py — CMO Agent V3 Live Fire Test
================================================================
Target: CMO Agent (Port 5020)
Objective: Verify brand-studio endpoint, Creative Complexity
           routing, and telemetry persistence.
"""

import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import requests
import json

CMO_URL = "http://localhost:5020"
SEPARATOR = "=" * 60

BRAND_STUDIO_PAYLOAD = {
    "task": "gtm_playbook",
    "brand_name": "Antigravity",
    "description": "Autonomous AI Agent Factory",
    "target_audience": "Enterprise CIOs"
}

def main():
    print("")
    print(SEPARATOR)
    print("  CMO LIVE FIRE -- V3 Architecture Verification")
    print(SEPARATOR)
    print("")

    # -- Step 1: Health Check --
    print("[1/4] Health check...")
    try:
        health = requests.get(f"{CMO_URL}/api/health", timeout=5)
        if health.status_code == 200:
            data = health.json()
            print(f"  [OK] CMO Agent ONLINE -- {data.get('agent', '?')} v{data.get('version', '?')}")
            print(f"       Persona: {data.get('persona', '?')}")
            print(f"       Endpoints: {len(data.get('endpoints', []))} registered")
        else:
            print(f"  [FAIL] CMO Agent returned {health.status_code}")
            sys.exit(1)
    except requests.ConnectionError:
        print(f"  [FAIL] CMO Agent OFFLINE (port 5020 unreachable)")
        print(f"         Start it with: python CMO_Agent/server.py")
        sys.exit(1)

    # -- Step 2: Pre-flight Telemetry --
    print("")
    print("[2/4] Pre-flight telemetry...")
    try:
        pre = requests.get(f"{CMO_URL}/api/llm/status", timeout=5).json()
        cb = pre.get("circuit_breaker", {})
        print(f"  Circuit Breaker State:   {cb.get('state', 'N/A')}")
        print(f"  Total Requests (before): {pre.get('total_requests', 0)}")
        print(f"  Local Requests:          {pre.get('local_requests', 0)}")
        print(f"  Cloud Requests:          {pre.get('cloud_requests', 0)}")
        print(f"  Fallback Count:          {pre.get('fallback_count', 0)}")
        print(f"  Ollama Reachable:        {pre.get('ollama_reachable', 'N/A')}")
        print(f"  Local Tasks:             {pre.get('local_task_types', [])}")
        print(f"  Cloud Tasks:             {pre.get('cloud_task_types', [])}")
    except Exception as e:
        print(f"  [WARN] Telemetry fetch failed: {e}")

    # -- Step 3: Fire Brand Studio Request --
    print("")
    print("[3/4] Firing brand-studio request...")
    print(f"  Task: gtm_playbook (HIGH complexity -> CLOUD classification)")
    print(f"  Brand: Antigravity | Audience: Enterprise CIOs")
    print(f"  Endpoint: POST {CMO_URL}/api/brand-studio")
    print("")

    try:
        res = requests.post(
            f"{CMO_URL}/api/brand-studio",
            json=BRAND_STUDIO_PAYLOAD,
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        if res.status_code == 200:
            data = res.json()
            provider = data.get("llm_provider", "NOT_FOUND")
            task = data.get("task", "?")
            brand = data.get("brand_name", "?")
            narrative = data.get("narrative", "")

            print(f"  [OK] BRAND STUDIO RESPONSE RECEIVED")
            print(f"  +---------------------------------------------")
            print(f"  | Task:          {task}")
            print(f"  | Brand:         {brand}")
            print(f"  | LLM Provider:  {provider}")
            print(f"  | Narrative Len: {len(narrative)} chars")
            print(f"  +---------------------------------------------")

            if narrative and isinstance(narrative, str):
                preview = narrative[:400].replace("\n", " ")
                print(f"")
                print(f"  Narrative preview:")
                print(f"  \"{preview}...\"")
        elif res.status_code == 422:
            print(f"  [FAIL] Pydantic validation error (422)")
            print(f"         {json.dumps(res.json(), indent=2)[:500]}")
        else:
            print(f"  [FAIL] Unexpected status: {res.status_code}")
            print(f"         {res.text[:300]}")

    except requests.Timeout:
        print(f"  [WARN] Request timed out after 60s")
    except Exception as e:
        print(f"  [FAIL] Request failed: {e}")

    # -- Step 4: Post-flight Telemetry --
    print("")
    print("[4/4] Post-flight telemetry...")
    try:
        post = requests.get(f"{CMO_URL}/api/llm/status", timeout=5).json()
        cb = post.get("circuit_breaker", {})
        print(f"  Circuit Breaker State:   {cb.get('state', 'N/A')}")
        print(f"  Consecutive Failures:    {cb.get('consecutive_failures', 'N/A')}")
        print(f"  Total Requests (after):  {post.get('total_requests', 0)}")
        print(f"  Local Requests:          {post.get('local_requests', 0)}")
        print(f"  Cloud Requests:          {post.get('cloud_requests', 0)}")
        print(f"  Fallback Count:          {post.get('fallback_count', 0)}")
        print(f"  Circuit Trips (total):   {post.get('circuit_breaker_trips', 0)}")
        print(f"  Avg Cloud Latency:       {post.get('avg_cloud_latency_ms', 0)}ms")
        print(f"  Telemetry Persistent:    {post.get('telemetry_persistent', False)}")
        print(f"  Telemetry File:          {post.get('telemetry_file', 'N/A')}")
    except Exception as e:
        print(f"  [WARN] Telemetry fetch failed: {e}")

    print("")
    print(SEPARATOR)
    print("  CMO LIVE FIRE COMPLETE")
    print(SEPARATOR)
    print("")


if __name__ == "__main__":
    main()
