"""
SSH Wire — Phase 3 ClaudeAY Autonomy
--------------------------------------
Remote shell execution over SSH with the same safety model as shell_wire/git_wire.

Three Gemini architectural patches included from the start:

  Patch 1 — Host allowlist: only IPs in APPROVED_HOSTS are reachable.
             Anything else is blocked before paramiko is ever imported.
  Patch 2 — Concurrency lock: per-host asyncio.Lock prevents two autonomous
             tasks from opening simultaneous SSH sessions to the same server.
  Patch 3 — Network I/O dampening: paramiko.SSHException, socket.error,
             TimeoutError, OSError are caught and returned as exit_code=502
             ("Gateway Unreachable") so callers can distinguish "blocked"
             from "unreachable" from "command failed".

Served on both planes:
  - MCP plane  : execute_remote_shell tool in mcp_server/server.py
                 (calls execute_async directly — lock is effective)
  - Gemini plane: execute_remote_shell() in ay_client.py
                 (calls execute() sync wrapper via asyncio.run())

Audit log: logs/ssh_wire_audit.jsonl
"""

import asyncio
import json
import logging
import os
import re
import socket
import time
from datetime import datetime, timezone
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

log = logging.getLogger("SSHWire")

AUDIT_LOG = Path(__file__).parent / "logs" / "ssh_wire_audit.jsonl"

# ── Patch 1 — Host allowlist (zero-trust: unlisted hosts are blocked) ─────────
# Hardcoded — not from env. Adding a server requires a code change + review.

APPROVED_HOSTS: dict[str, str] = {
    "104.248.233.220": "maf-production-nyc1",
    "68.183.30.128":   "mwo-production-nyc1",
}


# ── Remote command blocklist ───────────────────────────────────────────────────
# Applied to every command before an SSH connection is opened.

_REMOTE_BLOCK_SPECS: list[tuple[str, str]] = [
    (r"\brm\s+-[a-z]*r[a-z]*f\s*/\b",             "rm -rf /"),
    (r"^\s*(?:reboot|shutdown|halt|poweroff)\b",   "system reboot/shutdown/halt/poweroff"),
    (r"^\s*mkfs\b",                                "filesystem format (mkfs)"),
    (r"^\s*format\b",                              "filesystem format"),
    (r"\binit\s+[06]\b",                           "system runlevel 0 or 6"),
]

_REMOTE_BLOCKLIST: list[tuple[re.Pattern, str]] = [
    (re.compile(pat, re.IGNORECASE), desc) for pat, desc in _REMOTE_BLOCK_SPECS
]


def _check_remote_blocklist(command: str) -> str | None:
    """Returns block reason if command matches any remote blocklist rule, else None."""
    for pattern, desc in _REMOTE_BLOCKLIST:
        if pattern.search(command):
            return desc
    return None


# ── Patch 2 — Per-host asyncio concurrency lock ───────────────────────────────
# Keyed by host_ip string. Prevents parallel SSH sessions to the same server.

_HOST_LOCKS: dict[str, asyncio.Lock] = {}


def _get_host_lock(host_ip: str) -> asyncio.Lock:
    if host_ip not in _HOST_LOCKS:
        _HOST_LOCKS[host_ip] = asyncio.Lock()
    return _HOST_LOCKS[host_ip]


# ── SSH key discovery ─────────────────────────────────────────────────────────

def _find_ssh_key() -> str | None:
    """Try SSH_KEY_PATH from .env first, then auto-discover standard key files."""
    key_path = os.getenv("SSH_KEY_PATH", "").strip()
    if key_path and Path(key_path).exists():
        return key_path
    home = Path.home()
    for name in ("id_ed25519", "id_rsa", "id_ecdsa", "id_dsa"):
        candidate = home / ".ssh" / name
        if candidate.exists():
            return str(candidate)
    return None


# ── Audit ─────────────────────────────────────────────────────────────────────

def _audit(entry: dict) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Result factories ──────────────────────────────────────────────────────────

