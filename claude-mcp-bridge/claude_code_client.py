"""
Claude Code Client — Primary Executor with Antigravity Fallback
---------------------------------------------------------------
Execution priority:
  1. Claude Code CLI (primary — direct local filesystem access)
  2. Antigravity API (fallback — when Claude quota exhausted)
Automatic failover: if Claude Code returns quota/rate-limit error,
falls through to Antigravity transparently.
"""

import json
import os
import sys
import shutil
import subprocess
import logging
from pathlib import Path

log = logging.getLogger("ClaudeCodeClient")

MAF_ROOT = Path(__file__).parent.parent.resolve()

MAX_ITERATIONS = 5  # Safety cap inherited from ay_client circuit breaker

# Structured CLI output: --output-format json gives us the ledger text plus
# session_id (for continuity) and cost telemetry in one parseable envelope.
USE_JSON_OUTPUT = os.getenv("CLAUDEAY_CLI_JSON", "true").lower() == "true"
# Session continuity: resume the same Claude Code session across loop
# iterations so the executor keeps its context instead of cold-starting.
RESUME_SESSIONS = os.getenv("CLAUDEAY_RESUME_SESSIONS", "true").lower() == "true"
# Optional model override for the executor (e.g. claude-sonnet-4-6).
EXECUTOR_MODEL = os.getenv("CLAUDEAY_EXECUTOR_MODEL", "").strip()

_last_session_id: str | None = None


def reset_session() -> None:
    """Forget the resumable session (call at the start of a new run)."""
    global _last_session_id
    _last_session_id = None

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


def _build_argv(perm_tier: int, workdir: str = "") -> list[str]:
    # Piece 4 (PreToolUse permit-hook): default-deny capability cap. The hook permits
    # ONLY the named tools/commands for this tier and denies everything else; it is
    # fail-closed. --dangerously-skip-permissions is retired. Tier 0 = read-only plan.
    # Piece 5: workdir is passed to the hook so Edit/Write outside it are denied.
    import sys as _sys, os as _os, json as _json, base64 as _b64
    _bridge = _os.path.dirname(_os.path.abspath(__file__))
    _hook = _os.path.join(_bridge, "executor_permit_hook.py")
    # workdir may be a single path OR a JSON array of subtrees (multi-subtree scope,
    # Phase 4). base64 it so its quotes/brackets survive the hook command argv intact;
    # the hook decodes it fail-closed.
    _wd = _b64.urlsafe_b64encode((workdir or "").encode("utf-8")).decode("ascii")
    _cmd = (f'"{_sys.executable}" "{_hook}" {int(perm_tier)} {_wd}').replace("\\", "/")
    _settings = _json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "*", "hooks": [{"type": "command", "command": _cmd}]}]}})
    _mode = "plan" if int(perm_tier) == 0 else "default"
    argv = [_CLAUDE_BIN, "-p", "--permission-mode", _mode, "--settings", _settings]
    if USE_JSON_OUTPUT:
        argv += ["--output-format", "json"]
    if EXECUTOR_MODEL:
        argv += ["--model", EXECUTOR_MODEL]
    if RESUME_SESSIONS and _last_session_id:
        argv += ["--resume", _last_session_id]
    return argv


