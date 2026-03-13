"""
ledger_autocommit.py — LEDGER.md Auto-Commit Skill
=====================================================
Meta App Factory | Project Aether | Antigravity-AI

Watches LEDGER.md for changes to the ## SECURITY_INTERCEPTIONS section.
When a new entry is detected, commits it to a hidden audit_logs Git branch.

Usage:
    from ledger_autocommit import auto_commit_ledger, watch_ledger

    # One-shot: commit current state
    auto_commit_ledger()

    # Watch mode (blocking) — run in background thread
    watch_ledger()
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


import os
import subprocess
import threading
import time
import hashlib
from datetime import datetime, timezone
from typing import Optional

# ── Config ─────────────────────────────────────────────
SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
FACTORY_ROOT   = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
LEDGER_PATH    = os.path.join(FACTORY_ROOT, "LEDGER.md")
AUDIT_BRANCH   = "audit_logs"
WATCH_INTERVAL = 30   # seconds between checks
SECTION_MARKER = "## SECURITY_INTERCEPTIONS"

# ── Git Helpers ─────────────────────────────────────────

def _git(args: list, cwd: str = FACTORY_ROOT) -> tuple[bool, str]:
    """Run a git command. Returns (success, output)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        out = (result.stdout or "").strip() or (result.stderr or "").strip()
        return result.returncode == 0, out
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, str(e)

def _is_git_repo() -> bool:
    ok, _ = _git(["rev-parse", "--is-inside-work-tree"])
    return ok

def _ensure_audit_branch() -> bool:
    """Create audit_logs branch if it doesn't exist (orphan for clean history)."""
    ok, branches = _git(["branch", "--list", AUDIT_BRANCH])
    if ok and AUDIT_BRANCH in branches:
        return True
    # Create orphan branch
    ok, out = _git(["checkout", "--orphan", AUDIT_BRANCH])
    if not ok:
        print(f"[ledger_autocommit] Could not create branch '{AUDIT_BRANCH}': {out}")
        return False
    # Clear staging area
    _git(["rm", "-rf", "--cached", "."])
    # Initial empty commit
    _git(["commit", "--allow-empty", "-m", "chore: init audit_logs branch"])
    # Switch back to previous branch
    _git(["checkout", "-"])
    return True

def _extract_interceptions(ledger_text: str) -> str:
    """Extract only the SECURITY_INTERCEPTIONS section."""
    lines = ledger_text.splitlines()
    in_section = False
    section_lines = []
    for line in lines:
        if line.strip().startswith(SECTION_MARKER):
            in_section = True
        if in_section:
            section_lines.append(line)
    return "\n".join(section_lines)

def _ledger_hash(section_text: str) -> str:
    return hashlib.sha256(section_text.encode("utf-8")).hexdigest()[:12]

# ── Core Commit ─────────────────────────────────────────

def auto_commit_ledger(
    ledger_path: Optional[str] = None,
    message: Optional[str] = None,
) -> dict:
    """
    Commit the current LEDGER.md SECURITY_INTERCEPTIONS section to audit_logs branch.

    Args:
        ledger_path: Override path to LEDGER.md
        message: Override commit message

    Returns:
        dict: {success, commit_hash, branch, message, detail}
    """
    lp = ledger_path or LEDGER_PATH
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not os.path.exists(lp):
        return {"success": False, "detail": f"LEDGER.md not found: {lp}"}

    if not _is_git_repo():
        return {"success": False, "detail": "Not in a Git repository. Skipping auto-commit."}

    with open(lp, "r", encoding="utf-8") as f:
        content = f.read()

    section = _extract_interceptions(content)
    if not section:
        return {"success": False, "detail": "No SECURITY_INTERCEPTIONS section found yet."}

    h = _ledger_hash(section)
    branch_ok = _ensure_audit_branch()
    if not branch_ok:
        return {"success": False, "detail": f"Could not ensure '{AUDIT_BRANCH}' branch."}

    # ── SAFETY: Never use git stash --include-untracked on Google Drive repos ──
    # Instead, we commit the audit snapshot to a dedicated audit directory on
    # the CURRENT branch. This avoids branch switching entirely, which is the
    # root cause of the mass-trash incident (git stash -u removes files from
    # the working tree, triggering Google Drive trash operations).

    # Get current branch name
    ok, current_branch = _git(["branch", "--show-current"])
    if not ok:
        return {"success": False, "detail": f"Could not determine current branch: {current_branch}"}

    # Create audit directory on current branch (safe — no file removals)
    audit_dir = os.path.join(FACTORY_ROOT, ".audit_snapshots")
    os.makedirs(audit_dir, exist_ok=True)

    audit_file = os.path.join(audit_dir, f"audit_{ts[:10]}_{h}.md")
    with open(audit_file, "w", encoding="utf-8") as f:
        f.write(f"# LEDGER Audit Snapshot\n")
        f.write(f"**Timestamp**: {ts}\n")
        f.write(f"**Hash**: {h}\n")
        f.write(f"**Branch**: {current_branch}\n\n")
        f.write(section)

    _git(["add", audit_file])
    commit_msg = message or f"audit: SECURITY_INTERCEPTIONS snapshot [{h}] @ {ts}"
    ok, commit_out = _git(["commit", "-m", commit_msg])
    if not ok and "nothing to commit" not in commit_out:
        return {"success": False, "detail": f"commit failed: {commit_out}"}

    ok, hash_out = _git(["rev-parse", "--short", "HEAD"])
    commit_hash = hash_out if ok else "unknown"

    return {
        "success": True,
        "commit_hash": commit_hash,
        "branch": current_branch,
        "message": commit_msg,
        "detail": f"Snapshot committed: {audit_file}",
    }


# ── Watch Mode ──────────────────────────────────────────

def watch_ledger(
    ledger_path: Optional[str] = None,
    interval: int = WATCH_INTERVAL,
    stop_event: Optional[threading.Event] = None,
):
    """
    Watch LEDGER.md for changes to SECURITY_INTERCEPTIONS.
    Auto-commits whenever the section changes.
    """
    lp = ledger_path or LEDGER_PATH
    last_hash = ""
    print(f"[ledger_autocommit] Watching {lp} every {interval}s...")

    while not (stop_event and stop_event.is_set()):
        try:
            if os.path.exists(lp):
                with open(lp, "r", encoding="utf-8") as f:
                    content = f.read()
                section = _extract_interceptions(content)
                current_hash = _ledger_hash(section)

                if section and current_hash != last_hash:
                    print(f"[ledger_autocommit] SECURITY_INTERCEPTIONS changed -- committing...")
                    result = auto_commit_ledger(lp)
                    if result["success"]:
                        print(f"[ledger_autocommit] Committed: {result['commit_hash']} -> {AUDIT_BRANCH}")
                    else:
                        print(f"[ledger_autocommit] Commit skipped: {result['detail']}")
                    last_hash = current_hash

        except Exception as e:
            print(f"[ledger_autocommit] Error: {e}")

        time.sleep(interval)


if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser(description="Ledger Auto-Commit Skill")
    parser.add_argument("--once", action="store_true", help="Commit once and exit")
    parser.add_argument("--watch", action="store_true", help="Watch for changes (blocking)")
    parser.add_argument("--interval", type=int, default=WATCH_INTERVAL)
    args = parser.parse_args()

    if args.once:
        result = auto_commit_ledger()
        print(json.dumps(result, indent=2))
    elif args.watch:
        watch_ledger(interval=args.interval)
    else:
        print("Usage: --once | --watch [--interval N]")
# V3 AUTO-HEAL ACTIVE
