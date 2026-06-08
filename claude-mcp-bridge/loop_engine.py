"""
Autonomous Loop Engine
----------------------
Orchestrates the Claude (Architect) ↔ Antigravity (Executor) loop.

Flow:
  1. Receives user intent (plain English)
  2. Claude reads codebase + telemetry + rules
  3. Builds structured mandate
  4. Sends to Antigravity via ay_client
  5. Receives ledger
  6. Analyzes ledger + telemetry
  7. If Section 11 trigger → pauses for user input
  8. If clear → sends next mandate
  9. Loop continues until task complete or user intervenes
"""

import json
import sys
import asyncio
import threading
from pathlib import Path
from datetime import datetime

# Add bridge root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from claude_code_client import send_mandate
except ImportError:
    from ay_client import send_mandate  # fallback
from dispatcher import AntigravityDispatcher
from ledger_evaluator import evaluate_and_log, LedgerResult, LedgerStatus

# MCP bridge imports (telemetry access)
BRIDGE_ROOT = Path(__file__).parent
RULES_PATH  = BRIDGE_ROOT / "rules" / "CLAUDE_RULES.md"
TELEMETRY_LOG = BRIDGE_ROOT / "logs" / "telemetry.jsonl"
LOOP_LOG    = BRIDGE_ROOT / "logs" / "loop_history.jsonl"

dispatcher = AntigravityDispatcher(rules_path=RULES_PATH)

# ── Shared state for web-driven loop approval signalling ──────────────────
loop_status_buffer: list = []
_approval_event = threading.Event()
_approval_response: list = [""]

# ── Section 11 triggers — require user input before continuing ─────────────
SECTION_11_TRIGGERS = [
    "business logic", "data model", "user-facing", "ux", "ui design",
    "deploy", "digitalocean", "merge", "main branch", "delete", "overwrite",
    "new child app", "architectural decision"
]

INTERVENTION_PHRASES = ["stop", "pause", "change", "instead", "add", "also",
                         "deploy", "revert"]


def load_recent_telemetry(n: int = 20) -> dict:
    """Load the most recent N telemetry events from the log file."""
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
    recent = events[-n:]
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


def requires_user_input(mandate_text: str) -> str | None:
    """
    Check if the mandate contains a Section 11 trigger.
    Returns the trigger phrase if found, None if safe to proceed.
    """
    lower = mandate_text.lower()
    for trigger in SECTION_11_TRIGGERS:
        if trigger in lower:
            return trigger
    return None


