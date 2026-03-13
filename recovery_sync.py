"""
recovery_sync.py — Local-to-Cloud Recovery Sync Engine
═══════════════════════════════════════════════════════
Reads buffered/pending payloads from local_pending_sync.json,
validates cloud health via Resonance_Watchdog_V3, retransmits
payloads to their original n8n target URLs, and archives
successful syncs.

Usage:
    python recovery_sync.py              # Sync pending entries (requires healthy watchdog)
    python recovery_sync.py --force      # Force sync even if watchdog is unhealthy
    python recovery_sync.py --status     # Show buffer status only

Part of System Hardening V3.0 — Recovery Suite.
"""

import os
import sys
import json
import time
import glob
import shutil
import argparse
import requests
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Paths
STATE_FILE = os.path.join(SCRIPT_DIR, "local_pending_sync.json")
ARCHIVE_FILE = os.path.join(SCRIPT_DIR, "synced_archive.json")
PENDING_DIR = os.path.join(SCRIPT_DIR, "pending_sync")
RESILIENCE_CFG = os.path.join(SCRIPT_DIR, "resilience_config.json")

# Load env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(SCRIPT_DIR, ".env"), override=True)
except ImportError:
    pass

N8N_API_KEY = os.getenv("N8N_API_KEY", "")


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def load_config() -> dict:
    """Load resilience config for watchdog URL."""
    if os.path.exists(RESILIENCE_CFG):
        with open(RESILIENCE_CFG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_state() -> dict:
    """Load the local pending sync state."""
    if not os.path.exists(STATE_FILE):
        return {"entries": [], "pending_count": 0, "safe_buffer_mode": False}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"entries": [], "pending_count": 0, "safe_buffer_mode": False}


