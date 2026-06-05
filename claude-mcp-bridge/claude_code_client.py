"""
Claude Code Client — Primary Executor with Antigravity Fallback
---------------------------------------------------------------
Execution priority:
  1. Claude Code CLI (primary — direct local filesystem access)
  2. Antigravity API (fallback — when Claude quota exhausted)
Automatic failover: if Claude Code returns quota/rate-limit error,
falls through to Antigravity transparently.
"""

import os
import sys
import shutil
import subprocess
import logging
from pathlib import Path

log = logging.getLogger("ClaudeCodeClient")

MAF_ROOT = Path(__file__).parent.parent.resolve()

MAX_ITERATIONS = 5  # Safety cap inherited from ay_client circuit breaker

CLAUDE_QUOTA_ERRORS = [
    "rate limit",
    "quota",
    "overloaded",
    "529",
    "too many requests",
    "usage limit",
    "credit balance",
]


def _resolve_claude() -> str:
    """
    Resolves the claude CLI path cross-platform.
    On Windows, npm installs CLIs as .cmd wrappers that subprocess
    cannot find without shell=True. We probe explicit extensions first.
    """
    if sys.platform == "win32":
        for candidate in ["claude.cmd", "claude.CMD", "claude"]:
            found = shutil.which(candidate)
            if found:
                return found
        fallback = Path(r"C:\nvm4w\nodejs\claude.cmd")
        if fallback.exists():
            return str(fallback)
    return "claude"


_CLAUDE_BIN = _resolve_claude()


class QuotaExhaustedError(Exception):
    """Raised when Claude Code CLI hits quota/rate limits."""
    pass


def _is_quota_error(text: str) -> bool:
    """Returns True if the error indicates Claude quota exhaustion."""
    text_lower = text.lower()
    return any(signal in text_lower for signal in CLAUDE_QUOTA_ERRORS)


def _send_via_claude_code(mandate: str, timeout: int) -> str:
    """Primary: Claude Code CLI execution."""
    result = subprocess.run(
        [_CLAUDE_BIN, "-p", mandate, "--dangerously-skip-permissions"],
        capture_output=True,
        text=True,
        cwd=str(MAF_ROOT),
        timeout=timeout,
        encoding="utf-8",
        errors="replace"
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if _is_quota_error(stderr) or _is_quota_error(result.stdout):
            raise QuotaExhaustedError(
                f"Claude quota exhausted: {stderr[:200]}"
            )
        raise RuntimeError(
            f"[CLAUDE CODE] Exit {result.returncode}: {stderr}\n"
            f"Halting per CLAUDE_RULES.md Section 3.1."
        )
    ledger = result.stdout.strip()
    return ledger if ledger else "LEDGER: Execution complete."


def _send_via_antigravity(mandate: str, timeout: int) -> str:
    """Fallback: Antigravity API execution."""
    log.warning(
        "[EXECUTOR] Claude quota exhausted — falling back to Antigravity"
    )
    from ay_client import send_mandate as ay_send
    return ay_send(mandate, timeout=timeout)


def send_mandate(mandate: str, timeout: int = 300) -> str:
    """
    Sends mandate to Claude Code CLI.
    Falls back to Antigravity if Claude quota is exhausted.
    Automatically returns to Claude Code on next call once available.
    """
    # ── Primary: Claude Code ──────────────────────────────────────
    try:
        log.info(
            f"[EXECUTOR] Claude Code — dispatching mandate "
            f"({len(mandate)} chars)"
        )
        ledger = _send_via_claude_code(mandate, timeout)
        log.info(
            f"[EXECUTOR] Claude Code — ledger received "
            f"({len(ledger)} chars)"
        )
        return ledger
    except QuotaExhaustedError as qe:
        log.warning(f"[EXECUTOR] {qe}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"[CLAUDE CODE] Timed out after {timeout}s."
        )
    except FileNotFoundError:
        log.warning(
            "[EXECUTOR] Claude CLI not found — falling back to Antigravity"
        )

    # ── Fallback: Antigravity ─────────────────────────────────────
    try:
        return _send_via_antigravity(mandate, timeout)
    except Exception as ay_err:
        raise RuntimeError(
            f"[EXECUTOR] Both Claude Code and Antigravity failed.\n"
            f"Antigravity error: {ay_err}\n"
            f"Halting per CLAUDE_RULES.md Section 3.1."
        )


def test_connection() -> dict:
    """
    Tests both executors and returns their status.
    Returns: {"claude_code": bool, "antigravity": bool, "active": str}
    """
    claude_ok = False
    ay_ok = False

    # Test Claude Code
    try:
        result = subprocess.run(
            [_CLAUDE_BIN, "-p", "respond with exactly: BRIDGE OK",
             "--dangerously-skip-permissions"],
            capture_output=True,
            text=True,
            cwd=str(MAF_ROOT),
            timeout=30,
            encoding="utf-8",
            errors="replace"
        )
        claude_ok = (
            result.returncode == 0 and "BRIDGE OK" in result.stdout
        )
    except Exception as e:
        log.warning(f"[EXECUTOR] Claude Code test failed: {e}")

    # Test Antigravity
    try:
        from ay_client import test_connection as ay_test
        ay_ok = ay_test()
    except Exception as e:
        log.warning(f"[EXECUTOR] Antigravity test failed: {e}")

    active = (
        "Claude Code" if claude_ok
        else ("Antigravity" if ay_ok else "NONE")
    )
    return {
        "claude_code": claude_ok,
        "antigravity": ay_ok,
        "active": active
    }


if __name__ == "__main__":
    print("Testing Executor Cascade...")
    status = test_connection()
    print(f"Claude Code:  {'OK' if status['claude_code'] else 'UNAVAILABLE'}")
    print(f"Antigravity:  {'OK' if status['antigravity'] else 'UNAVAILABLE'}")
    print(f"Active Executor: {status['active']}")
