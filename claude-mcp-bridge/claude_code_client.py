"""
Claude Code Client
------------------
Replaces ay_client.py as the MAF executor.
Sends mandates to Claude Code CLI and returns ledgers.
Direct local filesystem access — no cloud sandbox dependency.
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
        # Hard-coded fallback for nvm4w layout
        fallback = Path(r"C:\nvm4w\nodejs\claude.cmd")
        if fallback.exists():
            return str(fallback)
    return "claude"


_CLAUDE_BIN = _resolve_claude()


def send_mandate(mandate: str, timeout: int = 300) -> str:
    """
    Sends a structured mandate to Claude Code CLI.
    Returns the full output ledger as a string.
    """
    try:
        log.info(f"[CLAUDE CODE] Dispatching mandate ({len(mandate)} chars)")
        result = subprocess.run(
            [
                _CLAUDE_BIN,
                "-p",
                mandate,
                "--dangerously-skip-permissions"
            ],
            capture_output=True,
            text=True,
            cwd=str(MAF_ROOT),
            timeout=timeout,
            encoding="utf-8",
            errors="replace"
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(
                f"[CLAUDE CODE] CLI returned non-zero exit code {result.returncode}.\n"
                f"STDERR: {stderr}\n"
                f"Halting per CLAUDE_RULES.md Section 3.1."
            )
        ledger = result.stdout.strip()
        log.info(f"[CLAUDE CODE] Ledger received ({len(ledger)} chars)")
        return ledger if ledger else "LEDGER: Execution complete. No output returned."
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"[CLAUDE CODE] Mandate timed out after {timeout}s.\n"
            f"Halting per CLAUDE_RULES.md Section 3.1."
        )
    except FileNotFoundError:
        raise RuntimeError(
            "[CLAUDE CODE] Claude CLI not found. "
            "Ensure 'claude' is installed and on PATH.\n"
            "Install: npm install -g @anthropic-ai/claude-code"
        )
    except Exception as e:
        raise RuntimeError(
            f"[CLAUDE CODE] Unexpected error: {e}\n"
            f"Halting per CLAUDE_RULES.md Section 3.1."
        )


def test_connection() -> bool:
    """Tests that Claude Code CLI is operational."""
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
        return result.returncode == 0 and "BRIDGE OK" in result.stdout
    except Exception as e:
        log.error(f"[CLAUDE CODE] Connection test failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing Claude Code Client...")
    if test_connection():
        print("[OK] Claude Code Client is operational.")
    else:
        print("[FAIL] Claude Code Client failed.")
