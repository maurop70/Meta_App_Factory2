"""
File System Wire — Phase 4 ClaudeAY Autonomy
----------------------------------------------
Safe, audited local file system operations for the MAF MCP bridge.
Served on both planes:
  - MCP plane  : file_operation tool in mcp_server/server.py
                 (calls execute_async — thin executor wrapper around execute)
  - Gemini plane: write_local_file() and read_local_file() in ay_client.py
                 (delegate to execute() directly)

Safety model:
  - PATH SANDBOX  : all resolved paths must be within SHELL_WIRE_ALLOWED_ROOTS
                    (imported from shell_wire — single source of truth).
  - SYSTEM PATHS  : /etc/, /boot/, /bin/, /sbin/, C:\\Windows blocked for all ops.
  - DELETE BLOCK  : .env files, .db/.sqlite databases, .git dir/contents.
  - WRITE BLOCK   : deploy_maf.py and deploy_erp.py are pipeline artifacts —
                    write/append to them is blocked.
  - SIZE LIMITS   : read ≤ 2 MB, write/append ≤ 5 MB, list ≤ 500 entries.

Operations: read, write, append, delete, list, exists, mkdir, move.

Audit log: logs/fs_wire_audit.jsonl
"""

import asyncio
import json
import logging
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# CWD sandbox enforcement — single source of truth in shell_wire
from shell_wire import _check_cwd_sandbox

log = logging.getLogger("FSWire")

MAF_ROOT         = Path(__file__).parent.parent.resolve()
AUDIT_LOG        = Path(__file__).parent / "logs" / "fs_wire_audit.jsonl"
READ_MAX_BYTES   = 2 * 1024 * 1024   # 2 MB
WRITE_MAX_BYTES  = 5 * 1024 * 1024   # 5 MB
LIST_MAX_ENTRIES = 500

SUPPORTED_OPERATIONS = frozenset({
    "read", "write", "append", "delete",
    "list", "exists", "mkdir", "move",
})


# ── System path blocklist (all operations) ────────────────────────────────────

_SYSTEM_BLOCK_SPECS: list[tuple[str, str]] = [
    (r"/etc/",          "system path /etc/"),
    (r"/boot/",         "system path /boot/"),
    (r"/bin/",          "system path /bin/"),
    (r"/sbin/",         "system path /sbin/"),
    (r"[Cc]:/[Ww]indows", "system path C:/Windows"),
]
_SYSTEM_BLOCKLIST: list[tuple[re.Pattern, str]] = [
    (re.compile(pat), desc) for pat, desc in _SYSTEM_BLOCK_SPECS
]


def _check_system_path(path: Path) -> str | None:
    """Returns block reason if path is a protected system path, else None."""
    posix = path.as_posix()
    for pattern, desc in _SYSTEM_BLOCKLIST:
        if pattern.search(posix):
            return desc
    return None


# ── Delete blocklist ──────────────────────────────────────────────────────────

def _check_delete_blocklist(path: Path) -> str | None:
    """Returns block reason for delete if the path matches a protected pattern."""
    name = path.name.lower()

    if name == ".env" or re.match(r"^\.env[.\-_]", name):
        return ".env file deletion blocked"

    if path.suffix.lower() in (".db", ".sqlite", ".sqlite3"):
        return "database file deletion blocked"

    if ".git" in [p.lower() for p in path.parts]:
        return ".git directory/contents deletion blocked"

    # CLAUDE_RULES §14.3 enforcement: migration/deploy backups survive their
    # session. (.db backups are already covered by the suffix rule above;
    # this catches renamed/exported backup artifacts of any extension.)
    if re.search(r"(?:^|[._\-])(?:pre_deploy|pre_inventory|pre_migration|backup)[._\-]", name):
        return "backup file deletion blocked — backups are removed only on explicit operator confirmation (CLAUDE_RULES 14.3)"
    if "archives" in [p.lower() for p in path.parts]:
        return "archives/ contents deletion blocked (CLAUDE_RULES 14.3)"

    return None


# ── Write/append blocklist ────────────────────────────────────────────────────