def log_loop_event(event_type: str, content: str):
    """Persist loop events for audit trail."""
    LOOP_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "type": event_type,
        "content": content[:2000]  # truncate for log
    }
    with open(LOOP_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


class AutonomousLoop:

    MAX_ITERATIONS = 10

    def __init__(self):
        self.iteration = 0
        self.task_complete = False
        self.context_files: list[str] = []

    def run(self, user_intent: str):
        """
        Main entry point. Runs the Claude↔AY loop for a given user intent.
        Blocks until task is complete or user intervenes.
        """
        print(f"\n[ARCHITECT] Received intent: {user_intent}")
        log_loop_event("USER_INTENT", user_intent)

        current_instruction = user_intent

        while not self.task_complete:
            self.iteration += 1
            print(f"\n[ARCHITECT] ── Iteration {self.iteration} ──────────────")

            if self.iteration >= self.MAX_ITERATIONS:
                print(f"[LOOP] MAX_ITERATIONS ({self.MAX_ITERATIONS}) reached — escalating")
                log_loop_event("MAX_ITERATIONS",
                               f"Reached {self.MAX_ITERATIONS} iterations without COMPLETE signal")
                loop_status_buffer.append({
                    "type": "escalate",
                    "msg": f"Max iterations ({self.MAX_ITERATIONS}) reached without COMPLETE signal"
                })
                return LedgerResult(
                    status=LedgerStatus.ESCALATE,
                    confidence=1.0,
                    summary=f"Max iterations ({self.MAX_ITERATIONS}) reached without COMPLETE signal"
                )

            # 1. Load telemetry
            telemetry = load_recent_telemetry()
            if telemetry["critical_events"]:
                print(f"[TELEMETRY] ⚠ {len(telemetry['critical_events'])} "
                      f"critical events detected")

            # 2. Load code context if specified
            code_context = (read_code_context(self.context_files)
                           if self.context_files else None)

            # 3. Build mandate
            mandate = dispatcher.build_prompt(
                instruction=current_instruction,
                telemetry=telemetry if telemetry["total_events"] > 0 else None,
                code_context=code_context,
            )

            # 4. Section 11 check
            trigger = requires_user_input(mandate)
            if trigger:
                print(f"\n[ARCHITECT] ⏸ Section 11 trigger detected: '{trigger}'")
                print("[ARCHITECT] This decision requires your input.")
                user_response = input("Your decision: ").strip()
                if not user_response:
                    print("[ARCHITECT] No input received. Halting loop.")
                    break
                current_instruction = user_response
                log_loop_event("USER_DECISION", user_response)
                continue

            # 5. Send to Antigravity
            print(f"[ARCHITECT] Sending mandate to Antigravity...")
            log_loop_event("MANDATE_SENT", mandate)

            try:
                ledger = send_mandate(mandate)
            except RuntimeError as e:
                print(f"\n[HALT] {e}")
                log_loop_event("HALT", str(e))
                break

            print(f"[ANTIGRAVITY] Ledger received ({len(ledger)} chars)")
            log_loop_event("LEDGER_RECEIVED", ledger)

            # 6. Analyze ledger via LedgerEvaluator
            result = evaluate_and_log(
                ledger, mandate_id=f"iteration_{self.iteration}"
            )
            log_loop_event("LEDGER_EVALUATED",
                           f"{result.status.value}: {result.summary}")

            if result.status == LedgerStatus.COMPLETE:
                loop_status_buffer.append({
                    "type": "complete",
                    "msg": result.summary,
                    "confidence": result.confidence
                })
                print(f"\n[ARCHITECT] ✅ {result.summary}")
                self.task_complete = True
                break

            elif result.status == LedgerStatus.ESCALATE:
                loop_status_buffer.append({
                    "type": "approval_required",
                    "msg": result.next_action or result.summary
                })
                print(f"\n[ARCHITECT] ⏸ {result.summary}")
                print("[ARCHITECT] Awaiting approval (web) or type directive...")
                while not _approval_event.is_set():
                    import time; time.sleep(0.5)
                _approval_event.clear()
                directive = _approval_response[0]
                if directive.lower() in ("stop", "halt", "abort"):
                    break
                current_instruction = directive
                log_loop_event("ESCALATE_DIRECTIVE", directive)
                continue

            elif result.status == LedgerStatus.ERROR:
                loop_status_buffer.append({
                    "type": "error",
                    "msg": result.error_detail or result.summary
                })
                print(f"\n[ARCHITECT] ❌ {result.summary}")
                log_loop_event("ERROR_DETECTED",
                               result.error_detail or result.summary)
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
                                    "ledger_snippet": ledger[:500]
                                }
                            )
                    asyncio.run(_alert())
                except Exception:
                    pass
                break

            elif result.status == LedgerStatus.ITERATE:
                loop_status_buffer.append({
                    "type": "iterate",
                    "msg": result.summary
                })
                print(f"\n[ARCHITECT] 🔄 {result.summary}")
                # Continue loop — next iteration generates follow-up mandate
                try:
                    architect = asyncio.run(_consult_architect(ledger, current_instruction, self.iteration))
                    if architect.get("next_mandate"):
                        current_instruction = architect["next_mandate"]
                    if architect.get("decision") == "ESCALATE":
                        loop_status_buffer.append({"type": "approval_required", "msg": architect.get("escalation_reason", "Escalation required")})
                except Exception:
                    pass

            # 7. Derive next instruction from ledger
            current_instruction = (
                f"Continue execution based on this completed ledger:\n\n"
                f"{ledger[:3000]}\n\n"
                f"Proceed to the next logical step per CLAUDE_RULES.md."
            )

        print("\n[ARCHITECT] Loop session ended.")
        print(f"[ARCHITECT] Total iterations: {self.iteration}")
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
    return {"decision": "COMPLETE", "reasoning": "Architect unavailable"}


if __name__ == "__main__":
    intent = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    if not intent:
        intent = input("[ARCHITECT] What do you want to build? ").strip()
    if intent:
        loop = AutonomousLoop()
        loop.run(intent)
