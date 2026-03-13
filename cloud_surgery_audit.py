"""n8n Cloud Surgery Diagnostic — Pull error stacks from failed executions."""
import os, sys, json, requests
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

N8N_API_BASE = "https://humanresource.app.n8n.cloud/api/v1"
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
HEADERS = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}

def main():
    print("\n" + "=" * 70)
    print("  AETHER CLOUD SURGERY — n8n Error Stack Audit")
    print("=" * 70 + "\n")

    # 1. Get last 5 failed executions
    r = requests.get(f"{N8N_API_BASE}/executions?status=error&limit=5", headers=HEADERS, timeout=15)
    if r.status_code != 200:
        print(f"API Error: {r.status_code}")
        return
    
    execs = r.json().get("data", [])
    print(f"Found {len(execs)} failed executions\n")

    error_types = {"401_unauthorized": 0, "workflow_operation_error": 0, "trigger_timeout": 0, "other": 0}
    node_errors = []

    for ex in execs:
        eid = ex["id"]
        wfid = ex.get("workflowId", "?")
        started = ex.get("startedAt", "?")
        mode = ex.get("mode", "?")

        # Fetch full execution detail
        r2 = requests.get(f"{N8N_API_BASE}/executions/{eid}", headers=HEADERS, timeout=15)
        if r2.status_code != 200:
            print(f"  Could not fetch execution {eid}: {r2.status_code}")
            continue

        detail = r2.json()
        print(f"{'='*60}")
        print(f"  Execution ID : {eid}")
        print(f"  Workflow ID  : {wfid}")
        print(f"  Mode         : {mode}")
        print(f"  Started      : {started}")

        # Navigate the error structure
        data = detail.get("data", {})
        if not isinstance(data, dict):
            print(f"  Data: {str(data)[:200]}")
            error_types["other"] += 1
            continue

        result_data = data.get("resultData", {})
        
        # Top-level error
        error_obj = result_data.get("error", {})
        if isinstance(error_obj, dict):
            msg = error_obj.get("message", "")
            node_info = error_obj.get("node", {})
            node_name = node_info.get("name", "N/A") if isinstance(node_info, dict) else "N/A"
            node_id = node_info.get("id", "N/A") if isinstance(node_info, dict) else "N/A"
            node_type = node_info.get("type", "N/A") if isinstance(node_info, dict) else "N/A"
            stack = str(error_obj.get("stack", ""))[:300]

            print(f"  Error Message: {msg[:200]}")
            print(f"  Error Node   : {node_name} (ID: {node_id})")
            print(f"  Node Type    : {node_type}")
            print(f"  Stack        : {stack[:200]}")

            # Classify
            msg_lower = msg.lower()
            if "401" in msg or "unauthorized" in msg_lower or "authentication" in msg_lower:
                error_types["401_unauthorized"] += 1
                print(f"  Classification: 🔴 401 UNAUTHORIZED (Token Decay)")
            elif "timeout" in msg_lower or "timed out" in msg_lower or "0.01" in msg:
                error_types["trigger_timeout"] += 1
                print(f"  Classification: 🟡 TRIGGER TIMEOUT")
            elif "workflowoperation" in msg_lower or "process" in msg_lower:
                error_types["workflow_operation_error"] += 1
                print(f"  Classification: 🟡 WORKFLOW OPERATION ERROR")
            else:
                error_types["other"] += 1
                print(f"  Classification: ⚪ OTHER")

            node_errors.append({
                "exec_id": eid,
                "workflow_id": wfid,
                "node_name": node_name,
                "node_id": node_id,
                "node_type": node_type,
                "message": msg[:200],
            })
        elif isinstance(error_obj, str):
            print(f"  Error: {error_obj[:200]}")
            error_types["other"] += 1

        # Also check run data for node-level errors
        run_data = result_data.get("runData", {})
        if isinstance(run_data, dict):
            for nname, nruns in run_data.items():
                if isinstance(nruns, list):
                    for nr in nruns:
                        if nr.get("error"):
                            err = nr["error"]
                            err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                            print(f"  Node Error [{nname}]: {str(err_msg)[:150]}")
        print()

    # Summary
    print("\n" + "=" * 70)
    print("  DIAGNOSIS SUMMARY")
    print("=" * 70)
    print(f"  401 Unauthorized (Token Decay)    : {error_types['401_unauthorized']}")
    print(f"  Workflow Operation Error           : {error_types['workflow_operation_error']}")
    print(f"  Trigger Timeout                    : {error_types['trigger_timeout']}")
    print(f"  Other                              : {error_types['other']}")
    print()

    if node_errors:
        print("  Offending Nodes:")
        for ne in node_errors:
            print(f"    Node: {ne['node_name']} (ID: {ne['node_id']}, Type: {ne['node_type']})")
            print(f"    Error: {ne['message'][:120]}")
            print()

    # Dump full error data
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloud_surgery_audit.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"error_types": error_types, "node_errors": node_errors}, f, indent=2)
    print(f"  Full audit saved to: {output_path}")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