def _check_write_blocklist(path: Path) -> str | None:
    """Returns block reason for write/append if path is a protected file."""
    if path.name.lower() in ("deploy_maf.py", "deploy_erp.py"):
        return f"write to {path.name} is blocked — deploy scripts are pipelines, not free-form edits"
    return None


# ── Path resolution ───────────────────────────────────────────────────────────

def _resolve_path(path: str, cwd: str | None) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p.resolve()
    base = Path(cwd).resolve() if cwd else MAF_ROOT
    return (base / p).resolve()


# ── Audit ─────────────────────────────────────────────────────────────────────

def _audit(entry: dict) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Result factories ──────────────────────────────────────────────────────────

def _ok(operation: str, path: Path, content: str = "", duration_ms: int = 0) -> dict:
    return {
        "content":      content,
        "stdout":       "",
        "stderr":       "",
        "exit_code":    0,
        "duration_ms":  duration_ms,
        "timed_out":    False,
        "blocked":      False,
        "block_reason": None,
        "operation":    operation,
        "path_used":    str(path),
    }


def _error(operation: str, path: Path, message: str, duration_ms: int = 0) -> dict:
    return {
        "content":      "",
        "stdout":       "",
        "stderr":       message,
        "exit_code":    1,
        "duration_ms":  duration_ms,
        "timed_out":    False,
        "blocked":      False,
        "block_reason": None,
        "operation":    operation,
        "path_used":    str(path),
    }


def _blocked_result(operation: str, path: Path, reason: str) -> dict:
    return {
        "content":      "",
        "stdout":       "",
        "stderr":       "",
        "exit_code":    -1,
        "duration_ms":  0,
        "timed_out":    False,
        "blocked":      True,
        "block_reason": reason,
        "operation":    operation,
        "path_used":    str(path),
    }


# ── Operation implementations ─────────────────────────────────────────────────

def _do_read(path: Path, start: float) -> dict:
    if not path.exists():
        return _error("read", path, f"file not found: {path}",
                      int((time.monotonic() - start) * 1000))
    if not path.is_file():
        return _error("read", path, f"not a file: {path}",
                      int((time.monotonic() - start) * 1000))
    size = path.stat().st_size
    if size > READ_MAX_BYTES:
        return _error("read", path,
                      f"file too large ({size:,} bytes > {READ_MAX_BYTES:,} byte limit); "
                      f"use chunked reads",
                      int((time.monotonic() - start) * 1000))
    content = path.read_text(encoding="utf-8", errors="replace")
    duration_ms = int((time.monotonic() - start) * 1000)
    _audit({"event": "result", "operation": "read", "path": str(path),
            "size": size, "duration_ms": duration_ms})
    return _ok("read", path, content, duration_ms)


def _do_write(path: Path, content: str, start: float) -> dict:
    content_bytes = content.encode("utf-8")
    if len(content_bytes) > WRITE_MAX_BYTES:
        return _error("write", path,
                      f"content too large ({len(content_bytes):,} bytes > "
                      f"{WRITE_MAX_BYTES:,} byte limit)",
                      int((time.monotonic() - start) * 1000))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    duration_ms = int((time.monotonic() - start) * 1000)
    _audit({"event": "result", "operation": "write", "path": str(path),
            "bytes": len(content_bytes), "duration_ms": duration_ms})
    return _ok("write", path, f"wrote {len(content_bytes):,} bytes", duration_ms)


def _do_append(path: Path, content: str, start: float) -> dict:
    content_bytes = content.encode("utf-8")
    if len(content_bytes) > WRITE_MAX_BYTES:
        return _error("append", path,
                      f"content too large ({len(content_bytes):,} bytes > "
                      f"{WRITE_MAX_BYTES:,} byte limit)",
                      int((time.monotonic() - start) * 1000))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)
    duration_ms = int((time.monotonic() - start) * 1000)
    _audit({"event": "result", "operation": "append", "path": str(path),
            "bytes": len(content_bytes), "duration_ms": duration_ms})
    return _ok("append", path, f"appended {len(content_bytes):,} bytes", duration_ms)


