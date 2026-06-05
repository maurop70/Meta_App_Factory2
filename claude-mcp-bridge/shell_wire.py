"""
Shell Execution Wire
--------------------
Safe, audited shell execution for the MAF MCP bridge.
Serves both planes:
  - MCP plane  : execute_shell / get_shell_log tools in mcp_server/server.py
  - Gemini plane: ay_client.execute_local_shell() delegates here

Safety model:
  - Hard blocklist (regex): destructive OS-level commands refused before
    any subprocess is spawned. No allowlist — all dev workflows pass through.
  - CWD sandbox: working directory must be within SHELL_WIRE_ALLOWED_ROOTS
    (semicolon-separated in .env, defaults to MAF root + TEMP).
  - Configurable timeout, clamped to [1, 120] seconds.
  - Every execution written to logs/shell_wire_audit.jsonl.
  - stdout/stderr streamed live to logs/shell_wire_live.log via threads.
"""

import json
import logging
import os
import platform
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

log = logging.getLogger("ShellWire")

MAF_ROOT        = Path(__file__).parent.parent.resolve()
LIVE_LOG        = Path(__file__).parent / "logs" / "shell_wire_live.log"
AUDIT_LOG       = Path(__file__).parent / "logs" / "shell_wire_audit.jsonl"
DEFAULT_TIMEOUT = 30
MAX_TIMEOUT     = 120


# ── Blocklist ─────────────────────────────────────────────────────────────────
# Patterns matched case-insensitively against the raw command string.
# Refused immediately — no subprocess is ever spawned for a blocked command.

_BLOCK_SPECS: list[tuple[str, str]] = [
    # No-preserve-root (no legitimate use in autonomous context)
    (r"--no-preserve-root",
     "--no-preserve-root flag"),
    # rm targeting filesystem root
    (r"\brm\b.*\s/\s*$",
     "rm of filesystem root /"),
    (r"\brm\b.*\s/\*",
     "rm of root wildcard /*"),
    # Windows drive root and system directory nukes
    (r"\b(?:del|rd|rmdir)\b.*/[sS].*\b[A-Za-z]:\\\s*$",
     "Windows drive root deletion"),
    (r"\b(?:del|rd|rmdir)\b.*/[sS].*\b[A-Za-z]:\\\*",
     "Windows drive root wildcard"),
    (r"\b(?:del|rd|rmdir)\b.*/[sS].*\b(?:windows|system32|program files)\b",
     "Windows system directory deletion"),
    # Disk format
    (r"^\s*format\s+[A-Za-z]:",
     "disk format"),
    # Shutdown / reboot
    (r"^\s*(?:shutdown|poweroff|reboot|halt)\b",
     "system shutdown/reboot/halt"),
    (r"\binit\s+[06]\b",
     "system runlevel 0 or 6"),
    # Machine-wide registry deletion
    (r"\breg(?:\.exe)?\s+delete\s+(?:HKLM|HKEY_LOCAL_MACHINE)\b",
     "HKLM registry deletion"),
]

BLOCKLIST: list[tuple[re.Pattern, str]] = [
    (re.compile(pat, re.IGNORECASE), desc) for pat, desc in _BLOCK_SPECS
]


def _check_blocklist(command: str) -> str | None:
    """Returns the block reason if the command matches any blocklist rule, else None."""
    for pattern, desc in BLOCKLIST:
        if pattern.search(command):
            return desc
    return None


# ── CWD Sandbox ───────────────────────────────────────────────────────────────
# SHELL_WIRE_ALLOWED_ROOTS: semicolon-separated paths in .env.
# Semicolons are used (not colons) to avoid ambiguity with Windows drive letters.
# Example: SHELL_WIRE_ALLOWED_ROOTS=C:/Dev/MAF;C:/Dev/MWO;C:/Dev/HouseOfVera

def _load_allowed_roots() -> list[Path]:
    raw = os.getenv("SHELL_WIRE_ALLOWED_ROOTS", "").strip()
    roots: list[Path] = []
    if raw:
        for segment in raw.split(";"):
            segment = segment.strip()
            if segment:
                roots.append(Path(segment).resolve())
    if not roots:
        roots.append(MAF_ROOT)
    temp = Path(os.environ.get("TEMP", os.environ.get("TMPDIR", "/tmp"))).resolve()
    if temp not in roots:
        roots.append(temp)
    return roots


def _check_cwd_sandbox(cwd: Path) -> bool:
    """Returns True if cwd is within at least one allowed root."""
    normalized = os.path.normcase(os.path.abspath(str(cwd)))
    for root in _load_allowed_roots():
        root_norm = os.path.normcase(os.path.abspath(str(root)))
        if normalized == root_norm or normalized.startswith(root_norm + os.sep):
            return True
    return False


# ── Shell resolution ──────────────────────────────────────────────────────────

