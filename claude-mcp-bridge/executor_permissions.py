"""
Executor permit profiles (Phase 1 piece 4) — TRUE allow-list, enforced by the
PreToolUse hook (executor_permit_hook.py). DEFAULT-DENY: the hook permits ONLY the
named tools/commands for the operator-approved tier and denies everything else —
including arbitrary `python script.py` (Bash is permitted only for named command
prefixes). The flag-form allow-list and the settings allow-list were both proven
NOT to bind on this CLI (2.1.195); the PreToolUse hook was proven to bind.

GUARD FILES are write-protected at EVERY tier including Tier 3 — the executor
cannot file off its own shackles. The hook and this file are themselves guard
files: a cap the executor could edit or delete is not a cap.
"""
import re

# ── Guard files: never Edit/Write at any tier (delete is impossible too — `rm`
#    is on no permit list). Includes the hook + this file (self-protection). ──
#
# DERIVED, NOT HAND-PICKED. The set is the enforcement path itself: every file the
# live capability path reads/calls to REFUSE, MINT, CLASSIFY, CONFINE, or DISPATCH.
# The item-2 failure (a tier-1 in-workdir build could rewrite the classifier and the
# hook allowed it) was a control-plane file nobody had listed. So the rule, not a
# memory list, decides membership. Import/call trace that produced this set:
#   refuse   : executor_gate.authorize · executor_permit_hook → executor_permissions
#              (_within/tool_permitted) · *_wire.py (per-action authorize) ·
#              loop_engine (drift-HALT gate)
#   mint     : executor_gate.mint ← approval_gate.request_approval · loop_engine (the
#              one plan-scoped mint)
#   classify : mandate_tiers.classify_tier / classify_action ← loop_engine, the wires
#   confine  : executor_permissions._within · workdir computed in loop_engine and
#              threaded via claude_code_client._build_argv (installs the hook)
#   dispatch : claude_code_client.send_mandate / _send_via_claude_code (primary) ·
#              ay_client.send_mandate (FALLBACK executor — trace-surfaced; the hand
#              list missed it)
# NOT guarded (build-prompt only, hold no hard cap; option-c token binds plan_id, not
# their output): dispatcher.py, ledger_evaluator.py. Add here only if they ever gain
# a refuse/mint/classify/confine/dispatch role.
GUARD_BASENAMES = {
    ".env", "executor_gate.py", "executor_permit_hook.py", "executor_permissions.py",
    "deploy_maf.py", "deploy_erp.py", "deploy_edge.py",
    # control plane (derived above) — the wall must not be able to edit itself:
    "mandate_tiers.py",        # classify
    "claude_code_client.py",   # dispatch + authorize call-site + installs the hook
    "approval_gate.py",        # mint path
    "loop_engine.py",          # drift-HALT gate + the one plan-scoped mint + dispatch
    "ay_client.py",            # FALLBACK dispatcher (trace-surfaced; hand list missed)
}

def is_guard_path(path: str) -> bool:
    base = str(path or "").replace("\\", "/").rstrip("/").split("/")[-1].lower()
    return base in GUARD_BASENAMES or base.endswith("_wire.py")

# ── Permitted TOOLS per tier ──
PERMIT_TOOLS = {
    0: {"Read", "Glob", "Grep", "LS"},                       # Tier 0: Bash-free, read-only
    1: {"Read", "Glob", "Grep", "LS", "Edit", "Write", "Bash"},
    2: {"Read", "Glob", "Grep", "LS", "Edit", "Write", "Bash"},
    3: {"Read", "Glob", "Grep", "LS", "Edit", "Write", "Bash"},
}
# NOTE: the Bash TOOL is permitted at build tiers, but bash_permitted() gates WHICH
# commands (named prefixes only) — so arbitrary `python x.py` / ssh / rm are still
# denied. Tier 0 omits Bash entirely (read-only).

# ── Permitted Bash COMMAND PREFIXES per tier (single command, no chaining) ──
_BASH1 = ["pytest", "python -m pytest", "npm test", "npm run test", "npx playwright test",
          "ls", "cat", "echo", "mkdir", "git status", "git diff"]
_BASH2 = _BASH1 + ["git add", "git commit", "git push"]
_BASH3 = _BASH2 + ["python deploy_maf.py", "python deploy_erp.py", "python deploy_edge.py",
                   "ssh", "systemctl"]
PERMIT_BASH = {0: [], 1: _BASH1, 2: _BASH2, 3: _BASH3}

# Reuse the piece-2 chaining/substitution guard so a permitted prefix can't be
# chained around (e.g. "pytest && rm -rf /").
_SHELL_METACHARS = re.compile(r"[&;|`\n<>]|\$\(")


def bash_permitted(command: str, tier: int) -> bool:
    c = (command or "").strip()
    if not c or _SHELL_METACHARS.search(c):
        return False                                  # chaining/substitution => deny
    cl = c.lower()
    # Tier 2 may push/commit but NOT to main (Tier 3 deploy may).
    if tier == 2 and re.match(r"git\s+(push|merge)\b", cl) and "main" in cl:
        return False
    return any(cl.startswith(p) for p in PERMIT_BASH.get(int(tier), []))


def _within(path: str, workdir: str) -> bool:
    """True iff path resolves INSIDE workdir. realpath+commonpath handles
    ..-traversal, sibling-prefix (/work vs /work-evil), and symlinks. Fail-closed
    (deny) on any error, including cross-drive paths on Windows."""
    import os
    try:
        p = os.path.realpath(path)
        w = os.path.realpath(workdir)
        return os.path.commonpath([p, w]) == w
    except Exception:
        return False


def tool_permitted(tool_name: str, tool_input: dict, tier: int, workdir: str = "") -> tuple:
    """Return (allowed: bool, reason: str). Default-DENY for anything unrecognized."""
    tier = int(tier)
    if tool_name not in PERMIT_TOOLS.get(tier, set()):
        return False, f"tool {tool_name!r} not permitted at tier {tier}"
    if tool_name == "Bash":
        cmd = (tool_input or {}).get("command", "")
        if not bash_permitted(cmd, tier):
            return False, f"bash command not on the tier-{tier} permit list: {cmd[:80]!r}"
    if tool_name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = (tool_input or {}).get("file_path") or (tool_input or {}).get("path") or ""
        if is_guard_path(path):
            return False, f"guard file is write-protected at all tiers: {path}"
        if workdir and not _within(path, workdir):
            return False, f"write outside declared workdir {workdir}: {path}"
    return True, "permitted"