def _do_delete(path: Path, start: float) -> dict:
    if not path.exists():
        return _error("delete", path, f"file not found: {path}",
                      int((time.monotonic() - start) * 1000))
    if path.is_dir():
        return _error("delete", path,
                      "delete only removes files; directory removal is not supported",
                      int((time.monotonic() - start) * 1000))
    path.unlink()
    duration_ms = int((time.monotonic() - start) * 1000)
    _audit({"event": "result", "operation": "delete", "path": str(path),
            "duration_ms": duration_ms})
    return _ok("delete", path, "deleted", duration_ms)


def _do_list(path: Path, recursive: bool, start: float) -> dict:
    if not path.exists():
        return _error("list", path, f"directory not found: {path}",
                      int((time.monotonic() - start) * 1000))
    if not path.is_dir():
        return _error("list", path, f"not a directory: {path}",
                      int((time.monotonic() - start) * 1000))

    glob_fn = path.rglob("*") if recursive else path.iterdir()
    entries: list[dict] = []
    truncated = False

    for p in sorted(glob_fn):
        if len(entries) >= LIST_MAX_ENTRIES:
            truncated = True
            break
        name = (
            str(p.relative_to(path)).replace("\\", "/")
            if recursive else p.name
        )
        entries.append({
            "name": name,
            "type": "directory" if p.is_dir() else "file",
            "size": p.stat().st_size if p.is_file() else 0,
        })

    payload = json.dumps({"entries": entries, "count": len(entries), "truncated": truncated})
    duration_ms = int((time.monotonic() - start) * 1000)
    _audit({"event": "result", "operation": "list", "path": str(path),
            "count": len(entries), "truncated": truncated, "duration_ms": duration_ms})
    return _ok("list", path, payload, duration_ms)


def _do_exists(path: Path, start: float) -> dict:
    exists = path.exists()
    duration_ms = int((time.monotonic() - start) * 1000)
    _audit({"event": "result", "operation": "exists", "path": str(path),
            "exists": exists, "duration_ms": duration_ms})
    return _ok("exists", path, "true" if exists else "false", duration_ms)


def _do_mkdir(path: Path, start: float) -> dict:
    path.mkdir(parents=True, exist_ok=True)
    duration_ms = int((time.monotonic() - start) * 1000)
    _audit({"event": "result", "operation": "mkdir", "path": str(path),
            "duration_ms": duration_ms})
    return _ok("mkdir", path, f"created {path}", duration_ms)


def _do_move(source: Path, destination: Path, start: float) -> dict:
    if not source.exists():
        return _error("move", source, f"source not found: {source}",
                      int((time.monotonic() - start) * 1000))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    duration_ms = int((time.monotonic() - start) * 1000)
    _audit({"event": "result", "operation": "move", "path": str(source),
            "destination": str(destination), "duration_ms": duration_ms})
    return _ok("move", source, f"moved to {destination}", duration_ms)


# ── Primary executor (sync) ───────────────────────────────────────────────────

