"""
Autonomous Loop Engine
----------------------
Orchestrates the Architect ↔ Executor loop with the full SOTA stack:

  1. Receives user intent (plain English)
  2. Risk-tier classification on the INSTRUCTION (mandate_tiers, §15)
     — Tier 3 requires operator approval BEFORE dispatch
  3. Telemetry (allowlist-filtered) + episodic recall + scoped rules
     are assembled by the dispatcher into a mandate
  4. Budget charge (budget.py) — BudgetExceeded becomes ESCALATE
  5. Executor runs mandate (Claude Code primary, Antigravity fallback)
  6. Structured LEDGER_JSON evaluation (ledger_evaluator, §14.1)
  7. Auditor verifies COMPLETE claims against ground truth (auditor.py)
  8. ERROR outcomes draft postmortem rules (postmortem.py, §13.2)
  9. Every run is checkpointed (logs/loop_runs/{trace_id}.json) and
     recorded as an episode (episodic_memory.py, §13.4)
"""

import json
import os
import sys
import asyncio
import threading
import uuid
from pathlib import Path
from datetime import datetime, timezone

# Add bridge root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from claude_code_client import send_mandate
except ImportError:
    from ay_client import send_mandate  # fallback
from dispatcher import AntigravityDispatcher
from ledger_evaluator import evaluate_and_log, LedgerResult, LedgerStatus
from mandate_tiers import classify_tier
from budget import RunBudget, BudgetExceeded
from episodic_memory import record_episode
import postmortem
import auditor

BRIDGE_ROOT   = Path(__file__).parent
RULES_PATH    = BRIDGE_ROOT / "rules" / "CLAUDE_RULES.md"
TELEMETRY_LOG = BRIDGE_ROOT / "logs" / "telemetry.jsonl"
LOOP_LOG      = BRIDGE_ROOT / "logs" / "loop_history.jsonl"
RUNS_DIR      = BRIDGE_ROOT / "logs" / "loop_runs"

dispatcher = AntigravityDispatcher(rules_path=RULES_PATH)

# ── Shared state for web-driven loop approval signalling ──────────────────
loop_status_buffer: list = []
_approval_event = threading.Event()
_approval_response: list = [""]

# ── Interactive Planner gate ───────────────────────────────────────────────
# always : draft + approve a plan before every run (architect default)
# tier2  : only for runs classified Tier >= 2 (version control and above)
# off    : no planning gate
PLAN_APPROVAL_ENV = "CLAUDEAY_PLAN_APPROVAL"
MAX_PLAN_REVISIONS = 3


def _plan_gate_needed(user_intent: str, web_mode: bool) -> bool:
    """
    Decide whether the interactive planning gate applies to this run.
    Headless runs (no terminal, not web-driven) skip the gate LOUDLY:
    nothing would ever answer the approval prompt — blocking would
    deadlock the thread (the web approval event is only serviced by
    operator-facing surfaces).
    """
    mode = os.getenv(PLAN_APPROVAL_ENV, "always").strip().lower()
    if mode == "off":
        return False
    if mode == "tier2" and classify_tier(user_intent).tier < 2:
        return False
    has_operator_channel = web_mode or (sys.stdin is not None and sys.stdin.isatty())
    if not has_operator_channel:
        # Plain ASCII: this branch runs in piped/headless contexts (cp1252-safe)
        print("[PLANNER] WARNING: no operator channel (headless run) - plan "
              "approval gate SKIPPED. Set CLAUDEAY_PLAN_APPROVAL=off to silence.")
        return False
    return True


def _is_local_url(url: str) -> bool:
    """Allowlist: only events from monitored local origins count."""
    return not url or any(h in url for h in ("localhost", "127.0.0.1", "::1"))


