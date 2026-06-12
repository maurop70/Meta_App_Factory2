"""
Budget Governor — per-run and per-day execution budgets
--------------------------------------------------------
Autonomy without metering is how a hallucination loop becomes an
invoice. Every loop run charges against:

  - per-run budget : iterations and wall-clock seconds
  - daily budget   : total executor dispatches across all runs

State: logs/budget_ledger.jsonl (one line per dispatch, replayed on
startup for the daily window). A tripped budget raises BudgetExceeded —
the loop engine converts that into an ESCALATE, never a silent stop.

Env overrides:
  CLAUDEAY_MAX_ITER_PER_RUN   (default 10)
  CLAUDEAY_MAX_SECS_PER_RUN   (default 1800)
  CLAUDEAY_MAX_DISPATCH_DAILY (default 60)
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

BUDGET_LOG = Path(__file__).parent / "logs" / "budget_ledger.jsonl"

MAX_ITER_PER_RUN   = int(os.getenv("CLAUDEAY_MAX_ITER_PER_RUN", "10"))
MAX_SECS_PER_RUN   = int(os.getenv("CLAUDEAY_MAX_SECS_PER_RUN", "1800"))
MAX_DISPATCH_DAILY = int(os.getenv("CLAUDEAY_MAX_DISPATCH_DAILY", "60"))


class BudgetExceeded(Exception):
    """Raised when a run or daily budget is exhausted."""


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _dispatches_today() -> int:
    if not BUDGET_LOG.exists():
        return 0
    today = _utc_today()
    count = 0
    try:
        for line in BUDGET_LOG.read_text(encoding="utf-8").splitlines():
            if line.strip() and f'"day": "{today}"' in line:
                count += 1
    except Exception:
        return 0
    return count


class RunBudget:
    """Tracks one loop run. Call charge() before every executor dispatch."""

    def __init__(self, trace_id: str,
                 max_iterations: int = MAX_ITER_PER_RUN,
                 max_seconds: int = MAX_SECS_PER_RUN):
        self.trace_id = trace_id
        self.max_iterations = max_iterations
        self.max_seconds = max_seconds
        self.started = time.monotonic()
        self.iterations = 0

    def charge(self) -> None:
        """Charge one dispatch. Raises BudgetExceeded when any cap trips."""
        self.iterations += 1
        elapsed = time.monotonic() - self.started

        if self.iterations > self.max_iterations:
            raise BudgetExceeded(
                f"run budget: {self.iterations} dispatches exceeds cap "
                f"{self.max_iterations} (trace {self.trace_id})")
        if elapsed > self.max_seconds:
            raise BudgetExceeded(
                f"run budget: {int(elapsed)}s elapsed exceeds cap "
                f"{self.max_seconds}s (trace {self.trace_id})")

        daily = _dispatches_today()
        if daily >= MAX_DISPATCH_DAILY:
            raise BudgetExceeded(
                f"daily budget: {daily} dispatches today reaches cap "
                f"{MAX_DISPATCH_DAILY} — operator must reset or wait for UTC rollover")

        try:
            BUDGET_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(BUDGET_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "day": _utc_today(),
                    "trace_id": self.trace_id,
                    "iteration": self.iterations,
                }) + "\n")
        except Exception:
            pass  # accounting failure must not block execution

    def snapshot(self) -> dict:
        return {
            "iterations": self.iterations,
            "max_iterations": self.max_iterations,
            "elapsed_s": int(time.monotonic() - self.started),
            "max_seconds": self.max_seconds,
            "dispatches_today": _dispatches_today(),
            "daily_cap": MAX_DISPATCH_DAILY,
        }


if __name__ == "__main__":
    b = RunBudget("selftest", max_iterations=2, max_seconds=9999)
    ok1 = ok2 = False
    try:
        b.charge(); b.charge()
        ok1 = True
    except BudgetExceeded:
        pass
    try:
        b.charge()
    except BudgetExceeded as e:
        ok2 = "run budget" in str(e)
    print(f"  [{'PASS' if ok1 else 'FAIL'}] two charges fit a 2-iteration budget")
    print(f"  [{'PASS' if ok2 else 'FAIL'}] third charge trips BudgetExceeded")
    print(f"\n{sum([ok1, ok2])}/2 passed")
