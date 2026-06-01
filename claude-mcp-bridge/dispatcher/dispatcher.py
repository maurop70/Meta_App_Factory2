"""
Antigravity Dispatcher
----------------------
Builds structured prompts for Antigravity (AY) with:
  1. CLAUDE_RULES.md injected as <SYSTEM_RULES>
  2. Browser telemetry as <TELEMETRY>
  3. Source code context as <CODE_CONTEXT>
  4. The instruction as <USER_REQUEST>
"""

import json
from datetime import datetime
from pathlib import Path

RULES_PATH  = Path(__file__).parent.parent / "rules" / "CLAUDE_RULES.md"
PROMPT_LOG  = Path(__file__).parent.parent / "logs" / "dispatched_prompts.jsonl"


class AntigravityDispatcher:

    def __init__(self, rules_path: Path = RULES_PATH):
        self.rules_path = rules_path

    def build_prompt(self, instruction: str, telemetry: dict | None = None,
                     code_context: dict[str, str] | None = None,
                     extra_context: str | None = None) -> str:
        parts = [self._rules_block()]
        if telemetry:
            parts.append(self._telemetry_block(telemetry))
        if code_context:
            parts.append(self._code_block(code_context))
        if extra_context:
            parts.append(f"<EXTRA_CONTEXT>\n{extra_context}\n</EXTRA_CONTEXT>")
        parts.append(self._instruction_block(instruction))
        prompt = "\n\n".join(parts)
        self._log_prompt(instruction, prompt)
        return prompt

    def build_autofix_prompt(self, telemetry: dict,
                              code_context: dict[str, str]) -> str:
        errors = telemetry.get("critical_events", [])
        if not errors:
            raise ValueError("No critical events in telemetry")
        error_summary = "\n".join(
            f"- [{e.get('type')}] {e.get('message','?')} "
            f"(line {e.get('lineNumber','?')}, {e.get('url','?')})"
            for e in errors[:5]
        )
        instruction = (
            f"Auto-heal the following runtime errors detected in the browser:\n\n"
            f"{error_summary}\n\n"
            f"1. Identify root cause in provided code context.\n"
            f"2. Apply minimal fix — no side effects.\n"
            f"3. Mark fix location with a comment.\n"
            f"4. Do NOT refactor unrelated code.\n"
            f"5. Confirm which file(s) were changed."
        )
        return self.build_prompt(instruction, telemetry=telemetry,
                                  code_context=code_context)

    def _rules_block(self) -> str:
        rules = (self.rules_path.read_text(encoding="utf-8").strip()
                 if self.rules_path.exists()
                 else "No CLAUDE_RULES.md found.")
        return f"<SYSTEM_RULES>\n{rules}\n</SYSTEM_RULES>"

    def _telemetry_block(self, telemetry: dict) -> str:
        critical = telemetry.get("critical_events", [])
        lines = [f"<TELEMETRY total='{telemetry.get('total_events',0)}' "
                 f"critical='{len(critical)}'>"]
        if critical:
            lines.append("  <!-- CRITICAL — address first -->")
            for e in critical[:10]:
                lines.append(f"  {json.dumps(e)}")
        lines.append("</TELEMETRY>")
        return "\n".join(lines)

    def _code_block(self, code_context: dict[str, str]) -> str:
        parts = ["<CODE_CONTEXT>"]
        for filename, content in code_context.items():
            parts.append(f"  <file name='{filename}'>\n{content}\n  </file>")
        parts.append("</CODE_CONTEXT>")
        return "\n".join(parts)

    def _instruction_block(self, instruction: str) -> str:
        return f"<USER_REQUEST>\n{instruction}\n</USER_REQUEST>"

    def _log_prompt(self, instruction: str, prompt: str):
        PROMPT_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": datetime.utcnow().isoformat(),
                 "instruction": instruction, "prompt_length": len(prompt)}
        with open(PROMPT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
