"""
PreToolUse permit-hook (Phase 1 piece 4) — DEFAULT-DENY capability cap.
----------------------------------------------------------------------
Claude Code runs this before every tool call (PreToolUse). It permits ONLY the
tools/commands named for the operator-approved tier (argv[1]) and denies everything
else. Proven to bind on CLI 2.1.195 where the allow-list flag did not.

FAIL-CLOSED by construction: any error, malformed input, missing/invalid tier, or
unimportable permit data => DENY. A cap that's only safe when healthy is a trapdoor;
every failure path here lands on deny.
"""
import json
import os
import sys
from datetime import datetime, timezone


def _log(decision: str, tool: str, tier, reason: str) -> None:
    """Record every decision (the proof artifact). Never breaks fail-closed."""
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "logs", "executor_permit_decisions.jsonl")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                                "tier": tier, "tool": tool,
                                "decision": decision, "reason": reason[:160]}) + "\n")
    except Exception:
        pass


def _emit(decision: str, reason: str = "", tool: str = "", tier="") -> None:
    _log(decision, tool, tier, reason)
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason[:200],
    }}))


def _deny(reason: str, tool: str = "", tier="") -> None:
    _emit("deny", reason, tool, tier)
    sys.exit(0)


def main() -> None:
    # Tier from argv — fail-closed to the most restrictive tier on anything odd.
    try:
        tier = int(sys.argv[1])
        if tier not in (0, 1, 2, 3):
            tier = 0
    except Exception:
        tier = 0
    # workdir arrives base64-encoded (it may be a JSON array of subtrees whose quotes
    # would otherwise break the hook command argv). Decode fail-closed.
    workdir = ""
    if len(sys.argv) > 2 and sys.argv[2]:
        try:
            import base64
            workdir = base64.urlsafe_b64decode(sys.argv[2].encode("ascii")).decode("utf-8")
        except Exception:
            _deny("malformed workdir scope (base64) — fail-closed", "", tier)

    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        _deny("malformed hook input", "", tier)

    tool_name = data.get("tool_name") or data.get("toolName") or ""
    tool_input = data.get("tool_input") or data.get("toolInput") or {}

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import executor_permissions as ep
        allowed, reason = ep.tool_permitted(tool_name, tool_input, tier, workdir)
    except Exception as exc:
        _deny(f"hook error (fail-closed): {exc}", tool_name, tier)

    if allowed:
        _emit("allow", "permitted", tool_name, tier)
    else:
        _deny(reason, tool_name, tier)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:           # last-resort fail-closed
        _deny(f"hook crashed (fail-closed): {exc}")