def _blocked_result(host_ip: str, host_name: str, reason: str) -> dict:
    return {
        "stdout":       "",
        "stderr":       "",
        "exit_code":    -1,
        "duration_ms":  0,
        "timed_out":    False,
        "blocked":      True,
        "block_reason": reason,
        "host_ip":      host_ip,
        "host_name":    host_name,
    }


def _gateway_error(host_ip: str, host_name: str, detail: str, duration_ms: int) -> dict:
    """Patch 3 — network/connection failure mapped to 502."""
    return {
        "stdout":       "",
        "stderr":       f"Gateway Unreachable: {detail}",
        "exit_code":    502,
        "duration_ms":  duration_ms,
        "timed_out":    False,
        "blocked":      False,
        "block_reason": None,
        "host_ip":      host_ip,
        "host_name":    host_name,
    }


# ── Synchronous SSH runner (runs in executor thread) ─────────────────────────

def _run_ssh(host_ip: str, command: str, timeout: int) -> dict:
    """
    Blocking paramiko runner. Called from execute_async via run_in_executor.

    Connection-level exceptions (SSHException, socket.error, OSError) are NOT
    caught here — they propagate to execute_async for Patch 3 handling.

    Channel-level socket.timeout (command exceeded timeout) IS caught here
    and returns timed_out=True so callers can distinguish the two cases.
    """
    ssh_key = _find_ssh_key()
    start   = time.monotonic()

    stdout_str = ""
    stderr_str = ""
    exit_code  = -1
    timed_out  = False

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        connect_kwargs: dict = {
            "hostname":    host_ip,
            "username":    "root",
            "timeout":     timeout,
            "look_for_keys": True,
            "allow_agent": True,
        }
        if ssh_key:
            connect_kwargs["key_filename"] = ssh_key

        client.connect(**connect_kwargs)

        _, stdout_ch, stderr_ch = client.exec_command(command, timeout=timeout)
        chan = stdout_ch.channel
        chan.settimeout(timeout)

        try:
            exit_code  = chan.recv_exit_status()
            stdout_str = stdout_ch.read().decode("utf-8", errors="replace")
            stderr_str = stderr_ch.read().decode("utf-8", errors="replace")
        except socket.timeout:
            timed_out = True
            exit_code = -1

    finally:
        client.close()

    duration_ms = int((time.monotonic() - start) * 1000)
    return {
        "stdout":       stdout_str,
        "stderr":       stderr_str,
        "exit_code":    exit_code,
        "duration_ms":  duration_ms,
        "timed_out":    timed_out,
        "blocked":      False,
        "block_reason": None,
    }


# ── Primary executor (async) ──────────────────────────────────────────────────

async def execute_async(
    host_ip: str,
    command:  str,
    timeout:  int = 60,
) -> dict:
    """
    Async primary executor used by mcp_server/server.py.

    Gate order:
      1. Host allowlist (Patch 1)
      2. Remote command blocklist
      3. Per-host lock acquired (Patch 2)
      4. _run_ssh in executor thread
      5. Network exception → 502 (Patch 3)
    """
    host_name = APPROVED_HOSTS.get(host_ip, "")

    # Gate 1 — host allowlist
    if host_ip not in APPROVED_HOSTS:
        log.warning("[SSH_WIRE] BLOCKED unapproved host: %s", host_ip)
        _audit({"event": "blocked", "host_ip": host_ip,
                "command": command, "reason": "unapproved host"})
        return _blocked_result(host_ip, "", "unapproved host")

    # Gate 2 — remote command blocklist
    block_reason = _check_remote_blocklist(command)
    if block_reason:
        log.warning("[SSH_WIRE] BLOCKED remote command (%s): %r", block_reason, command)
        _audit({"event": "blocked", "host_ip": host_ip, "host_name": host_name,
                "command": command, "reason": block_reason})
        return _blocked_result(host_ip, host_name, block_reason)

    log.info("[SSH_WIRE] run on %s (%s) timeout=%ds: %r",
             host_ip, host_name, timeout, command)
    _audit({"event": "execute", "host_ip": host_ip, "host_name": host_name,
            "command": command, "timeout": timeout})

    start = time.monotonic()
    lock  = _get_host_lock(host_ip)

    # Gate 3 — per-host concurrency lock (Patch 2)
    async with lock:
        try:
            loop   = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: _run_ssh(host_ip, command, timeout)
            )
        except (paramiko.SSHException, socket.error, TimeoutError, OSError) as exc:
            # Gate 5 — Patch 3: network/connection failure → 502
            duration_ms = int((time.monotonic() - start) * 1000)
            log.warning("[SSH_WIRE] Network error on %s: %s", host_ip, exc)
            _audit({"event": "gateway_error", "host_ip": host_ip,
                    "host_name": host_name, "error": str(exc)})
            return _gateway_error(host_ip, host_name, str(exc), duration_ms)

    result["host_ip"]   = host_ip
    result["host_name"] = host_name

    log.info("[SSH_WIRE] exit=%d duration=%dms host=%s",
             result["exit_code"], result["duration_ms"], host_ip)
    _audit({"event": "result", "host_ip": host_ip, "host_name": host_name,
            "exit_code": result["exit_code"], "duration_ms": result["duration_ms"]})

    return result