def save_state(state: dict):
    """Write state back to disk."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)


def load_archive() -> list:
    """Load the synced archive."""
    if not os.path.exists(ARCHIVE_FILE):
        return []
    try:
        with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_archive(archive: list):
    """Write archive to disk."""
    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(archive, f, indent=2, default=str)


def ping_watchdog() -> tuple:
    """Ping the Resonance_Watchdog_V3 and return (healthy: bool, latency_ms: float)."""
    cfg = load_config()
    url = cfg.get("cloud_health", {}).get("watchdog_url", "")
    if not url:
        return False, 0.0

    try:
        start = time.time()
        r = requests.get(url, timeout=5)
        ms = (time.time() - start) * 1000
        return r.status_code == 200, ms
    except Exception:
        return False, 0.0


def collect_pending() -> list:
    """Collect all recoverable payloads from state file + pending_sync/ directory."""
    items = []

    # 1. From local_pending_sync.json entries
    state = load_state()
    for entry in state.get("entries", []):
        if entry.get("status") in ("pending", "failed", "buffered"):
            items.append({
                "source": "state",
                "id": entry.get("id", "?"),
                "url": entry.get("url", ""),
                "project": entry.get("project", "?"),
                "timestamp": entry.get("timestamp", "?"),
                "entry": entry,
            })

    # 2. From pending_sync/ directory (queued files)
    if os.path.exists(PENDING_DIR):
        for fpath in sorted(glob.glob(os.path.join(PENDING_DIR, "*.json"))):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items.append({
                    "source": "file",
                    "id": os.path.basename(fpath),
                    "url": data.get("url", ""),
                    "payload": data.get("payload", {}),
                    "project": data.get("project", "?"),
                    "timestamp": data.get("queued_at", "?"),
                    "filepath": fpath,
                })
            except Exception:
                continue

    return items


def transmit_payload(url: str, payload: dict) -> tuple:
    """POST a payload to its target URL. Returns (success: bool, status_code: int, latency_ms: float)."""
    headers = {"Content-Type": "application/json"}
    if N8N_API_KEY:
        headers["X-N8N-API-KEY"] = N8N_API_KEY

    try:
        start = time.time()
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        ms = (time.time() - start) * 1000
        return r.status_code == 200, r.status_code, ms
    except Exception as e:
        return False, 0, 0.0


def archive_entry(entry: dict, status_code: int, latency_ms: float):
    """Move a synced entry to synced_archive.json."""
    archive = load_archive()
    archive.append({
        "id": entry.get("id", "?"),
        "url": entry.get("url", ""),
        "project": entry.get("project", "?"),
        "original_timestamp": entry.get("timestamp", "?"),
        "synced_at": datetime.now().isoformat(),
        "response_code": status_code,
        "latency_ms": latency_ms,
        "status": "synced",
    })
    save_archive(archive)


def run_sync(force: bool = False):
    """Main sync execution."""
    print(f"\n{'='*60}")
    print(f"  Recovery Sync Engine — V3.0")
    print(f"  {timestamp()}")
    print(f"{'='*60}\n")

    # Step 1: Ping watchdog
    healthy, wdog_ms = ping_watchdog()
    icon = "🟢" if healthy else "🔴"
    print(f"  Watchdog:  {icon} {'HEALTHY' if healthy else 'UNHEALTHY'} ({wdog_ms:.0f}ms)")

    if not healthy and not force:
        print(f"\n  ❌ Cloud is unhealthy. Use --force to sync anyway.")
        print(f"{'='*60}\n")
        return {"synced": 0, "failed": 0, "buffer_size": len(collect_pending())}

    if not healthy and force:
        print(f"  ⚠️ Forcing sync despite unhealthy watchdog...")

    # Step 2: Collect pending items
    pending = collect_pending()
    print(f"  Buffer:    📦 {len(pending)} items\n")

    if not pending:
        print(f"  ✅ Buffer is empty — nothing to sync.")
        # Disable Safe-Buffer mode if it was on
        try:
            from local_state_manager import StateManager
            sm = StateManager()
            if sm.is_safe_buffer_mode():
                sm.set_safe_buffer_mode(False)
                print(f"  ✅ Safe-Buffer mode disabled (cloud recovered)")
        except ImportError:
            pass
        print(f"{'='*60}\n")
        return {"synced": 0, "failed": 0, "buffer_size": 0}

    # Step 3: Transmit each payload
    synced = 0
    failed = 0
    state = load_state()

    for item in pending:
        source = item["source"]
        project = item.get("project", "?")
        url = item.get("url", "")

        if not url:
            print(f"  ⏭️ [{project}] No URL — skipping")
            continue

        # Get payload
        if source == "file":
            payload = item.get("payload", {})
        else:
            # State entries don't store payloads (only hashes) — skip
            print(f"  ⏭️ [{project}] State entry (no payload stored) — marking synced")
            for e in state.get("entries", []):
                if e.get("id") == item["id"]:
                    e["status"] = "synced"
                    e["synced_at"] = datetime.now().isoformat()
            synced += 1
            continue

        print(f"  📤 [{project}] → {url[:60]}...", end=" ", flush=True)
        success, code, ms = transmit_payload(url, payload)

        if success:
            print(f"✅ {code} ({ms:.0f}ms)")
            synced += 1
            archive_entry(item, code, ms)

            # Remove the pending_sync file
            if "filepath" in item and os.path.exists(item["filepath"]):
                os.remove(item["filepath"])
        else:
            print(f"❌ {code}")
            failed += 1

    # Step 4: Update state
    state["pending_count"] = sum(
        1 for e in state.get("entries", []) if e.get("status") in ("pending", "failed", "buffered")
    )
    save_state(state)

    # Disable Safe-Buffer if everything synced
    if failed == 0 and healthy:
        try:
            from local_state_manager import StateManager
            sm = StateManager()
            if sm.is_safe_buffer_mode():
                sm.set_safe_buffer_mode(False)
                print(f"\n  ✅ Safe-Buffer mode disabled (all synced)")
        except ImportError:
            pass

    # Summary
    remaining = len(collect_pending())
    print(f"\n{'='*60}")
    print(f"  RECOVERY SYNC SUMMARY")
    print(f"{'='*60}")
    print(f"  Total Synced:      {synced}")
    print(f"  Failed Retries:    {failed}")
    print(f"  Current Buffer:    {remaining} items remaining")
    print(f"{'='*60}\n")

    return {"synced": synced, "failed": failed, "buffer_size": remaining}


def show_status():
    """Display current buffer status without syncing."""
    print(f"\n{'='*60}")
    print(f"  Recovery Sync — Buffer Status")
    print(f"{'='*60}\n")

    pending = collect_pending()
    state = load_state()
    archive = load_archive()

    healthy, wdog_ms = ping_watchdog()
    safe_buffer = state.get("safe_buffer_mode", False)

    print(f"  Watchdog:        {'🟢' if healthy else '🔴'} {'HEALTHY' if healthy else 'UNHEALTHY'} ({wdog_ms:.0f}ms)")
    print(f"  Safe-Buffer:     {'🛡️ ACTIVE' if safe_buffer else '✅ OFF'}")
    print(f"  Pending:         {len(pending)} items")
    print(f"  Archived:        {len(archive)} items")

    if pending:
        print(f"\n  Pending items:")
        for p in pending:
            print(f"    [{p['source']}] {p['project']} @ {p['timestamp']} → {p['url'][:50]}")

    print(f"\n{'='*60}\n")


# ── Entry Point ─────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recovery Sync Engine — V3.0")
    parser.add_argument("--force", action="store_true",
                        help="Force sync even if watchdog is unhealthy")
    parser.add_argument("--status", action="store_true",
                        help="Show buffer status without syncing")
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        run_sync(force=args.force)