def execute(
    operation:   str,
    path:        str,
    content:     str | None = None,
    destination: str | None = None,
    cwd:         str | None = None,
    recursive:   bool = False,
) -> dict:
    """
    Synchronous primary executor.

    Gate order (applied before any I/O):
      1. Validate operation name
      2. Resolve path (relative → absolute)
      3. System path check (all operations)
      4. Sandbox check (all operations)
      5. Operation-specific block checks (delete / write / append)
      6. Execute operation
    """
    if operation not in SUPPORTED_OPERATIONS:
        dummy = Path(path) if path else Path(".")
        return _error(operation, dummy, f"unsupported operation: {operation!r}")

    # Gate 2 — resolve path
    try:
        resolved = _resolve_path(path, cwd)
    except Exception as exc:
        return _error(operation, Path(path), f"path resolution failed: {exc}")

    # Gate 3 — system path
    sys_reason = _check_system_path(resolved)
    if sys_reason:
        log.warning("[FS_WIRE] BLOCKED system path (%s): %s", sys_reason, resolved)
        _audit({"event": "blocked", "operation": operation,
                "path": str(resolved), "reason": sys_reason})
        return _blocked_result(operation, resolved, sys_reason)

    # Gate 4 — sandbox
    if not _check_cwd_sandbox(resolved):
        reason = f"path outside sandbox: {resolved}"
        log.warning("[FS_WIRE] BLOCKED sandbox violation: %s", resolved)
        _audit({"event": "blocked", "operation": operation,
                "path": str(resolved), "reason": reason})
        return _blocked_result(operation, resolved, reason)

    # Gate 5 — operation-specific blocks
    if operation == "delete":
        del_reason = _check_delete_blocklist(resolved)
        if del_reason:
            log.warning("[FS_WIRE] BLOCKED delete (%s): %s", del_reason, resolved)
            _audit({"event": "blocked", "operation": operation,
                    "path": str(resolved), "reason": del_reason})
            return _blocked_result(operation, resolved, del_reason)

    if operation in ("write", "append"):
        write_reason = _check_write_blocklist(resolved)
        if write_reason:
            log.warning("[FS_WIRE] BLOCKED write (%s): %s", write_reason, resolved)
            _audit({"event": "blocked", "operation": operation,
                    "path": str(resolved), "reason": write_reason})
            return _blocked_result(operation, resolved, write_reason)

    log.info("[FS_WIRE] %s: %s", operation, resolved)
    _audit({"event": "execute", "operation": operation, "path": str(resolved)})

    start = time.monotonic()

    try:
        if operation == "read":
            return _do_read(resolved, start)

        if operation == "write":
            return _do_write(resolved, content or "", start)

        if operation == "append":
            return _do_append(resolved, content or "", start)

        if operation == "delete":
            return _do_delete(resolved, start)

        if operation == "list":
            return _do_list(resolved, recursive, start)

        if operation == "exists":
            return _do_exists(resolved, start)

        if operation == "mkdir":
            return _do_mkdir(resolved, start)

        if operation == "move":
            if not destination:
                return _error(operation, resolved,
                              "move requires a 'destination' argument")
            try:
                dest_resolved = _resolve_path(destination, cwd)
            except Exception as exc:
                return _error(operation, resolved,
                              f"destination path resolution failed: {exc}")

            dest_sys = _check_system_path(dest_resolved)
            if dest_sys:
                return _blocked_result(operation, resolved,
                                       f"destination blocked — {dest_sys}")
            if not _check_cwd_sandbox(dest_resolved):
                return _blocked_result(operation, resolved,
                                       f"destination outside sandbox: {dest_resolved}")
            dest_write = _check_write_blocklist(dest_resolved)
            if dest_write:
                return _blocked_result(operation, resolved,
                                       f"destination blocked — {dest_write}")
            return _do_move(resolved, dest_resolved, start)

    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        log.error("[FS_WIRE] error in %s on %s: %s", operation, resolved, exc)
        _audit({"event": "error", "operation": operation,
                "path": str(resolved), "error": str(exc)})
        return _error(operation, resolved, str(exc), duration_ms)

    # Unreachable — keeps the type-checker happy
    return _error(operation, resolved, f"internal error: unhandled operation {operation!r}")


# ── Async wrapper (for mcp_server/server.py) ─────────────────────────────────

