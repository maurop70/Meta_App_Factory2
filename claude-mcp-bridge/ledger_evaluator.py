"""
Ledger Evaluator
----------------
Reads Claude Code execution ledgers and decides:
  - COMPLETE: mandate succeeded, loop ends
  - ITERATE:  mandate partially succeeded, generate next mandate
  - ERROR:    mandate failed, trigger self-healing
  - ESCALATE: Section 11 decision required, notify Mauro
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

log = logging.getLogger("LedgerEvaluator")


class LedgerStatus(Enum):
    COMPLETE  = "complete"
    ITERATE   = "iterate"
    ERROR     = "error"
    ESCALATE  = "escalate"


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
    "deploy", "merge to main", "delete", "new child app",
    "business logic", "section 11", "irreversible"
]

ITERATE_SIGNALS = [
    "partial", "incomplete", "next step", "remaining",
    "todo", "fixme", "not yet", "still needs", "follow up"
]


@dataclass
class LedgerResult:
    status: LedgerStatus
    confidence: float
    summary: str
    next_action: Optional[str] = None
    error_detail: Optional[str] = None


def evaluate(ledger: str) -> LedgerResult:
    """
    Evaluates a ledger string and returns a structured result.
    Decision priority: ESCALATE > ERROR > COMPLETE > ITERATE
    """
    if not ledger or not ledger.strip():
        return LedgerResult(
            status=LedgerStatus.ERROR,
            confidence=1.0,
            summary="Empty ledger — executor produced no output",
            error_detail="Empty ledger"
        )

    ledger_lower = ledger.lower()

    escalate_score = sum(1 for s in ESCALATE_SIGNALS if s in ledger_lower)
    error_score    = sum(1 for s in ERROR_SIGNALS    if s in ledger_lower)
    complete_score = sum(1 for s in COMPLETE_SIGNALS if s in ledger_lower)
    iterate_score  = sum(1 for s in ITERATE_SIGNALS  if s in ledger_lower)

    log.debug(
        f"[EVALUATOR] Scores — escalate:{escalate_score} "
        f"error:{error_score} complete:{complete_score} "
        f"iterate:{iterate_score}"
    )

    if escalate_score > 0:
        return LedgerResult(
            status=LedgerStatus.ESCALATE,
            confidence=min(1.0, escalate_score / 3),
            summary=f"Section 11 trigger detected ({escalate_score} signals)",
            next_action="Notify Mauro and await approval"
        )

    if error_score > complete_score:
        error_lines = [
            line for line in ledger.split('\n')
            if any(s in line.lower() for s in ERROR_SIGNALS)
        ]
        return LedgerResult(
            status=LedgerStatus.ERROR,
            confidence=min(1.0, error_score / 5),
            summary=f"Execution errors detected ({error_score} signals)",
            error_detail=error_lines[0] if error_lines else "See ledger",
            next_action="Trigger self-healing via PhantomSRE"
        )

    if complete_score > 0:
        return LedgerResult(
            status=LedgerStatus.COMPLETE,
            confidence=min(1.0, complete_score / 5),
            summary=f"Mandate completed successfully ({complete_score} signals)",
        )

    if iterate_score > 0:
        return LedgerResult(
            status=LedgerStatus.ITERATE,
            confidence=min(1.0, iterate_score / 3),
            summary=f"Partial completion — iteration needed ({iterate_score} signals)",
            next_action="Generate follow-up mandate"
        )

    return LedgerResult(
        status=LedgerStatus.COMPLETE,
        confidence=0.3,
        summary="Ambiguous ledger — assumed complete (low confidence)",
    )


def evaluate_and_log(ledger: str, mandate_id: str = "") -> LedgerResult:
    """Evaluates ledger and logs the result."""
    result = evaluate(ledger)
    log.info(
        f"[EVALUATOR] {mandate_id} → {result.status.value} "
        f"(confidence: {result.confidence:.0%}) — {result.summary}"
    )
    return result
