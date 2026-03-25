"""
Antigravity Config Snapshot — Auto-versioned config backup before mutations.
Usage:
    from config_snapshot import snapshot_before_mutation
    snapshot_before_mutation("server.py", "Updating ngrok URL")
    
    # Restore from snapshot
    python config_snapshot.py --restore server.py
    python config_snapshot.py --list           # List all snapshots
"""
# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

from auto_heal import healed_post, auto_heal, diagnose

def _v3_preflight():
    """V3: Ping Resonance_Watchdog_V3 before execution."""
    if not _V3_AVAILABLE:
        return True
    try:
        import json as _j
        _cfg_path = _os.path.join(_FACTORY_DIR, "resilience_config.json")
        if not _os.path.exists(_cfg_path):
            return True
        with open(_cfg_path) as _f:
            _cfg = _j.load(_f)
        _url = _cfg.get("cloud_health", {}).get("watchdog_url", "")
        if not _url:
            return True
        import requests as _rq
        _r = _rq.get(_url, timeout=5)
        return _r.status_code == 200
    except Exception:
        return False


import os, sys, json, shutil
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RUNTIME_DIR = os.environ.get('ALPHA_RUNTIME_DIR', os.path.join(SCRIPT_DIR, 'Alpha_Data'))
SNAPSHOT_DIR = os.path.join(RUNTIME_DIR, ".config_snapshots")
MANIFEST_PATH = os.path.join(SNAPSHOT_DIR, "manifest.json")
MAX_SNAPSHOTS_PER_FILE = 10  # Keep last N snapshots per file


def _load_manifest():
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"snapshots": []}


def _save_manifest(manifest):
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def snapshot_before_mutation(file_path, reason="auto", app_name="Unknown"):
    """
    Create a snapshot of a file before it's modified.
    Call this BEFORE any config/workflow mutation.
    Returns the snapshot path or None on failure.
    """
    if not os.path.exists(file_path):
        return None

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    basename = os.path.basename(file_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_name = f"{basename}.{timestamp}.bak"
    snapshot_path = os.path.join(SNAPSHOT_DIR, snapshot_name)

    try:
        shutil.copy2(file_path, snapshot_path)
    except Exception as e:
        print(f"  ⚠️  Snapshot failed for {basename}: {e}")
        return None

    # Update manifest
    manifest = _load_manifest()
    entry = {
        "file": basename,
        "original_path": os.path.abspath(file_path),
        "snapshot_name": snapshot_name,
        "snapshot_path": snapshot_path,
        "timestamp": datetime.now().isoformat(),
        "reason": reason,
        "app": app_name,
        "size_bytes": os.path.getsize(file_path),
    }
    manifest["snapshots"].append(entry)

    # Prune old snapshots for this file
    file_snapshots = [s for s in manifest["snapshots"] if s["file"] == basename]
    if len(file_snapshots) > MAX_SNAPSHOTS_PER_FILE:
        to_remove = file_snapshots[:-MAX_SNAPSHOTS_PER_FILE]
        for old in to_remove:
            try:
                if os.path.exists(old["snapshot_path"]):
                    os.remove(old["snapshot_path"])
            except Exception:
                pass
            manifest["snapshots"].remove(old)

    _save_manifest(manifest)
    print(f"  📸 Snapshot: {basename} ({reason})")
    return snapshot_path


def restore_snapshot(file_basename, snapshot_index=-1):
    """
    Restore a file from a snapshot.
    snapshot_index: -1 for most recent, or specific index from list.
    """
    manifest = _load_manifest()
    file_snapshots = [s for s in manifest["snapshots"] if s["file"] == file_basename]

    if not file_snapshots:
        print(f"  ❌ No snapshots found for {file_basename}")
        return False

    try:
        snap = file_snapshots[snapshot_index]
    except IndexError:
        print(f"  ❌ Snapshot index {snapshot_index} out of range")
        return False

    if not os.path.exists(snap["snapshot_path"]):
        print(f"  ❌ Snapshot file missing: {snap['snapshot_path']}")
        return False

    # Create a snapshot of the CURRENT state before restoring
    snapshot_before_mutation(snap["original_path"], reason="pre-restore backup", app_name="ConfigSnapshot")

    try:
        shutil.copy2(snap["snapshot_path"], snap["original_path"])
        print(f"  ✅ Restored {file_basename} from {snap['timestamp']} ({snap['reason']})")
        return True
    except Exception as e:
        print(f"  ❌ Restore failed: {e}")
        return False


def list_snapshots(file_filter=None):
    """List all available snapshots."""
    manifest = _load_manifest()
    snapshots = manifest.get("snapshots", [])

    if file_filter:
        snapshots = [s for s in snapshots if s["file"] == file_filter]

    return snapshots


# ── CLI ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Antigravity Config Snapshot Manager")
    parser.add_argument("--list", action="store_true", help="List all snapshots")
    parser.add_argument("--restore", type=str, help="Restore a file from its most recent snapshot")
    parser.add_argument("--file", type=str, help="Filter by filename")
    args = parser.parse_args()

    print(f"\n{'='*55}")
    print(f"  CONFIG SNAPSHOT MANAGER")
    print(f"{'='*55}\n")

    if args.restore:
        restore_snapshot(args.restore)
    else:
        snapshots = list_snapshots(args.file)
        if not snapshots:
            print("  No snapshots yet. They're created automatically before config mutations.")
        else:
            for i, s in enumerate(snapshots):
                ts = s["timestamp"][:19]
                size = s.get("size_bytes", 0)
                print(f"  [{i}] {s['file']} — {ts} ({s['reason']}) [{size:,} bytes]")

    print(f"\n{'='*55}\n")
# V3 AUTO-HEAL ACTIVE