async def execute_async(
    operation:   str,
    path:        str,
    content:     str | None = None,
    destination: str | None = None,
    cwd:         str | None = None,
    recursive:   bool = False,
) -> dict:
    """
    Async wrapper used by mcp_server/server.py.
    Runs execute() in a thread-pool executor so the MCP event loop stays free.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: execute(operation, path, content, destination, cwd, recursive),
    )


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    passed = failed = 0
    SMOKE_FILE = "logs/fs_wire_smoke_test.tmp"
    MAF = str(MAF_ROOT)

    def _report(label: str, ok: bool, note: str = "") -> None:
        global passed, failed
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}]{(' ' + note) if note else ''}  {label}")
        if ok:
            passed += 1
        else:
            failed += 1

    print("=== FS Wire Smoke Test ===\n")

    # ── Case 1: write ─────────────────────────────────────────────────────────
    r1 = execute("write", SMOKE_FILE, content="hello phase 4", cwd=MAF)
    ok1 = r1["exit_code"] == 0 and not r1["blocked"]
    _report("write temp file: exit_code=0", ok1,
            f"[exit={r1['exit_code']} content={r1['content']!r}]")

    # ── Case 2: read back ─────────────────────────────────────────────────────
    r2 = execute("read", SMOKE_FILE, cwd=MAF)
    ok2 = r2["exit_code"] == 0 and r2["content"] == "hello phase 4"
    _report("read back: content matches", ok2,
            f"[exit={r2['exit_code']} content={r2['content']!r}]")

    # ── Case 3: append ────────────────────────────────────────────────────────
    r3 = execute("append", SMOKE_FILE, content="\nline 2", cwd=MAF)
    r3_read = execute("read", SMOKE_FILE, cwd=MAF)
    ok3 = r3["exit_code"] == 0 and "line 2" in r3_read["content"]
    _report("append: content updated", ok3,
            f"[exit={r3['exit_code']} full={r3_read['content']!r}]")

    # ── Case 4: list ──────────────────────────────────────────────────────────
    r4 = execute("list", "logs", cwd=MAF)
    listing = json.loads(r4["content"]) if r4["exit_code"] == 0 else {"entries": []}
    names = [e["name"] for e in listing.get("entries", [])]
    ok4 = r4["exit_code"] == 0 and "fs_wire_smoke_test.tmp" in names
    _report("list logs/: file appears in listing", ok4,
            f"[count={listing.get('count',0)} found={'fs_wire_smoke_test.tmp' in names}]")

    # ── Case 5: exists (True) ─────────────────────────────────────────────────
    r5 = execute("exists", SMOKE_FILE, cwd=MAF)
    ok5 = r5["exit_code"] == 0 and r5["content"] == "true"
    _report("exists before delete: true", ok5,
            f"[exit={r5['exit_code']} content={r5['content']!r}]")

    # ── Case 6: delete ────────────────────────────────────────────────────────
    r6 = execute("delete", SMOKE_FILE, cwd=MAF)
    ok6 = r6["exit_code"] == 0 and not r6["blocked"]
    _report("delete temp file: exit_code=0", ok6,
            f"[exit={r6['exit_code']} content={r6['content']!r}]")

    # ── Case 7: exists (False) ────────────────────────────────────────────────
    r7 = execute("exists", SMOKE_FILE, cwd=MAF)
    ok7 = r7["exit_code"] == 0 and r7["content"] == "false"
    _report("exists after delete: false", ok7,
            f"[exit={r7['exit_code']} content={r7['content']!r}]")

    # ── Case 8: blocked — delete .env ─────────────────────────────────────────
    r8 = execute("delete", ".env", cwd=MAF)
    ok8 = r8["blocked"] and r8["block_reason"] is not None
    _report("delete .env: blocked=True", ok8,
            f"[blocked={r8['blocked']} reason={r8['block_reason']!r}]")

    # ── Case 9: blocked — write to deploy_maf.py ──────────────────────────────
    r9 = execute("write", "deploy_maf.py", content="# malicious", cwd=MAF)
    ok9 = r9["blocked"] and r9["block_reason"] is not None
    _report("write deploy_maf.py: blocked=True", ok9,
            f"[blocked={r9['blocked']} reason={r9['block_reason']!r}]")

    # ── Case 10: blocked — path outside sandbox ───────────────────────────────
    # C:\TestOutside_Phase4 is outside MAF_ROOT and TEMP and has no system-path
    # patterns, so this tests the sandbox gate specifically.
    r10 = execute("read", "C:\\TestOutside_Phase4\\probe.txt")
    ok10 = r10["blocked"] and "sandbox" in (r10["block_reason"] or "").lower()
    _report("path outside sandbox: blocked=True", ok10,
            f"[blocked={r10['blocked']} reason={r10['block_reason']!r}]")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{passed}/{passed + failed} passed")
    if failed:
        sys.exit(1)