def load_recent_telemetry(n: int = 20) -> dict:
    """
    Load the most recent N telemetry events from monitored origins only.
    External-tab noise (Gmail, Sentry, arbitrary sites) is excluded — the
    same filter auto_trigger and autonomy_trigger apply, applied here too.
    """
    if not TELEMETRY_LOG.exists():
        return {"critical_events": [], "other": [], "total_events": 0}
    events = []
    try:
        with open(TELEMETRY_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except Exception:
        return {"critical_events": [], "other": [], "total_events": 0}
    recent = [e for e in events[-n * 3:] if _is_local_url(e.get("url", ""))][-n:]
    critical = [e for e in recent if e.get("type") in
                ("console_error", "page_error", "request_failed")]
    return {
        "critical_events": critical,
        "other": [e for e in recent if e not in critical],
        "total_events": len(recent)
    }


def read_code_context(files: list[str]) -> dict[str, str]:
    """Read specified files from the MAF repo for code context."""
    maf_root = BRIDGE_ROOT.parent
    context = {}
    for filepath in files:
        full_path = maf_root / filepath
        if full_path.exists():
            try:
                context[filepath] = full_path.read_text(encoding="utf-8")
            except Exception as e:
                context[filepath] = f"[Could not read: {e}]"
        else:
            context[filepath] = "[FILE NOT FOUND]"
    return context


def requires_user_input(instruction: str) -> str | None:
    """
    Tier-3 gate on the INSTRUCTION text (never the rule-injected mandate —
    the legacy version scanned the full prompt and false-positived on the
    rules themselves). Returns the gate reason, or None when safe.
    """
    tier = classify_tier(instruction)
    if tier.requires_human:
        return ", ".join(tier.reasons) or "tier 3"
    return None


def log_loop_event(event_type: str, content: str, trace_id: str = ""):
    """Persist loop events for audit trail."""
    LOOP_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace_id,
        "type": event_type,
        "content": content[:2000]  # truncate for log
    }
    with open(LOOP_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


class AutonomousLoop:

    MAX_ITERATIONS = 10  # kept for back-compat; enforced via RunBudget

    def __init__(self, web_mode: bool = False):
        self.iteration = 0
        self.task_complete = False
        self.context_files: list[str] = []
        self.web_mode = web_mode
        self.trace_id = str(uuid.uuid4())[:8]
        self._tier3_authorized_for: str | None = None
        self._history: list[dict] = []

    # ── Checkpointing ──────────────────────────────────────────────────────

    def _checkpoint(self, status: str, summary: str = ""):
        try:
            RUNS_DIR.mkdir(parents=True, exist_ok=True)
            state = {
                "trace_id": self.trace_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "iteration": self.iteration,
                "status": status,
                "summary": summary[:300],
                "history": self._history[-20:],
            }
            (RUNS_DIR / f"{self.trace_id}.json").write_text(
                json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ── Operator interaction ──────────────────────────────────────────────

    def _await_directive(self, prompt_msg: str) -> str:
        """
        Block until the operator responds. Web mode: event-driven wait on
        _approval_event (no busy-poll). Terminal mode: stdin input().

        Course correction contract: any response that is not an approval
        ("yes"/"approve"/...) or a stop word is treated by callers as a
        STRUCTURAL MODIFICATION — it replaces or amends the loop's active
        instruction instead of halting the run.
        """
        loop_status_buffer.append({"type": "approval_required", "msg": prompt_msg})
        # Deadlock guard: input() in a non-tty context blocks forever, so any
        # run without a real terminal goes through the web approval event.
        if self.web_mode or sys.stdin is None or not sys.stdin.isatty():
            _approval_event.wait()
            _approval_event.clear()
            return _approval_response[0].strip()
        print(f"\n[ARCHITECT] ⏸ {prompt_msg}")
        return input("Your decision: ").strip()

    # ── Interactive Planner (upfront plan approval + revision loop) ───────

    def _draft_plan(self, user_intent: str, feedback: str = "") -> str:
        """Draft an implementation plan via the model router (Tier 0 call —
        not an executor dispatch, so it is not charged to the run budget)."""
        try:
            maf_root = str(BRIDGE_ROOT.parent)
            if maf_root not in sys.path:
                sys.path.insert(0, maf_root)
            from model_router import route
            prompt = (
                "Draft a concise implementation plan for this mandate in the "
                f"Meta App Factory codebase:\n\n{user_intent}\n"
                + (f"\nOperator feedback on the previous draft — incorporate it:"
                   f"\n{feedback}\n" if feedback else "")
                + "\nFormat: numbered steps, files to touch, risks, and a final "
                  "VERIFICATION section. Under 30 lines. Plain text."
            )
            plan = route("implementation_plan", prompt)
            return plan or "[planner unavailable — no model produced a draft]"
        except Exception as e:
            return f"[planner error: {str(e)[:160]}]"

    def _planning_phase(self, user_intent: str) -> str | None:
        """
        Draft → print → await approval. Non-approval, non-stop input is plan
        FEEDBACK: the plan is redrafted with it (course correction before any
        execution). Returns the approved intent, or None when the operator
        stops the run.
        """
        feedback = ""
        for revision in range(MAX_PLAN_REVISIONS):
            plan = self._draft_plan(user_intent, feedback)
            try:
                RUNS_DIR.mkdir(parents=True, exist_ok=True)
                (RUNS_DIR / f"{self.trace_id}_plan.md").write_text(
                    plan, encoding="utf-8")
            except Exception:
                pass
            print(f"\n[PLANNER] ── Draft plan (revision {revision + 1}) "
                  f"──────────\n{plan}\n")
            log_loop_event("PLAN_DRAFTED", plan, self.trace_id)
            directive = self._await_directive(
                "Plan drafted — 'yes' to approve, 'stop' to abort, or type "
                "feedback to revise")
            low = directive.lower()
            if low in ("yes", "y", "approve", "approved", "go", "proceed", ""):
                log_loop_event("PLAN_APPROVED", f"revision {revision + 1}",
                               self.trace_id)
                return user_intent
            if low in ("stop", "halt", "abort", "no"):
                return None
            feedback = directive
            log_loop_event("PLAN_FEEDBACK", directive, self.trace_id)
        print(f"[PLANNER] {MAX_PLAN_REVISIONS} revisions without approval — halting.")
        return None

    # ── Main loop ─────────────────────────────────────────────────────────

    def run(self, user_intent: str):
        """
        Main entry point. Runs the Architect↔Executor loop for a given
        user intent. Blocks until complete, escalated, or out of budget.
        """
        print(f"\n[ARCHITECT] Received intent: {user_intent} "
              f"(trace {self.trace_id})")
        log_loop_event("USER_INTENT", user_intent, self.trace_id)
        self._checkpoint("started", user_intent)
        try:
            from claude_code_client import reset_session
            reset_session()  # fresh executor session per run; iterations resume it
        except ImportError:
            pass

        # ── Interactive Planner gate (CLAUDEAY_PLAN_APPROVAL) ─────────────
        if _plan_gate_needed(user_intent, self.web_mode):
            approved_intent = self._planning_phase(user_intent)
            if approved_intent is None:
                log_loop_event("PLAN_REJECTED", user_intent, self.trace_id)
                self._checkpoint("halted", "operator rejected plan")
                record_episode(self.trace_id, user_intent, "halted",
                               "operator rejected plan at planning gate",
                               tags=["halted", "plan_rejected"])
                print("\n[ARCHITECT] Run aborted at planning gate.")
                return
            user_intent = approved_intent

        budget = RunBudget(self.trace_id, max_iterations=self.MAX_ITERATIONS)
        current_instruction = user_intent
        final_status, final_summary = "halted", ""

        while not self.task_complete:
            self.iteration += 1
            print(f"\n[ARCHITECT] ── Iteration {self.iteration} "
                  f"(trace {self.trace_id}) ──────────────")

            # 1. Tier gate — on the instruction, BEFORE building the mandate
            if current_instruction != self._tier3_authorized_for:
                gate_reason = requires_user_input(current_instruction)
                if gate_reason:
                    directive = self._await_directive(
                        f"Tier 3 action requires approval ({gate_reason}): "
                        f"{current_instruction[:200]}")
                    log_loop_event("TIER3_DIRECTIVE", directive, self.trace_id)
                    if not directive or directive.lower() in ("stop", "halt", "abort", "no"):
                        final_status, final_summary = "halted", f"operator declined: {gate_reason}"
                        break
                    if directive.lower() in ("yes", "approve", "approved", "go", "proceed"):
                        # Same instruction, now operator-authorized
                        self._tier3_authorized_for = current_instruction
                        current_instruction = (
                            f"{current_instruction}\n\n[OPERATOR AUTHORIZATION "
                            f"GRANTED for this Tier 3 action — trace {self.trace_id}]")
                        self._tier3_authorized_for = current_instruction
                    else:
                        current_instruction = directive
                        continue

            # 2. Budget charge
            try:
                budget.charge()
            except BudgetExceeded as be:
                loop_status_buffer.append({"type": "escalate", "msg": str(be)})
                log_loop_event("BUDGET_EXCEEDED", str(be), self.trace_id)
                print(f"[LOOP] 💸 {be}")
                final_status, final_summary = "escalate", str(be)
                break

            # 3. Load telemetry (allowlist-filtered)
            telemetry = load_recent_telemetry()
            if telemetry["critical_events"]:
                print(f"[TELEMETRY] ⚠ {len(telemetry['critical_events'])} "
                      f"critical events detected")

            # 4. Build mandate (scoped rules + untrusted telemetry + episodes)
            code_context = (read_code_context(self.context_files)
                           if self.context_files else None)
            mandate = dispatcher.build_prompt(
                instruction=current_instruction,
                telemetry=telemetry if telemetry["total_events"] > 0 else None,
                code_context=code_context,
                trace_id=self.trace_id,
            )

            # 5. Dispatch to executor
            print(f"[ARCHITECT] Sending mandate to executor...")
            log_loop_event("MANDATE_SENT", mandate, self.trace_id)
            try:
                ledger = send_mandate(mandate)
            except RuntimeError as e:
                print(f"\n[HALT] {e}")
                log_loop_event("HALT", str(e), self.trace_id)
                final_status, final_summary = "error", str(e)
                break

            print(f"[EXECUTOR] Ledger received ({len(ledger)} chars)")
            log_loop_event("LEDGER_RECEIVED", ledger, self.trace_id)

            # 6. Evaluate (structured LEDGER_JSON primary)
            result = evaluate_and_log(
                ledger, mandate_id=f"{self.trace_id}:it{self.iteration}")
            log_loop_event("LEDGER_EVALUATED",
                           f"{result.status.value}: {result.summary}", self.trace_id)
            self._history.append({
                "iteration": self.iteration,
                "instruction": current_instruction[:160],
                "status": result.status.value,
                "structured": result.structured,
                "summary": result.summary[:160],
            })
            self._checkpoint(result.status.value, result.summary)

            # Low-confidence COMPLETE (prose-only ledger) → verify, don't trust
            if (result.status == LedgerStatus.COMPLETE
                    and result.confidence < 0.5):
                print(f"\n[ARCHITECT] ⚠ Unverified ledger "
                      f"(confidence {result.confidence:.0%}, "
                      f"{'no ' if not result.structured else ''}LEDGER_JSON) — "
                      f"verification iteration")
                result.status = LedgerStatus.ITERATE
                result.summary = (
                    f"Unverified ledger (confidence {result.confidence:.0%}) — "
                    f"re-run with explicit verification and emit LEDGER_JSON")

            # 7. COMPLETE → Auditor verification before acceptance
            if result.status == LedgerStatus.COMPLETE:
                tier = classify_tier(user_intent)
                if tier.tier >= 1:
                    print(f"[AUDITOR] Verifying executor claims "
                          f"(tier {tier.tier})...")
                    report = auditor.audit(
                        instruction=user_intent,
                        ledger_result=result,
                        trace_id=self.trace_id,
                        run_suites=True,
                    )
                    log_loop_event("AUDIT", report.summary(), self.trace_id)
                    if not report.verified:
                        print(f"[AUDITOR] ❌ {report.summary()}")
                        failed = [c for c in report.checks if not c.ok]
                        current_instruction = (
                            "The Auditor rejected your COMPLETE claim. "
                            "Fix these verified discrepancies and emit a new "
                            "LEDGER_JSON:\n" +
                            "\n".join(f"- {c.name}: {c.detail}" for c in failed[:5]))
                        continue
                    print(f"[AUDITOR] ✅ {report.summary()}")

                loop_status_buffer.append({
                    "type": "complete",
                    "msg": result.summary,
                    "confidence": result.confidence
                })
                print(f"\n[ARCHITECT] ✅ {result.summary}")
                self.task_complete = True
                final_status, final_summary = "complete", result.summary
                break

            elif result.status == LedgerStatus.ESCALATE:
                reason = result.needs_human or result.next_action or result.summary
                directive = self._await_directive(reason)
                if directive.lower() in ("stop", "halt", "abort"):
                    final_status, final_summary = "halted", f"escalation: {reason}"
                    break
                current_instruction = directive
                log_loop_event("ESCALATE_DIRECTIVE", directive, self.trace_id)
                continue

            elif result.status == LedgerStatus.ERROR:
                loop_status_buffer.append({
                    "type": "error",
                    "msg": result.error_detail or result.summary
                })
                print(f"\n[ARCHITECT] ❌ {result.summary}")
                log_loop_event("ERROR_DETECTED",
                               result.error_detail or result.summary, self.trace_id)
                # Postmortem draft → pending rules queue (§13.2)
                postmortem.draft_from_failure(
                    self.trace_id, user_intent,
                    result.error_detail or result.summary, ledger[:300])
                try:
                    import httpx

                    async def _alert():
                        async with httpx.AsyncClient(timeout=5.0) as client:
                            await client.post(
                                "http://127.0.0.1:5030/api/qa/alerts",
                                json={
                                    "source": "LOOP_ENGINE",
                                    "severity": "HIGH",
                                    "message": result.error_detail,
                                    "trace_id": self.trace_id,
                                    "ledger_snippet": ledger[:500]
                                }
                            )
                    asyncio.run(_alert())
                except Exception:
                    pass
                final_status, final_summary = "error", result.summary
                break

            elif result.status == LedgerStatus.ITERATE:
                loop_status_buffer.append({
                    "type": "iterate",
                    "msg": result.summary
                })
                print(f"\n[ARCHITECT] 🔄 {result.summary}")
                if result.next_action:
                    # Structured ledger told us the next step — use it directly
                    current_instruction = result.next_action
                    continue
                fallback_instruction = (
                    f"Continue execution based on this completed ledger:\n\n"
                    f"{ledger[:3000]}\n\n"
                    f"Proceed to the next logical step per CLAUDE_RULES.md."
                )
                try:
                    architect = asyncio.run(_consult_architect(
                        ledger, current_instruction, self.iteration))
                    current_instruction = (architect.get("next_mandate")
                                           or fallback_instruction)
                    if architect.get("decision") == "ESCALATE":
                        loop_status_buffer.append({
                            "type": "approval_required",
                            "msg": architect.get("escalation_reason",
                                                 "Escalation required")})
                except Exception:
                    current_instruction = fallback_instruction

        # ── Run end: episode + final checkpoint ────────────────────────────
        record_episode(
            trace_id=self.trace_id,
            instruction=user_intent,
            status=final_status,
            summary=final_summary,
            resolution=self._history[-1]["summary"] if self._history else "",
            tags=[final_status],
        )
        self._checkpoint(final_status, final_summary)
        print("\n[ARCHITECT] Loop session ended.")
        print(f"[ARCHITECT] Trace: {self.trace_id} | "
              f"Iterations: {self.iteration} | Status: {final_status}")
        print(f"[ARCHITECT] Budget: {budget.snapshot()}")
        print(f"[ARCHITECT] Full log: {LOOP_LOG}")


async def _consult_architect(ledger, context, iteration):
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "http://127.0.0.1:5050/api/loop/architect",
                json={"ledger": ledger, "context": context, "iteration": iteration}
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"decision": "UNAVAILABLE", "reasoning": "Architect server unreachable"}


if __name__ == "__main__":
    intent = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    if not intent:
        intent = input("[ARCHITECT] What do you want to build? ").strip()
    if intent:
        loop = AutonomousLoop()
        loop.run(intent)
