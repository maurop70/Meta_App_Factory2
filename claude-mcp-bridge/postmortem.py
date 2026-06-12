"""
Postmortem Engine — CLAUDE_RULES.md §13.2
------------------------------------------
After every ERROR or ESCALATE run outcome, draft a prevention rule and
queue it for OPERATOR approval. Rules never enter CLAUDE_RULES.md
without a human in the loop — this is the rule-poisoning defense.

Queue: rules/pending_rules.jsonl
  {ts, trace_id, root_cause, proposed_rule, status: pending|approved|rejected}

Approval CLI:
  python postmortem.py list               — show pending proposals
  python postmortem.py approve <n>        — append proposal n to CLAUDE_RULES.md
  python postmortem.py reject  <n>        — mark proposal n rejected

Deduplication: a proposal whose root_cause token-overlaps an existing
pending/approved proposal above 0.6 is dropped (CLAUDE_RULES 13.2:
check for an existing rule before proposing a duplicate).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BRIDGE_ROOT   = Path(__file__).parent
PENDING_RULES = BRIDGE_ROOT / "rules" / "pending_rules.jsonl"
RULES_PATH    = BRIDGE_ROOT / "rules" / "CLAUDE_RULES.md"


def _load_queue() -> list[dict]:
    if not PENDING_RULES.exists():
        return []
    entries = []
    for line in PENDING_RULES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _save_queue(entries: list[dict]) -> None:
    PENDING_RULES.parent.mkdir(parents=True, exist_ok=True)
    with open(PENDING_RULES, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _similar(a: str, b: str) -> float:
    ta, tb = set(a.lower().split()), set(b.lower().split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def propose_rule(trace_id: str, root_cause: str, proposed_rule: str,
                 source: str = "postmortem") -> bool:
    """
    Queue a rule proposal. Returns False when a near-duplicate exists.
    Never raises — the postmortem path must not break the loop.
    """
    try:
        queue = _load_queue()
        for e in queue:
            if e.get("status") in ("pending", "approved") and \
               _similar(root_cause, e.get("root_cause", "")) > 0.6:
                return False
        queue.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "source": source,
            "root_cause": root_cause[:500],
            "proposed_rule": proposed_rule[:1500],
            "status": "pending",
        })
        _save_queue(queue)
        return True
    except Exception:
        return False


def draft_from_failure(trace_id: str, instruction: str,
                       error_detail: str, ledger_excerpt: str = "") -> bool:
    """
    Mechanical postmortem draft from a failed run. The Architect (or the
    operator) refines wording at approval time; the draft captures the
    facts while they are fresh.
    """
    root_cause = f"Run failed on: {instruction[:160]} | error: {error_detail[:200]}"
    proposed = (
        f"[PROPOSED {datetime.now(timezone.utc).strftime('%Y-%m-%d')} "
        f"trace={trace_id}] When executing mandates like '{instruction[:120]}', "
        f"guard against: {error_detail[:200]}. "
        f"(Draft from postmortem engine — refine before approval. "
        f"Ledger excerpt: {ledger_excerpt[:200]})"
    )
    return propose_rule(trace_id, root_cause, proposed)


# ── Operator CLI ──────────────────────────────────────────────────────────────

def _cli_list() -> None:
    queue = _load_queue()
    pending = [(i, e) for i, e in enumerate(queue) if e.get("status") == "pending"]
    if not pending:
        print("No pending rule proposals.")
        return
    for i, e in pending:
        print(f"\n[{i}] {e['ts'][:19]}  trace={e.get('trace_id','?')}  src={e.get('source','?')}")
        print(f"    cause: {e.get('root_cause','')[:160]}")
        print(f"    rule : {e.get('proposed_rule','')[:300]}")


def _cli_approve(idx: int) -> None:
    queue = _load_queue()
    if idx < 0 or idx >= len(queue) or queue[idx].get("status") != "pending":
        print(f"No pending proposal at index {idx}.")
        return
    e = queue[idx]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    section = (
        f"\n\n## [APPROVED RULE {stamp}] (provenance: trace={e.get('trace_id','?')}, "
        f"source={e.get('source','?')}, approved by operator)\n"
        f"{e['proposed_rule']}\n"
    )
    with open(RULES_PATH, "a", encoding="utf-8") as f:
        f.write(section)
    e["status"] = "approved"
    e["approved_ts"] = datetime.now(timezone.utc).isoformat()
    _save_queue(queue)
    print(f"Approved and appended to {RULES_PATH.name}.")


def _cli_reject(idx: int) -> None:
    queue = _load_queue()
    if idx < 0 or idx >= len(queue) or queue[idx].get("status") != "pending":
        print(f"No pending proposal at index {idx}.")
        return
    queue[idx]["status"] = "rejected"
    queue[idx]["rejected_ts"] = datetime.now(timezone.utc).isoformat()
    _save_queue(queue)
    print("Rejected.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "list":
        _cli_list()
    elif args[0] == "approve" and len(args) > 1:
        _cli_approve(int(args[1]))
    elif args[0] == "reject" and len(args) > 1:
        _cli_reject(int(args[1]))
    else:
        print("Usage: python postmortem.py [list | approve <n> | reject <n>]")