def _shell_argv(shell: str, command: str) -> list[str]:
    """Builds the subprocess argv list for the requested shell."""
    os_name  = platform.system().lower()
    resolved = shell if shell != "auto" else ("powershell" if os_name == "windows" else "bash")
    if resolved == "powershell":
        return ["powershell", "-NonInteractive", "-Command", command]
    if resolved == "cmd":
        return ["cmd", "/c", command]
    if resolved == "bash":
        return ["bash", "-c", command]
    raise ValueError(f"Unknown shell: {shell!r}")


# ── Audit logging ─────────────────────────────────────────────────────────────

def _audit(entry: dict) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Blocked result factory ────────────────────────────────────────────────────

def _blocked(command: str, cwd: Path, reason: str) -> dict:
    return {
        "stdout":       "",
        "stderr":       "",
        "exit_code":    -1,
        "duration_ms":  0,
        "timed_out":    False,
        "blocked":      True,
        "block_reason": reason,
        "command_run":  command,
        "cwd_used":     str(cwd),
    }


# ── Main execute() ────────────────────────────────────────────────────────────

def execute(
    command: str,
    cwd: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT,
    shell: str = "auto",
) -> dict:
    """
    Execute a shell command with safety checks, CWD sandbox, and live streaming.

    Args:
        command:         Raw command string to execute.
        cwd:             Working directory. Defaults to MAF root.
        timeout_seconds: Max execution time. Clamped to [1, 120].
        shell:           "auto" | "powershell" | "cmd" | "bash".
                         "auto" resolves to powershell on Windows, bash elsewhere.

    Returns dict:
        stdout, stderr, exit_code, duration_ms, timed_out,
        blocked, block_reason, command_run, cwd_used
    """
    timeout_seconds = max(1, min(int(timeout_seconds), MAX_TIMEOUT))
    cwd_resolved    = Path(cwd).resolve() if cwd else MAF_ROOT

    # Blocklist gate
    block_reason = _check_blocklist(command)
    if block_reason:
        log.warning("[SHELL_WIRE] BLOCKED (%s): %r", block_reason, command)
        _audit({"event": "blocked", "command": command, "reason": block_reason})
        return _blocked(command, cwd_resolved, block_reason)

    # CWD sandbox gate
    if not _check_cwd_sandbox(cwd_resolved):
        reason = f"cwd_out_of_sandbox: {cwd_resolved}"
        log.warning("[SHELL_WIRE] BLOCKED (%s)", reason)
        _audit({"event": "cwd_blocked", "command": command, "cwd": str(cwd_resolved)})
        return _blocked(command, cwd_resolved, reason)

    log.info("[SHELL_WIRE] run (timeout=%ds shell=%s): %r", timeout_seconds, shell, command)
    _audit({"event": "execute", "command": command,
            "cwd": str(cwd_resolved), "timeout": timeout_seconds})

    # Initialise live log for this run
    LIVE_LOG.parent.mkdir(parents=True, exist_ok=True)
    LIVE_LOG.write_text(
        f"[shell_wire] command : {command}\n"
        f"[shell_wire] cwd     : {cwd_resolved}\n"
        f"[shell_wire] timeout : {timeout_seconds}s\n\n",
        encoding="utf-8",
    )

    stdout_buf: list[str] = []
    stderr_buf: list[str] = []
    timed_out  = False
    exit_code  = -1
    start      = time.monotonic()

    try:
        proc = subprocess.Popen(
            _shell_argv(shell, command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(cwd_resolved),
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        def _reader(stream, buf: list[str], label: str) -> None:
            for line in stream:
                buf.append(line)
                try:
                    with open(LIVE_LOG, "a", encoding="utf-8") as f:
                        f.write(f"[{label}] {line}")
                except Exception:
                    pass

        t_out = threading.Thread(target=_reader, args=(proc.stdout, stdout_buf, "OUT"), daemon=True)
        t_err = threading.Thread(target=_reader, args=(proc.stderr, stderr_buf, "ERR"), daemon=True)
        t_out.start()
        t_err.start()

        try:
            proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            timed_out = True

        t_out.join(timeout=2)
        t_err.join(timeout=2)
        exit_code = proc.returncode if not timed_out else -1

    except Exception as exc:
        stderr_buf.append(f"[shell_wire error] {exc}\n")
        exit_code = -2

    duration_ms = int((time.monotonic() - start) * 1000)
    log.info("[SHELL_WIRE] exit=%d duration=%dms timed_out=%s", exit_code, duration_ms, timed_out)
    _audit({"event": "result", "command": command, "exit_code": exit_code,
            "duration_ms": duration_ms, "timed_out": timed_out})

    return {
        "stdout":       "".join(stdout_buf),
        "stderr":       "".join(stderr_buf),
        "exit_code":    exit_code,
        "duration_ms":  duration_ms,
        "timed_out":    timed_out,
        "blocked":      False,
        "block_reason": None,
        "command_run":  command,
        "cwd_used":     str(cwd_resolved),
    }
