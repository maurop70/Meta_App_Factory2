"""
Antigravity N8N Budget Guard — Tracks execution usage and warns before quota exhaustion.
Usage:
    python n8n_budget_guard.py                  # Check current usage
    python n8n_budget_guard.py --limit 10000    # Set monthly limit
    
Designed to be called during preflight or on-demand.
"""
import os, sys, json, time
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUDGET_LOG = os.path.join(SCRIPT_DIR, "Alpha_Data", "n8n_execution_log.json")
N8N_BASE = "https://humanresource.app.n8n.cloud/api/v1"
DEFAULT_MONTHLY_LIMIT = 10000

# V2.0 Vault integration
try:
    sys.path.insert(0, SCRIPT_DIR)
    from vault_client import get_secret as _vault_get
except ImportError:
    _vault_get = None

def _get_api_key():
    """Load N8N_API_KEY from vault, then env, then .env."""
    if _vault_get:
        val = _vault_get("N8N_API_KEY")
        if val:
            return val
    key = os.getenv("N8N_API_KEY")
    if key:
        return key
    env_path = os.path.join(SCRIPT_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if line.strip().startswith("N8N_API_KEY="):
                    return line.strip().split("=", 1)[1]
    return None


def fetch_execution_counts(api_key):
    """Fetch execution counts from N8N API."""
    import requests
    headers = {"X-N8N-API-KEY": api_key}
    results = {}

    try:
        # Get all workflows
        r = requests.get(f"{N8N_BASE}/workflows", headers=headers, timeout=15)
        if r.status_code != 200:
            return None, f"API error: {r.status_code}"

        workflows = r.json().get("data", [])

        # Get recent executions (last 30 days)
        params = {"limit": 250, "status": "all"}
        r2 = requests.get(f"{N8N_BASE}/executions", headers=headers, params=params, timeout=15)

        total = 0
        success = 0
        failed = 0
        by_workflow = {}

        if r2.status_code == 200:
            executions = r2.json().get("data", [])
            total = len(executions)
            for ex in executions:
                wf_name = ex.get("workflowData", {}).get("name", "Unknown")
                status = ex.get("status", "unknown")
                if wf_name not in by_workflow:
                    by_workflow[wf_name] = {"success": 0, "failed": 0, "total": 0}
                by_workflow[wf_name]["total"] += 1
                if status == "success":
                    by_workflow[wf_name]["success"] += 1
                    success += 1
                else:
                    by_workflow[wf_name]["failed"] += 1
                    failed += 1

        return {
            "timestamp": datetime.now().isoformat(),
            "total_executions": total,
            "success": success,
            "failed": failed,
            "failure_rate": round(failed / max(total, 1) * 100, 1),
            "by_workflow": by_workflow,
            "active_workflows": sum(1 for w in workflows if w.get("active")),
            "total_workflows": len(workflows),
        }, None

    except Exception as e:
        return None, str(e)


def load_budget_log():
    """Load the execution budget log."""
    if os.path.exists(BUDGET_LOG):
        try:
            with open(BUDGET_LOG, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"monthly_limit": DEFAULT_MONTHLY_LIMIT, "history": []}


def save_budget_log(log):
    """Save the execution budget log."""
    os.makedirs(os.path.dirname(BUDGET_LOG), exist_ok=True)
    with open(BUDGET_LOG, "w") as f:
        json.dump(log, f, indent=2)


def check_budget(monthly_limit=None):
    """
    Check N8N execution budget. Returns (status, message) where status is:
    'ok' (< 70%), 'warning' (70-90%), 'critical' (> 90%), 'error' (can't check)
    """
    api_key = _get_api_key()
    if not api_key:
        return "error", "N8N_API_KEY not found"

    log = load_budget_log()
    limit = monthly_limit or log.get("monthly_limit", DEFAULT_MONTHLY_LIMIT)

    counts, err = fetch_execution_counts(api_key)
    if err:
        return "error", f"Could not fetch counts: {err}"

    # Save to history
    log["monthly_limit"] = limit
    log["history"].append(counts)
    log["history"] = log["history"][-30:]  # Keep last 30 snapshots
    log["last_check"] = counts["timestamp"]
    save_budget_log(log)

    total = counts["total_executions"]
    pct = round(total / max(limit, 1) * 100, 1)

    if pct >= 90:
        status = "critical"
    elif pct >= 70:
        status = "warning"
    else:
        status = "ok"

    return status, counts


def print_report(status, data):
    """Print a human-readable budget report."""
    if isinstance(data, str):
        print(f"  ❌ Budget Check Error: {data}")
        return

    log = load_budget_log()
    limit = log.get("monthly_limit", DEFAULT_MONTHLY_LIMIT)
    pct = round(data["total_executions"] / max(limit, 1) * 100, 1)

    icons = {"ok": "✅", "warning": "⚠️ ", "critical": "🚨"}
    print(f"\n{'='*55}")
    print(f"  N8N EXECUTION BUDGET REPORT")
    print(f"{'='*55}")
    print(f"  {icons.get(status, '❓')} Status: {status.upper()}")
    print(f"  📊 Executions: {data['total_executions']} / {limit} ({pct}%)")
    print(f"  ✅ Success: {data['success']}  |  ❌ Failed: {data['failed']}  |  📉 Fail Rate: {data['failure_rate']}%")
    print(f"  🔧 Active Workflows: {data['active_workflows']} / {data['total_workflows']}")

    if data["by_workflow"]:
        print(f"\n  Top Workflows:")
        sorted_wf = sorted(data["by_workflow"].items(), key=lambda x: x[1]["total"], reverse=True)
        for name, counts in sorted_wf[:5]:
            print(f"    {name}: {counts['total']} ({counts['failed']} failed)")

    if status == "critical":
        print(f"\n  🚨 CRITICAL: Approaching monthly limit! Consider deactivating unused workflows.")
    elif status == "warning":
        print(f"\n  ⚠️  WARNING: Usage at {pct}% of monthly limit.")

    print(f"{'='*55}\n")


# ── CLI ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="N8N Execution Budget Guard")
    parser.add_argument("--limit", type=int, default=None, help="Monthly execution limit")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
    except ImportError:
        pass

    status, data = check_budget(args.limit)
    print_report(status, data)
    sys.exit(0 if status in ("ok", "warning") else 1)