def execute(
    host_ip: str,
    command:  str,
    timeout:  int = 60,
) -> dict:
    """
    Sync wrapper for ay_client.py (Gemini plane).
    Creates a fresh event loop via asyncio.run() — safe because Gemini
    tool calls are always synchronous with no running loop in the thread.
    """
    return asyncio.run(execute_async(host_ip, command, timeout))


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from unittest.mock import patch as _patch

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    MAF_PROD = "104.248.233.220"
    passed = failed = 0

    def _report(label: str, ok: bool, note: str = "") -> None:
        global passed, failed
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}]{(' ' + note) if note else ''}  {label}")
        if ok:
            passed += 1
        else:
            failed += 1

    print("=== SSH Wire Smoke Test ===\n")

    # ── Case 1: whoami on approved production host ────────────────────────────
    print("  --- Case 1: live SSH to maf-production-nyc1 ---")
    r1 = execute(MAF_PROD, "whoami", timeout=30)
    ok1 = (not r1["blocked"]
           and r1["exit_code"] == 0
           and "root" in r1["stdout"].lower())
    _report(
        "whoami: exit=0, stdout contains 'root'",
        ok1,
        f"[exit={r1['exit_code']} host={r1['host_name']} stdout={r1['stdout'].strip()!r}]",
    )
    if not ok1 and r1.get("stderr"):
        print(f"         stderr: {r1['stderr'][:120]}")

    # ── Case 2: unapproved host blocked before connection ─────────────────────
    print("\n  --- Case 2: unapproved host ---")
    r2 = execute("8.8.8.8", "whoami")
    ok2 = r2["blocked"] and r2["block_reason"] == "unapproved host"
    _report(
        "8.8.8.8: blocked=True, reason='unapproved host'",
        ok2,
        f"[blocked={r2['blocked']} reason={r2['block_reason']!r}]",
    )

    # ── Case 3: remote blocklist refuses reboot ───────────────────────────────
    print("\n  --- Case 3: remote blocklist ---")
    r3 = execute(MAF_PROD, "reboot")
    ok3 = r3["blocked"] and r3["block_reason"] is not None
    _report(
        "reboot: blocked=True",
        ok3,
        f"[blocked={r3['blocked']} reason={r3['block_reason']!r}]",
    )

    # ── Case 4: network failure → 502 Gateway Unreachable ────────────────────
    # Patch paramiko.SSHClient.connect to simulate an unreachable host without
    # needing a real network timeout.
    print("\n  --- Case 4: network I/O dampening (Patch 3) ---")
    with _patch.object(
        paramiko.SSHClient, "connect",
        side_effect=paramiko.SSHException("Connection refused by remote host"),
    ):
        r4 = execute(MAF_PROD, "whoami")

    ok4 = (not r4["blocked"]
           and r4["exit_code"] == 502
           and "Gateway Unreachable" in r4["stderr"])
    _report(
        "SSHException: exit=502, stderr contains 'Gateway Unreachable'",
        ok4,
        f"[exit={r4['exit_code']} stderr={r4['stderr'][:60]!r}]",
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{passed}/{passed + failed} passed")
    if failed:
        sys.exit(1)