def _send_via_claude_code(mandate: str, timeout: int, perm_tier: int = 0,
                          workdir: str = "") -> str:
    """Primary: Claude Code CLI execution. perm_tier selects the PreToolUse permit
    profile (piece 4); workdir confines the executor cwd + Edit/Write (piece 5)."""
    global _last_session_id
    # Mandate goes via stdin, not argv: argv would pass it through
    # cmd.exe (.cmd wrapper) where metacharacters mangle it, and
    # Windows caps the command line at ~32K chars.
    result = subprocess.run(
        _build_argv(perm_tier, workdir),
        input=mandate,
        capture_output=True,
        text=True,
        cwd=str(MAF_ROOT),   # confinement is enforced by the hook (multi-subtree), not cwd
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
        # A stale --resume id must not kill the run — retry once cold.
        if _last_session_id and ("resume" in stderr.lower()
                                 or "session" in stderr.lower()):
            log.warning("[CLAUDE CODE] resume failed — retrying without session")
            _last_session_id = None
            return _send_via_claude_code(mandate, timeout, perm_tier, workdir)
        raise RuntimeError(
            f"[CLAUDE CODE] Exit {result.returncode}: {stderr}\n"
            f"Halting per CLAUDE_RULES.md Section 3.1."
        )
    raw = result.stdout.strip()
    if USE_JSON_OUTPUT:
        try:
            envelope = json.loads(raw)
            _last_session_id = envelope.get("session_id") or _last_session_id
            cost = envelope.get("total_cost_usd")
            if cost is not None:
                log.info(f"[CLAUDE CODE] session={_last_session_id} "
                         f"cost=${cost:.4f}")
            ledger = (envelope.get("result") or "").strip()
            return ledger if ledger else "LEDGER: Execution complete."
        except (json.JSONDecodeError, AttributeError):
            log.warning("[CLAUDE CODE] JSON envelope unparseable — raw passthrough")
    return raw if raw else "LEDGER: Execution complete."


def _send_via_antigravity(mandate: str, timeout: int) -> str:
    """Fallback: Antigravity API execution."""
    log.warning(
        "[EXECUTOR] Claude quota exhausted — falling back to Antigravity"
    )
    from ay_client import send_mandate as ay_send
    return ay_send(mandate, timeout=timeout)


def send_mandate(mandate: str, timeout: int = 300, authorization=None,
                 plan_id: str | None = None) -> str:
    """
    Sends mandate to Claude Code CLI.
    Falls back to Antigravity if Claude quota is exhausted.
    Automatically returns to Claude Code on next call once available.

    plan_id (option c): when given, the token is authorized against this stable
    approved-PLAN identity rather than the per-iteration assembled mandate (which
    mutates every loop turn). One human approval thus scopes the whole multi-step
    build; the PreToolUse permit-hook (tier ceiling + workdir) is the wall on every
    tool call. plan_id=None ⇒ exact-byte binding (preserves the floor for any caller
    holding no plan token — those resolve to None ⇒ refused).
    """
    # ── Executor authorization gate (Phase 1 piece 4, Door A) ──
    # Mandate-bound (hash) + tier-capped. Door A capability tier = the operator-
    # approved ceiling (the whole plan was approved at that tier); the PreToolUse
    # permit-hook (piece 4) then caps what the executor PROCESS can do. Floor
    # unchanged: a None authorization is refused regardless of tier.
    import sys as _sys
    from pathlib import Path as _P
    _sys.path.insert(0, str(_P(__file__).parent))
    import executor_gate
    _tier = (authorization.tier_ceiling
             if isinstance(authorization, executor_gate.Authorization) else 3)
    _workdir = getattr(authorization, "workdir", "") or ""
    # Option (c): bind against the stable plan id when supplied; else exact-byte.
    _bind = plan_id if plan_id is not None else mandate
    _ok, _reason = executor_gate.authorize(authorization, _tier, mandate[:200],
                                           "claude_code_client.send_mandate", mandate_text=_bind)
    if not _ok:
        import json as _json
        return "LEDGER_JSON: " + _json.dumps({
            "status": "ERROR",
            "summary": f"Executor refused — {_reason}",
            "needs_human": "operator authorization required (Phase 1 tier-scoped key)",
        })

    # ── Primary: Claude Code ──────────────────────────────────────
    try:
        log.info(
            f"[EXECUTOR] Claude Code — dispatching mandate "
            f"({len(mandate)} chars)"
        )
        ledger = _send_via_claude_code(mandate, timeout, perm_tier=_tier, workdir=_workdir)
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
            [_CLAUDE_BIN, "-p", "--permission-mode", "plan"],   # read-only probe, not all-tools
            input="respond with exactly: BRIDGE OK",
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
