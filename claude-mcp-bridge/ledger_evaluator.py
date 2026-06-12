"""
Ledger Evaluator
----------------
Reads executor ledgers and decides:
  - COMPLETE: mandate succeeded, loop ends
  - ITERATE:  mandate partially succeeded, generate next mandate
  - ERROR:    mandate failed, trigger self-healing
  - ESCALATE: Tier 3 decision required, notify the operator

PRIMARY PATH (CLAUDE_RULES.md §14.1 — Structured Ledger Contract):
the executor ends every ledger with a machine-readable block:

  LEDGER_JSON: {"status": "...", "summary": "...", "files_changed": [...],
                "tests_run": [{"suite": "...", "passed": N, "failed": N}],
                "next_step": "...", "needs_human": "..."}

When that block parses, the executor's own declaration is authoritative
(confidence 0.95) — subject to internal consistency checks (failing tests
can never yield COMPLETE) and downstream Auditor verification.

FALLBACK PATH: ledgers without the block fall back to the legacy keyword
heuristics at capped confidence (≤0.5), which forces the loop engine to
treat them as unverified.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

log = logging.getLogger("LedgerEvaluator")


class LedgerStatus(Enum):
    COMPLETE  = "complete"
    ITERATE   = "iterate"
    ERROR     = "error"
    ESCALATE  = "escalate"


@dataclass
class LedgerResult:
    status: LedgerStatus
    confidence: float
    summary: str
    next_action: Optional[str] = None
    error_detail: Optional[str] = None
    structured: bool = False
    files_changed: list = field(default_factory=list)
    tests_run: list = field(default_factory=list)
    needs_human: Optional[str] = None


# ── Structured path ───────────────────────────────────────────────────────────

# The JSON object may span lines; grab from LEDGER_JSON: to the end of the
# balanced object. A simple greedy-to-last-brace works because the block is
# contractually the LAST thing in the ledger.
_LEDGER_JSON_RE = re.compile(
    r"LEDGER_JSON:\s*(\{.*\})\s*(?:```)?\s*$", re.DOTALL
)

_VALID_STATUSES = {"COMPLETE", "ITERATE", "ERROR", "ESCALATE"}


def _parse_structured(ledger: str) -> Optional[dict]:
    m = _LEDGER_JSON_RE.search(ledger.strip())
    if not m:
        return None
    raw = m.group(1)
    # Trim trailing fence/noise by retrying progressively shorter brace spans.
    for end in range(len(raw), 0, -1):
        if raw[end - 1] != "}":
            continue
        try:
            obj = json.loads(raw[:end])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _evaluate_structured(block: dict) -> LedgerResult:
    status_str = str(block.get("status", "")).strip().upper()
    if status_str not in _VALID_STATUSES:
        return None  # malformed — caller falls back to heuristics

    summary       = str(block.get("summary") or "")[:300]
    files_changed = block.get("files_changed") or []
    tests_run     = block.get("tests_run") or []
    next_step     = block.get("next_step") or None
    needs_human   = block.get("needs_human") or None

    # Consistency check 1: failing tests can never be COMPLETE.
    total_failed = 0
    for t in tests_run:
        try:
            total_failed += int(t.get("failed", 0))
        except (TypeError, ValueError, AttributeError):
            pass
    if status_str == "COMPLETE" and total_failed > 0:
        return LedgerResult(
            status=LedgerStatus.ERROR, confidence=0.95, structured=True,
            summary=f"Executor declared COMPLETE but reported {total_failed} "
                    f"failing test(s) — overridden to ERROR",
            error_detail=f"{total_failed} failing tests in declared-complete ledger",
            files_changed=files_changed, tests_run=tests_run,
        )

    # Consistency check 2: needs_human forces ESCALATE regardless of status.
    if needs_human and status_str != "ESCALATE":
        status_str = "ESCALATE"
        summary = f"needs_human set: {needs_human}"

    status = LedgerStatus[status_str]
    return LedgerResult(
        status=status, confidence=0.95, structured=True,
        summary=summary or f"Executor declared {status_str}",
        next_action=next_step,
        error_detail=summary if status == LedgerStatus.ERROR else None,
        files_changed=files_changed, tests_run=tests_run,
        needs_human=needs_human,
    )


# ── Legacy heuristic fallback (capped confidence) ─────────────────────────────

COMPLETE_SIGNALS = [
    "fully operational", "task complete", "no further action",
    "successfully", "sealed", "pushed to dev", "exit code 0",
    "all verifications passed", "bridge ok", "ledger ok",
    "tests passed", "0 errors", "clean compilation"
]

ERROR_SIGNALS = [
    "traceback", "exception", "error:", "failed:", "halting",
    "circuit breaker", "anomal", "[halt", "exit code 1",
    "exit code 2", "syntaxerror", "importerror", "runtimeerror"
]

ESCALATE_SIGNALS = [
    "merge to main", "new child app", "section 11",
    "irreversible", "needs operator", "requires approval",
]

ITERATE_SIGNALS = [
    "partial", "incomplete", "next step", "remaining",
    "todo", "fixme", "not yet", "still needs", "follow up"
]

# Heuristic results can never exceed this confidence: the loop engine
# treats sub-0.5 COMPLETE as unverified and forces a verification pass.
_HEURISTIC_CONFIDENCE_CAP = 0.5


def _evaluate_heuristic(ledger: str) -> LedgerResult:
    ledger_lower = ledger.lower()

    escalate_score = sum(1 for s in ESCALATE_SIGNALS if s in ledger_lower)
    error_score    = sum(1 for s in ERROR_SIGNALS    if s in ledger_lower)
    complete_score = sum(1 for s in COMPLETE_SIGNALS if s in ledger_lower)
    iterate_score  = sum(1 for s in ITERATE_SIGNALS  if s in ledger_lower)

    cap = _HEURISTIC_CONFIDENCE_CAP

    if escalate_score > 0:
        return LedgerResult(
            status=LedgerStatus.ESCALATE,
            confidence=min(cap, escalate_score / 6),
            summary=f"[heuristic] escalation signals detected ({escalate_score})",
            next_action="Notify operator and await approval",
        )

    if error_score > complete_score:
        error_lines = [
            line for line in ledger.split('\n')
            if any(s in line.lower() for s in ERROR_SIGNALS)
        ]
        return LedgerResult(
            status=LedgerStatus.ERROR,
            confidence=min(cap, error_score / 10),
            summary=f"[heuristic] execution errors detected ({error_score} signals)",
            error_detail=error_lines[0] if error_lines else "See ledger",
            next_action="Trigger self-healing",
        )

    if complete_score > 0:
        return LedgerResult(
            status=LedgerStatus.COMPLETE,
            confidence=min(cap, complete_score / 10),
            summary=f"[heuristic] completion signals ({complete_score}) — UNVERIFIED, "
                    f"no LEDGER_JSON block",
        )

    if iterate_score > 0:
        return LedgerResult(
            status=LedgerStatus.ITERATE,
            confidence=min(cap, iterate_score / 6),
            summary=f"[heuristic] partial completion ({iterate_score} signals)",
            next_action="Generate follow-up mandate",
        )

    return LedgerResult(
        status=LedgerStatus.COMPLETE,
        confidence=0.2,
        summary="[heuristic] ambiguous ledger, no LEDGER_JSON block — "
                "assumed complete at low confidence",
    )


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate(ledger: str) -> LedgerResult:
    """
    Evaluate a ledger. Structured LEDGER_JSON block is authoritative;
    prose-only ledgers fall back to capped-confidence heuristics.
    """
    if not ledger or not ledger.strip():
        return LedgerResult(
            status=LedgerStatus.ERROR,
            confidence=1.0,
            summary="Empty ledger — executor produced no output",
            error_detail="Empty ledger",
        )

    block = _parse_structured(ledger)
    if block is not None:
        result = _evaluate_structured(block)
        if result is not None:
            return result
        log.warning("[EVALUATOR] LEDGER_JSON present but malformed — heuristic fallback")

    return _evaluate_heuristic(ledger)


def evaluate_and_log(ledger: str, mandate_id: str = "") -> LedgerResult:
    """Evaluates ledger and logs the result."""
    result = evaluate(ledger)
    log.info(
        f"[EVALUATOR] {mandate_id} → {result.status.value} "
        f"(confidence: {result.confidence:.0%}, "
        f"{'structured' if result.structured else 'heuristic'}) — {result.summary}"
    )
    return result
