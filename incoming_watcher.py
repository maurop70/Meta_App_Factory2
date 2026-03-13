"""
incoming_watcher.py — Legacy Audit File Watcher (Phase 4)
═══════════════════════════════════════════════════════════
Monitors projects/{name}/incoming/ directories for new files.
When detected, auto-seeds a Boardroom War Room session for audit.

Links audit_incoming() → War Room WebSocket + Socratic Challenger.
"""

import os
import sys
import json
import time
import logging
import hashlib
import asyncio
import requests
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(SCRIPT_DIR, "projects")
WARROOM_API = "http://localhost:8000"

logger = logging.getLogger("incoming_watcher")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [IncomingWatcher] %(message)s"))
    logger.addHandler(handler)

# Track already-processed files
_processed_hashes = set()
_state_file = os.path.join(SCRIPT_DIR, "incoming_watcher_state.json")


def _load_state():
    """Load previously processed file hashes."""
    global _processed_hashes
    try:
        if os.path.exists(_state_file):
            with open(_state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                _processed_hashes = set(data.get("processed", []))
    except Exception:
        _processed_hashes = set()


def _save_state():
    """Persist processed file hashes."""
    try:
        with open(_state_file, "w", encoding="utf-8") as f:
            json.dump({"processed": list(_processed_hashes)}, f)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


def _file_hash(filepath):
    """Generate a hash for a file (path + mtime + size)."""
    stat = os.stat(filepath)
    raw = f"{filepath}:{stat.st_mtime}:{stat.st_size}"
    return hashlib.md5(raw.encode()).hexdigest()


def audit_incoming():
    """
    Scan all projects/{name}/incoming/ directories for new files.
    For each new file detected, auto-seed a War Room boardroom session.

    Returns a list of newly detected files and their audit actions.
    """
    _load_state()
    results = []

    if not os.path.exists(PROJECTS_DIR):
        os.makedirs(PROJECTS_DIR, exist_ok=True)
        logger.info(f"Created projects directory: {PROJECTS_DIR}")
        return results

    for project_name in os.listdir(PROJECTS_DIR):
        project_dir = os.path.join(PROJECTS_DIR, project_name)
        if not os.path.isdir(project_dir):
            continue

        incoming_dir = os.path.join(project_dir, "incoming")
        if not os.path.isdir(incoming_dir):
            continue

        for root, dirs, files in os.walk(incoming_dir):
            for filename in files:
                filepath = os.path.join(root, filename)
                fhash = _file_hash(filepath)

                if fhash in _processed_hashes:
                    continue

                # New file detected
                logger.info(f"📥 New file detected: {filepath}")

                file_info = {
                    "project": project_name,
                    "filename": filename,
                    "filepath": filepath,
                    "size": os.path.getsize(filepath),
                    "detected_at": datetime.now().isoformat(),
                }

                # Auto-seed War Room session
                topic = f"Legacy Audit: {project_name}/{filename} — New file in incoming/"
                try:
                    resp = requests.post(
                        f"{WARROOM_API}/api/warroom/seed",
                        json={"topic": topic},
                        timeout=5,
                    )
                    file_info["warroom_seeded"] = resp.status_code == 200
                    logger.info(f"🏛️ War Room seeded: {topic}")
                except Exception as e:
                    file_info["warroom_seeded"] = False
                    logger.warning(f"Failed to seed War Room: {e}")

                # Auto-trigger Socratic Challenge on the file
                try:
                    challenge_resp = requests.post(
                        f"{WARROOM_API}/api/warroom/challenge",
                        json={
                            "proposal": f"Incoming file audit: {filename} in {project_name}. "
                                        f"File size: {file_info['size']} bytes. "
                                        f"Requires quality validation before integration.",
                            "critic_score": 5.0,  # Start skeptical
                        },
                        timeout=10,
                    )
                    file_info["challenge_issued"] = challenge_resp.status_code == 200
                    if challenge_resp.status_code == 200:
                        cdata = challenge_resp.json()
                        file_info["challenge_id"] = cdata.get("challenge_id")
                except Exception as e:
                    file_info["challenge_issued"] = False
                    logger.warning(f"Failed to issue challenge: {e}")

                _processed_hashes.add(fhash)
                results.append(file_info)

    _save_state()
    return results


def watch_incoming(interval_seconds=30):
    """
    Continuous watcher — polls projects/*/incoming/ at regular intervals.
    Designed to run as a background task in the FastAPI server.
    """
    logger.info(f"🔍 Incoming Watcher started (interval: {interval_seconds}s)")
    logger.info(f"   Monitoring: {PROJECTS_DIR}/*/incoming/")

    while True:
        try:
            new_files = audit_incoming()
            if new_files:
                logger.info(f"📥 Detected {len(new_files)} new file(s)")
                for f in new_files:
                    logger.info(f"   → {f['project']}/{f['filename']} "
                                f"(seeded: {f.get('warroom_seeded')}, "
                                f"challenged: {f.get('challenge_issued')})")
        except Exception as e:
            logger.error(f"Watcher error: {e}")

        time.sleep(interval_seconds)


# ── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Incoming File Watcher — War Room Auto-Seed")
    parser.add_argument("--once", action="store_true", help="Run once then exit")
    parser.add_argument("--interval", type=int, default=30, help="Poll interval in seconds")
    args = parser.parse_args()

    if args.once:
        results = audit_incoming()
        print(f"\n{'='*50}")
        print(f"  📥 Incoming Watcher — Single Scan")
        print(f"{'='*50}")
        print(f"  Projects dir: {PROJECTS_DIR}")
        print(f"  Files detected: {len(results)}")
        for r in results:
            print(f"  → {r['project']}/{r['filename']} ({r['size']} bytes)")
            print(f"    War Room: {'✅' if r.get('warroom_seeded') else '❌'}")
            print(f"    Challenge: {'✅' if r.get('challenge_issued') else '❌'}")
        print(f"{'='*50}\n")
    else:
        watch_incoming(args.interval)
