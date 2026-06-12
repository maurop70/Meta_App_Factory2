"""
Git Wire — Phase 2 ClaudeAY Autonomy
--------------------------------------
Wraps common git operations with the same safety model as shell_wire.py.
Three Gemini architectural patches included from the start:

  Patch 1 — Bypass closed: shell_wire blocks raw "git" commands,
             forcing all git work through this module.
  Patch 2 — Concurrency lock: per-repo asyncio.Lock prevents two
             autonomous tasks from mutating the same repo simultaneously.
  Patch 3 — Network I/O dampening: push/pull failures caused by
             DNS/connection errors return exit_code 502 (not -1 or 128)
             so the caller can distinguish "blocked" from "unreachable".

Served on both planes:
  - MCP plane  : git_operation tool in mcp_server/server.py
                 (calls execute_async directly — lock is effective)
  - Gemini plane: git_operation() in ay_client.py
                 (calls execute() sync wrapper via asyncio.run())
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# CWD sandbox enforcement — single source of truth in shell_wire
from shell_wire import _check_cwd_sandbox

log = logging.getLogger("GitWire")

MAF_ROOT  = Path(__file__).parent.parent.resolve()
AUDIT_LOG = Path(__file__).parent / "logs" / "git_wire_audit.jsonl"
TIMEOUT   = 60  # seconds — generous for push/pull on slow links

PROTECTED_BRANCHES: set[str] = {"prod", "production"}

# Substrings that identify a network-layer failure in git's stderr
_NETWORK_ERRORS: tuple[str, ...] = (
    "could not resolve host",
    "connection refused",
    "timed out",
    "network unreachable",
    "no route to host",
    "failed to connect",
    "ssl connection error",
    "unable to connect to",
    "repository not found",   # DNS resolves but auth fails → also unreachable for our purposes
)


# ── Patch 2 — Per-repo asyncio concurrency lock ───────────────────────────────
# Keyed by the resolved cwd string. Prevents two MCP tool calls from running
# simultaneous git subprocesses against the same repository.

_REPO_LOCKS: dict[str, asyncio.Lock] = {}


def _get_repo_lock(cwd: str) -> asyncio.Lock:
    if cwd not in _REPO_LOCKS:
        _REPO_LOCKS[cwd] = asyncio.Lock()
    return _REPO_LOCKS[cwd]


# ── Audit ─────────────────────────────────────────────────────────────────────

def _audit(entry: dict) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Result factories ──────────────────────────────────────────────────────────

def _blocked(operation: str, cwd: Path, reason: str) -> dict:
    return {
        "stdout":       "",
        "stderr":       "",
        "exit_code":    -1,
        "duration_ms":  0,
        "timed_out":    False,
        "blocked":      True,
        "block_reason": reason,
        "operation":    operation,
        "cwd_used":     str(cwd),
    }


def _gateway_error(operation: str, cwd: Path, message: str, duration_ms: int) -> dict:
    """Patch 3 — network failure mapped to 502."""
    return {
        "stdout":       "",
        "stderr":       f"Gateway Unreachable: {message}",
        "exit_code":    502,
        "duration_ms":  duration_ms,
        "timed_out":    False,
        "blocked":      False,
        "block_reason": None,
        "operation":    operation,
        "cwd_used":     str(cwd),
    }


# ── Git subprocess ────────────────────────────────────────────────────────────

def _run_git(argv: list[str], cwd: Path) -> tuple[int, str, str, int]:
    """Sync git runner. Returns (exit_code, stdout, stderr, duration_ms)."""
    start = time.monotonic()
    try:
        proc = subprocess.run(
            ["git"] + argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
        )
        return proc.returncode, proc.stdout, proc.stderr, int((time.monotonic() - start) * 1000)
    except subprocess.TimeoutExpired:
        return -1, "", f"git timed out after {TIMEOUT}s", int((time.monotonic() - start) * 1000)
    except Exception as exc:
        return -2, "", str(exc), int((time.monotonic() - start) * 1000)


def _current_branch(cwd: Path) -> str:
    rc, out, _, _ = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    return out.strip() if rc == 0 and out.strip() else "main"


# ── Patch 3 — Network I/O dampening ──────────────────────────────────────────

def _is_network_error(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in _NETWORK_ERRORS)


async def _run_network_safe(argv: list[str], cwd: Path) -> tuple[int, str, str, int]:
    """
    Async wrapper for push/pull that converts any network-layer failure
    to (502, "", "Gateway Unreachable: <detail>", duration_ms).
    All other failures pass through unchanged.
    """
    start = time.monotonic()
    try:
        loop = asyncio.get_event_loop()
        rc, stdout, stderr, duration_ms = await loop.run_in_executor(
            None, lambda: _run_git(argv, cwd)
        )
        # Non-zero + network pattern in stderr → 502
        if rc != 0 and _is_network_error(stderr):
            return 502, "", f"Gateway Unreachable: {stderr.strip()}", duration_ms
        return rc, stdout, stderr, duration_ms
    except (OSError, ConnectionError) as exc:
        return 502, "", f"Gateway Unreachable: {exc}", int((time.monotonic() - start) * 1000)
    except Exception as exc:
        if _is_network_error(str(exc)):
            return 502, "", f"Gateway Unreachable: {exc}", int((time.monotonic() - start) * 1000)
        raise


# ── Command builder (all safety rules live here) ──────────────────────────────

def _build_argv(
    operation: str, args: dict, cwd: Path
) -> tuple[list[str] | None, str | None]:
    """
    Map operation + args to a git argv list.
    Returns (argv, None) on success, (None, block_reason) when the
    operation is disallowed.
    """
    if operation == "status":
        return ["status", "--porcelain"], None

    if operation == "log":
        n = max(1, int(args.get("n", 10)))
        return ["log", "--oneline", f"-{n}"], None

    if operation == "diff":
        return ["diff", "--staged"] if args.get("staged") else ["diff"], None

    if operation == "add":
        # CLAUDE_RULES §14.4 enforcement: selective staging only. The repo is
        # shared with other agents — bulk staging is physically blocked.
        paths = args.get("paths")
        if isinstance(paths, str):
            paths = paths.split()
        if not paths:
            return None, "git add requires explicit 'paths' — bulk staging is blocked (CLAUDE_RULES 14.4)"
        forbidden = {".", "-A", "--all", "-a", "*"}
        bad = [p for p in paths if p.strip() in forbidden]
        if bad:
            return None, (f"git add {' '.join(bad)} is blocked — enumerate "
                          f"explicit file paths (CLAUDE_RULES 14.4)")
        return ["add"] + paths, None

    if operation == "commit":
        message = (args.get("message") or "").strip()
        if not message:
            return None, "commit requires a non-empty 'message'"
        return ["commit", "-m", message], None

    if operation == "push":
        branch = (args.get("branch") or "").strip() or _current_branch(cwd)
        if args.get("force"):
            return None, "git push --force is not permitted"
        if branch.lower() in PROTECTED_BRANCHES:
            return None, f"direct push to '{branch}' is not permitted"
        return ["push", "origin", branch], None

    if operation == "pull":
        branch = (args.get("branch") or "").strip() or _current_branch(cwd)
        return ["pull", "origin", branch], None

    if operation == "branch":
        name = (args.get("name") or "").strip()
        return (["checkout", "-b", name] if name else ["branch"]), None

    if operation == "reset_file":
        file_path = (args.get("file") or "").strip()
        if not file_path:
            return None, "reset_file requires a 'file' argument"
        return ["checkout", "--", file_path], None

    if operation == "stash":
        action = (args.get("action") or "push").lower()
        return (["stash", "pop"] if action == "pop" else ["stash"]), None

    # Anything else is unsupported — covers reset --hard, clean -fd, etc.
    return None, f"unsupported git operation: '{operation}'"


# ── Primary executor (async) ──────────────────────────────────────────────────

async def execute_async(
    operation: str,
    args: dict | None = None,
    cwd: str | None = None,
) -> dict:
    """
    Async primary executor used by mcp_server/server.py.

    Applies Patch 2 (per-repo lock) and Patch 3 (network dampening)
    with a real asyncio event loop — lock contention is actually effective
    when multiple MCP tool calls run concurrently.
    """
    args         = args or {}
    cwd_resolved = Path(cwd).resolve() if cwd else MAF_ROOT

    # CWD sandbox — same enforcement as shell_wire
    if not _check_cwd_sandbox(cwd_resolved):
        reason = f"cwd_out_of_sandbox: {cwd_resolved}"
        log.warning("[GIT_WIRE] BLOCKED (%s)", reason)
        _audit({"event": "cwd_blocked", "operation": operation, "cwd": str(cwd_resolved)})
        return _blocked(operation, cwd_resolved, reason)

    # Build argv + operation-level safety
    argv, block_reason = _build_argv(operation, args, cwd_resolved)
    if block_reason:
        log.warning("[GIT_WIRE] BLOCKED (%s): op=%r args=%s", block_reason, operation, args)
        _audit({"event": "blocked", "operation": operation,
                "args": args, "reason": block_reason})
        return _blocked(operation, cwd_resolved, block_reason)

    cmd_str = "git " + " ".join(argv)
    log.info("[GIT_WIRE] run: %r in %s", cmd_str, cwd_resolved)
    _audit({"event": "execute", "operation": operation,
            "command": cmd_str, "cwd": str(cwd_resolved)})

    # ── Patch 2: hold per-repo lock for the duration of the subprocess ────────
    lock = _get_repo_lock(str(cwd_resolved))
    async with lock:
        if operation in ("push", "pull"):
            # ── Patch 3: network-safe runner ──────────────────────────────────
            exit_code, stdout, stderr, duration_ms = await _run_network_safe(
                argv, cwd_resolved
            )
        else:
            loop = asyncio.get_event_loop()
            exit_code, stdout, stderr, duration_ms = await loop.run_in_executor(
                None, lambda: _run_git(argv, cwd_resolved)
            )

    timed_out = (exit_code == -1 and "timed out" in stderr)
    log.info("[GIT_WIRE] exit=%d duration=%dms op=%s", exit_code, duration_ms, operation)
    _audit({"event": "result", "operation": operation,
            "exit_code": exit_code, "duration_ms": duration_ms})

    return {
        "stdout":       stdout,
        "stderr":       stderr,
        "exit_code":    exit_code,
        "duration_ms":  duration_ms,
        "timed_out":    timed_out,
        "blocked":      False,
        "block_reason": None,
        "operation":    operation,
        "cwd_used":     str(cwd_resolved),
    }


def execute(
    operation: str,
    args: dict | None = None,
    cwd: str | None = None,
) -> dict:
    """
    Sync wrapper for ay_client.py (Gemini plane).
    Creates a fresh event loop via asyncio.run() — safe because Gemini
    tool calls are always synchronous with no running loop in the thread.
    """
    return asyncio.run(execute_async(operation, args, cwd))


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from unittest.mock import patch as _patch

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    MAF = str(MAF_ROOT)

    # (label, operation, args, expect_blocked, expect_exit_code_or_None)
    # NOTE: no state-changing operations against the REAL repo here. The old
    # "stash push" case ran a real `git stash` on the shared MAF tree on every
    # smoke run, silently hiding all agents' uncommitted work (discovered
    # 2026-06-12 — it caused the mid-session file reverts). Stash is now
    # exercised in the isolated temp repo below.
    CASES = [
        ("status",              "status",   {},                       False, None),
        ("log -5",              "log",      {"n": 5},                 False, None),
        ("diff unstaged",       "diff",     {},                       False, None),
        ("push --force",        "push",     {"force": True},          True,  -1),
        ("push to production",  "push",     {"branch": "production"}, True,  -1),
        ("push to prod",        "push",     {"branch": "prod"},       True,  -1),
        ("git clean (unsup.)",  "clean",    {},                       True,  -1),
        ("reset --hard (unsup.)","reset",   {},                       True,  -1),
        ("commit empty msg",    "commit",   {"message": ""},          True,  -1),
        ("reset_file no arg",   "reset_file",{},                     True,  -1),
    ]

    print("=== Git Wire Smoke Test ===\n")
    passed = failed = 0

    for label, op, args, expect_blocked, _ in CASES:
        r = execute(op, args=args, cwd=MAF)
        is_blocked = r["blocked"]
        ok = is_blocked == expect_blocked
        status = "PASS" if ok else "FAIL"
        note = (f" [BLOCKED: {r['block_reason']}]" if is_blocked
                else f" [exit={r['exit_code']} {len(r['stdout'])}ch]")
        print(f"  [{status}]{note}  {label}")
        if ok:
            passed += 1
        else:
            failed += 1
            if r["stderr"]:
                print(f"         stderr: {r['stderr'][:100]}")

    # ── Patch 3: network dampening (real connection-refused, no mocking) ─────────
    # A temp repo pointing to a closed port triggers an immediate network error
    # without any DNS timeout — tests the full code path end-to-end.
    print("\n  --- Patch 3: network dampening ---")
    import tempfile as _tmp
    import shutil as _shu
    import subprocess as _sp2

    _tmpdir = _tmp.mkdtemp()
    try:
        _git_env = {**os.environ,
                    "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t.com",
                    "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t.com"}
        _sp2.run(["git", "init"], cwd=_tmpdir, capture_output=True)
        _sp2.run(["git", "commit", "--allow-empty", "-m", "init"],
                 cwd=_tmpdir, capture_output=True, env=_git_env)
        _sp2.run(
            ["git", "remote", "add", "origin", "http://127.0.0.1:19999/nonexistent.git"],
            cwd=_tmpdir, capture_output=True,
        )
        _br = (_sp2.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                        cwd=_tmpdir, capture_output=True, text=True).stdout.strip() or "main")
        r = execute("push", {"branch": _br}, cwd=_tmpdir)
        ok_net = r["exit_code"] == 502 and "Gateway Unreachable" in r["stderr"]
        note   = f"[exit={r['exit_code']}] {r['stderr'][:55]}"
        print(f"  [{'PASS' if ok_net else 'FAIL'}] {note}  push connection-refused maps to 502")
        if ok_net:
            passed += 1
        else:
            failed += 1
            print(f"         stderr : {r['stderr'][:200]}")
            print(f"         stdout : {r['stdout'][:100]}")

        # ── stash: exercised ONLY in the isolated temp repo ──────────────────
        # (the old real-repo stash case silently hid all agents' uncommitted
        # work on every smoke run — root cause of the 2026-06-11/12 reverts)
        _f = os.path.join(_tmpdir, "tracked.txt")
        with open(_f, "w") as _fh:
            _fh.write("v1\n")
        _sp2.run(["git", "add", "tracked.txt"], cwd=_tmpdir, capture_output=True)
        _sp2.run(["git", "commit", "-m", "track"], cwd=_tmpdir,
                 capture_output=True, env=_git_env)
        with open(_f, "w") as _fh:
            _fh.write("v2 dirty\n")
        r = execute("stash", {"action": "push"}, cwd=_tmpdir)
        ok_stash = (not r["blocked"]) and r["exit_code"] == 0
        print(f"  [{'PASS' if ok_stash else 'FAIL'}] [exit={r['exit_code']}]  "
              f"stash push (temp repo only — never the shared tree)")
        if ok_stash:
            passed += 1
        else:
            failed += 1
    finally:
        _shu.rmtree(_tmpdir, ignore_errors=True)

    print(f"\n{passed}/{passed + failed} passed")
    if failed:
        sys.exit(1)
