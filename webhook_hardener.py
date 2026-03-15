"""
webhook_hardener.py — Webhook Optimization (System Hardening V3)
═══════════════════════════════════════════════════════════════════
Iterates through all n8n workflows and updates webhook trigger nodes
to use responseMode: responseNode (respond immediately) to prevent
cloud timeouts on heavy executions.

Usage:
    python webhook_hardener.py           # Dry-run (preview changes)
    python webhook_hardener.py --apply   # Apply changes to n8n Cloud
"""

import os, sys, json, requests, argparse
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

N8N_API_BASE = "https://humanresource.app.n8n.cloud/api/v1"
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
HEADERS = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}

# Webhook node types
WEBHOOK_TYPES = {
    "n8n-nodes-base.webhook",
    "@n8n/n8n-nodes-langchain.chatTrigger",
}

REPORT = {"scanned": 0, "with_webhooks": 0, "updated": 0, "skipped": 0, "errors": 0, "details": []}

# ── Checksum Handshake (Resilience Patch v3.0) ──────────
import hashlib

def compute_payload_hash(payload: dict) -> str:
    """Compute SHA-256 hash of a normalized JSON payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_payload_hash(payload: dict, expected_hash: str) -> dict:
    """
    Verify payload integrity via SHA-256 checksum handshake.
    Used by Specialist - CFO (V2) workflow to guarantee data integrity.

    Returns:
        {"valid": True/False, "computed": str, "expected": str, "action": str}
    """
    computed = compute_payload_hash(payload)
    valid = computed == expected_hash
    return {
        "valid": valid,
        "computed": computed,
        "expected": expected_hash,
        "action": "accepted" if valid else "autonomous_retry",
    }



def fetch_all_workflows():
    """Fetch all workflows from n8n API."""
    r = requests.get(f"{N8N_API_BASE}/workflows?limit=200", headers=HEADERS, timeout=15)
    if r.status_code != 200:
        print(f"❌ Failed to list workflows: {r.status_code}")
        return []
    return r.json().get("data", [])


def get_workflow_detail(wf_id):
    """Fetch full workflow detail including nodes."""
    r = requests.get(f"{N8N_API_BASE}/workflows/{wf_id}", headers=HEADERS, timeout=15)
    if r.status_code != 200:
        return None
    return r.json()


def needs_update(node):
    """Check if a webhook node needs responseMode update."""
    node_type = node.get("type", "")
    if node_type not in WEBHOOK_TYPES:
        return False
    
    params = node.get("parameters", {})
    current_mode = params.get("responseMode", "")
    
    # Already set to respond immediately via response node
    if current_mode == "responseNode":
        return False
    
    return True


def update_workflow(wf_id, wf_detail, apply=False):
    """Update webhook nodes in a workflow to responseMode: responseNode."""
    nodes = wf_detail.get("nodes", [])
    wf_name = wf_detail.get("name", "?")
    modified = False
    
    for node in nodes:
        if not needs_update(node):
            continue
        
        node_name = node.get("name", "?")
        node_id = node.get("id", "?")
        params = node.get("parameters", {})
        old_mode = params.get("responseMode", "lastNode")
        
        detail = {
            "workflow": wf_name,
            "workflow_id": wf_id,
            "node": node_name,
            "node_id": node_id,
            "old_mode": old_mode,
            "new_mode": "responseNode",
        }
        REPORT["details"].append(detail)
        
        print(f"  🔧 [{node_name}] (ID: {node_id}): {old_mode} → responseNode")
        
        params["responseMode"] = "responseNode"
        modified = True
    
    if modified and apply:
        # PUT the updated workflow back — n8n API is strict about allowed fields
        allowed_keys = {"name", "nodes", "connections", "settings", "staticData", "pinData", "tags"}
        update_payload = {k: v for k, v in wf_detail.items() if k in allowed_keys}
        
        r = requests.put(f"{N8N_API_BASE}/workflows/{wf_id}", 
                        headers=HEADERS, json=update_payload, timeout=15)
        if r.status_code in (200, 204):
            print(f"  ✅ Updated successfully")
            REPORT["updated"] += 1
        else:
            print(f"  ❌ Update failed: {r.status_code} — {r.text[:100]}")
            REPORT["errors"] += 1
    elif modified:
        print(f"  ⏸️ DRY RUN — would update (use --apply to commit)")
        REPORT["updated"] += 1
    
    return modified


def main():
    parser = argparse.ArgumentParser(description="Webhook Hardener — System Hardening V3")
    parser.add_argument("--apply", action="store_true", help="Apply changes to n8n Cloud")
    args = parser.parse_args()
    
    mode = "LIVE" if args.apply else "DRY-RUN"
    print(f"\n{'='*60}")
    print(f"  ⚡ WEBHOOK HARDENER — System Hardening V3 ({mode})")
    print(f"{'='*60}\n")
    
    workflows = fetch_all_workflows()
    print(f"Scanning {len(workflows)} workflows...\n")
    
    for wf in workflows:
        wf_id = wf.get("id", "?")
        wf_name = wf.get("name", "?")
        REPORT["scanned"] += 1
        
        detail = get_workflow_detail(wf_id)
        if not detail:
            continue
        
        nodes = detail.get("nodes", [])
        webhook_nodes = [n for n in nodes if n.get("type", "") in WEBHOOK_TYPES]
        
        if not webhook_nodes:
            continue
        
        REPORT["with_webhooks"] += 1
        print(f"📌 {wf_name} ({wf_id}):")
        
        has_updates = False
        for node in webhook_nodes:
            if needs_update(node):
                has_updates = True
        
        if has_updates:
            update_workflow(wf_id, detail, apply=args.apply)
        else:
            already_modes = [n.get("parameters", {}).get("responseMode", "N/A") for n in webhook_nodes]
            print(f"  ✅ Already optimized ({', '.join(already_modes)})")
            REPORT["skipped"] += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Workflows scanned    : {REPORT['scanned']}")
    print(f"  With webhook triggers: {REPORT['with_webhooks']}")
    print(f"  Updated / to update  : {REPORT['updated']}")
    print(f"  Already optimized    : {REPORT['skipped']}")
    print(f"  Errors               : {REPORT['errors']}")
    
    # Save report
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webhook_hardener_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(REPORT, f, indent=2)
    print(f"\n  Report: {report_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
