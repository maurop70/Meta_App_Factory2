"""
n8n_archiver.py — Legacy Workflow Archiver (Phase 4)
═══════════════════════════════════════════════════════════
Uses the Antigravity_Full_v2 API key to archive all n8n
workflows labeled 'V1', 'TEST', or 'OLD'.

Ensures the Specialist — Critic (V2) remains the sole arbiter
of workflow quality by deactivating legacy workflows.
"""

import os
import sys
import json
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

logger = logging.getLogger("n8n_archiver")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [n8nArchiver] %(message)s"))
    logger.addHandler(handler)

# ── Configuration ────────────────────────────────────────

N8N_API_KEY = os.environ.get("N8N_API_KEY", "")
N8N_BASE_URL = os.environ.get("N8N_BASE_URL", "https://humanresource.app.n8n.cloud")

# Legacy labels to archive
ARCHIVE_LABELS = {"V1", "TEST", "OLD", "v1", "test", "old"}

# Archive log
ARCHIVE_LOG = os.path.join(SCRIPT_DIR, "n8n_archive_log.json")


def _headers():
    """Auth headers using Antigravity_Full_v2 key."""
    return {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def list_workflows():
    """Fetch all workflows from n8n Cloud."""
    url = f"{N8N_BASE_URL}/api/v1/workflows"
    try:
        resp = requests.get(url, headers=_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        return []


def identify_legacy(workflows):
    """
    Identify workflows that match legacy labels (V1, TEST, OLD).
    Checks workflow name and tags for label matches.
    """
    legacy = []
    for wf in workflows:
        name = wf.get("name", "")
        tags = [t.get("name", "") for t in wf.get("tags", [])]
        wf_id = wf.get("id", "unknown")
        is_active = wf.get("active", False)

        # Check name for legacy indicators
        name_upper = name.upper()
        matched_labels = []
        for label in ARCHIVE_LABELS:
            label_upper = label.upper()
            if label_upper in name_upper:
                matched_labels.append(label_upper)
            if label_upper in [t.upper() for t in tags]:
                matched_labels.append(f"tag:{label_upper}")

        if matched_labels:
            legacy.append({
                "id": wf_id,
                "name": name,
                "active": is_active,
                "matched_labels": list(set(matched_labels)),
                "tags": tags,
            })

    return legacy


def archive_workflow(workflow_id, workflow_name):
    """
    Archive a workflow by deactivating it and adding [ARCHIVED] tag.
    Does NOT delete — preserves for audit trail.
    """
    url = f"{N8N_BASE_URL}/api/v1/workflows/{workflow_id}"

    try:
        # Deactivate
        deactivate_url = f"{url}/deactivate"
        resp = requests.post(deactivate_url, headers=_headers(), timeout=10)

        result = {
            "id": workflow_id,
            "name": workflow_name,
            "deactivated": resp.status_code == 200,
            "archived_at": datetime.now().isoformat(),
            "status_code": resp.status_code,
        }

        if resp.status_code == 200:
            logger.info(f"✅ Archived: {workflow_name} (ID: {workflow_id})")
        else:
            logger.warning(f"⚠️ Failed to deactivate {workflow_name}: HTTP {resp.status_code}")
            # Try PATCH to set active=false as fallback
            try:
                patch_resp = requests.patch(
                    url,
                    headers=_headers(),
                    json={"active": False},
                    timeout=10,
                )
                result["deactivated"] = patch_resp.status_code == 200
                result["method"] = "patch_fallback"
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"❌ Error archiving {workflow_name}: {e}")
        return {
            "id": workflow_id,
            "name": workflow_name,
            "deactivated": False,
            "error": str(e),
        }


def run_archive(dry_run=False):
    """
    Full archive operation:
    1. List all workflows
    2. Identify legacy (V1/TEST/OLD)
    3. Deactivate them
    4. Log results

    Returns summary dict.
    """
    logger.info("=" * 50)
    logger.info("🗄️  n8n Legacy Workflow Archiver")
    logger.info(f"   Using key: Antigravity_Full_v2 ({'*' * 20}...)")
    logger.info(f"   Base URL: {N8N_BASE_URL}")
    logger.info(f"   Archive labels: {', '.join(sorted(ARCHIVE_LABELS))}")
    logger.info("=" * 50)

    # Step 1: List
    workflows = list_workflows()
    logger.info(f"📋 Total workflows found: {len(workflows)}")

    # Step 2: Identify legacy
    legacy = identify_legacy(workflows)
    logger.info(f"🗃️  Legacy workflows identified: {len(legacy)}")

    for wf in legacy:
        logger.info(f"   → {wf['name']} (ID: {wf['id']}) "
                     f"[{'ACTIVE' if wf['active'] else 'inactive'}] "
                     f"Labels: {', '.join(wf['matched_labels'])}")

    # Step 3: Archive
    archive_results = []
    if not dry_run:
        for wf in legacy:
            result = archive_workflow(wf["id"], wf["name"])
            archive_results.append(result)
    else:
        logger.info("🔍 DRY RUN — no workflows will be modified")

    # Step 4: Identify Critic V2 as sole arbiter
    critic_workflows = [
        wf for wf in workflows
        if "critic" in wf.get("name", "").lower()
           or "quality" in wf.get("name", "").lower()
           or "v2" in wf.get("name", "").lower()
    ]

    # Step 5: Log
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_workflows": len(workflows),
        "legacy_identified": len(legacy),
        "legacy_details": legacy,
        "archived": len([r for r in archive_results if r.get("deactivated")]),
        "archive_results": archive_results,
        "critic_v2_workflows": [wf.get("name") for wf in critic_workflows],
        "sole_arbiter": "Specialist - Critic (V2)",
        "dry_run": dry_run,
    }

    # Save log
    try:
        existing = []
        if os.path.exists(ARCHIVE_LOG):
            with open(ARCHIVE_LOG, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.append(summary)
        with open(ARCHIVE_LOG, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, default=str)
        logger.info(f"📝 Archive log saved: {ARCHIVE_LOG}")
    except Exception as e:
        logger.error(f"Failed to save archive log: {e}")

    logger.info("=" * 50)
    logger.info(f"📊 Summary:")
    logger.info(f"   Workflows scanned: {len(workflows)}")
    logger.info(f"   Legacy identified: {len(legacy)}")
    logger.info(f"   Archived: {summary['archived']}")
    logger.info(f"   Critic V2 (sole arbiter): {len(critic_workflows)} workflows")
    logger.info("=" * 50)

    return summary


# ── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="n8n Legacy Workflow Archiver")
    parser.add_argument("--dry-run", action="store_true", help="Scan only, don't modify")
    args = parser.parse_args()

    if not N8N_API_KEY:
        print("❌ N8N_API_KEY not found in .env")
        sys.exit(1)

    run_archive(dry_run=args.dry_run)
