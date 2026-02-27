"""
Antigravity Action Plan Engine
Handles parsing, revision, and execution of Triad Protocol action plans.
"""
import json
import os
import time
import re
import threading
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Callable
from datetime import datetime


@dataclass
class PlanStep:
    """A single step in an action plan."""
    step_number: int
    agent: str              # "Gemini" | "CFO" | "CMO" | "Architect" | "Claude" | etc.
    description: str        # Human-readable task
    risk_level: str = "safe"     # "safe" | "caution" | "critical"
    tools: List[str] = field(default_factory=list)
    code: str = ""               # Code/instructions for this step
    status: str = "pending"      # "pending" | "running" | "done" | "failed" | "skipped"
    output: str = ""             # Result after execution
    error: str = ""              # Error message if failed
    user_notes: str = ""         # User's per-step feedback
    triad_notes: str = ""        # Triad's response to user notes
    elapsed_seconds: float = 0.0
    skipped: bool = False
    pause_after: bool = False

    @property
    def risk_icon(self) -> str:
        return {"safe": "🟢", "caution": "🟡", "critical": "🔴"}.get(self.risk_level, "⚪")

    @property
    def status_icon(self) -> str:
        return {
            "pending": "⏳", "running": "⚙️", "done": "✅",
            "failed": "❌", "skipped": "⏭️"
        }.get(self.status, "❓")

    @property
    def agent_badge(self) -> str:
        badges = {
            "Gemini": "🧠", "CEO": "👔", "CFO": "💰", "CMO": "📢",
            "HR": "👥", "Critic": "🎯", "Architect": "🏗️", "Claude": "🔧",
            "Atomizer": "⚡", "Pitch": "🎤", "Antigravity": "🚀"
        }
        return badges.get(self.agent, "🤖")


@dataclass
class ActionPlan:
    """A full action plan from the Triad Protocol."""
    task: str                              # Original user task
    steps: List[PlanStep] = field(default_factory=list)
    status: str = "draft"                  # "draft" | "reviewing" | "approved" | "executing" | "complete" | "failed"
    revision_count: int = 0
    revision_history: List[dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    artifacts: List[str] = field(default_factory=list)  # Files created during execution
    _on_progress: Optional[Callable] = field(default=None, repr=False)
    _on_step_complete: Optional[Callable] = field(default=None, repr=False)
    _on_artifact: Optional[Callable] = field(default=None, repr=False)
    _paused: bool = field(default=False, repr=False)
    _cancel: bool = field(default=False, repr=False)

    @property
    def progress(self) -> str:
        done = sum(1 for s in self.steps if s.status in ("done", "skipped"))
        return f"{done}/{len(self.steps)}"

    @property
    def current_step_index(self) -> int:
        for i, s in enumerate(self.steps):
            if s.status == "running":
                return i
        for i, s in enumerate(self.steps):
            if s.status == "pending":
                return i
        return -1

    def to_summary_text(self) -> str:
        """Render the plan as a readable summary for the UI console."""
        lines = []
        lines.append(f"{'═' * 56}")
        lines.append(f"  ACTION PLAN: {self.task}")
        lines.append(f"  Status: {self.status.upper()} | Steps: {len(self.steps)} | Revision: #{self.revision_count}")
        lines.append(f"{'═' * 56}")

        for step in self.steps:
            risk = step.risk_icon
            badge = step.agent_badge
            status = step.status_icon

            lines.append(f"\n  {status} Step {step.step_number}: {badge} {step.agent}")
            lines.append(f"     {risk} {step.description}")

            if step.tools:
                lines.append(f"     Tools: {', '.join(step.tools)}")
            if step.user_notes:
                lines.append(f"     📝 Your Notes: {step.user_notes}")
            if step.triad_notes:
                lines.append(f"     💬 Triad: {step.triad_notes}")
            if step.output and step.status == "done":
                preview = step.output[:150].replace('\n', ' ')
                lines.append(f"     ✅ Output: {preview}...")
            if step.error:
                lines.append(f"     ❌ Error: {step.error}")
            if step.skipped:
                lines.append(f"     ⏭️ SKIPPED by user")
            if step.pause_after:
                lines.append(f"     ⏸️ Will pause after this step")

        lines.append(f"\n{'═' * 56}")

        if self.artifacts:
            lines.append(f"  📦 Artifacts: {', '.join(self.artifacts)}")

        return "\n".join(lines)

    def to_context_json(self) -> str:
        """Serialize the plan for sending back to Gemini as context."""
        plan_data = {
            "task": self.task,
            "revision": self.revision_count,
            "steps": [
                {
                    "step": s.step_number,
                    "agent": s.agent,
                    "description": s.description,
                    "risk": s.risk_level,
                    "tools": s.tools,
                    "user_notes": s.user_notes,
                    "status": s.status
                }
                for s in self.steps
            ]
        }
        return json.dumps(plan_data, indent=2)

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def cancel(self):
        self._cancel = True

    def generate_mission_report(self) -> str:
        """Generate a post-execution Mission Report with results and artifact links."""
        lines = []
        lines.append("")
        lines.append("=" * 60)
        lines.append("  MISSION REPORT — TRIAD PROTOCOL")
        lines.append("=" * 60)
        lines.append(f"  Task: {self.task}")
        lines.append(f"  Status: {self.status.upper()}")
        lines.append(f"  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("-" * 60)

        done_count = sum(1 for s in self.steps if s.status == "done")
        fail_count = sum(1 for s in self.steps if s.status == "failed")
        skip_count = sum(1 for s in self.steps if s.status in ("skipped",))
        total_time = sum(s.elapsed_seconds for s in self.steps)

        lines.append(f"  Steps: {done_count} completed | {fail_count} failed | {skip_count} skipped")
        lines.append(f"  Total Time: {total_time:.1f}s")
        lines.append("-" * 60)
        lines.append("")

        # Per-step results
        for step in self.steps:
            icon = step.status_icon
            badge = step.agent_badge
            time_str = f"({step.elapsed_seconds:.1f}s)" if step.elapsed_seconds > 0 else ""
            lines.append(f"  {icon} Step {step.step_number}: {badge} {step.agent} {time_str}")

            if step.status == "done" and step.output:
                # Show first line of output as preview
                preview = step.output.strip().split('\n')[0][:120]
                lines.append(f"     >> {preview}")
            elif step.status == "failed" and step.error:
                lines.append(f"     !! {step.error[:120]}")
            elif step.status == "skipped":
                lines.append(f"     -- Skipped by user")

        # Artifacts section
        if self.artifacts:
            lines.append("")
            lines.append("-" * 60)
            lines.append("  ARTIFACTS CREATED:")
            for i, artifact in enumerate(self.artifacts, 1):
                lines.append(f"    [{i}] {artifact}")

        # Links section — extract URLs from step outputs
        urls = []
        for step in self.steps:
            if step.output:
                import re as _re
                found = _re.findall(r'https?://\S+', step.output)
                urls.extend(found)
        if urls:
            lines.append("")
            lines.append("  LINKS:")
            for url in list(dict.fromkeys(urls))[:10]:  # Deduplicate, max 10
                lines.append(f"    >> {url}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════
#   PLAN PARSER — Converts Gemini response to ActionPlan
# ═══════════════════════════════════════════════════════

def _classify_risk(step_data: dict) -> str:
    """Classify risk level based on agent, tools, and description."""
    desc = step_data.get("description", "").lower()
    agent = step_data.get("agent", "").lower()
    tools = [t.lower() for t in step_data.get("tools", [])]

    # Critical: external calls, file deletion, deployment
    critical_keywords = ["deploy", "delete", "remove", "execute", "production", "docker", "push"]
    if any(kw in desc for kw in critical_keywords):
        return "critical"

    # Caution: file writes, code generation, API calls
    caution_keywords = ["write", "create", "generate", "modify", "update", "code", "script", "file"]
    caution_tools = ["file_system_tool", "produce_document", "google_workspace"]
    if any(kw in desc for kw in caution_keywords) or any(t in tools for t in caution_tools):
        return "caution"

    return "safe"


def _map_agent_name(raw_agent: str) -> str:
    """Normalize agent names from Gemini's response."""
    mapping = {
        "gemini": "Gemini", "antigravity": "Antigravity", "claude": "Claude",
        "ceo": "CEO", "cfo": "CFO", "cmo": "CMO", "hr": "HR",
        "critic": "Critic", "architect": "Architect", "pitch": "Pitch",
        "atomizer": "Atomizer", "presentation_architect": "Architect"
    }
    return mapping.get(raw_agent.lower().strip(), raw_agent.strip())


def parse_gemini_response(response_text: str, original_task: str) -> Optional[ActionPlan]:
    """
    Parse a Gemini response into an ActionPlan.
    Handles multiple formats:
    - Full JSON with "steps" array
    - JSON wrapped in markdown code blocks
    - Structured text with numbered steps
    """
    plan = ActionPlan(task=original_task)

    # Try to extract JSON from the response
    json_data = None

    # Try raw JSON parse first
    try:
        json_data = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try extracting from markdown code block
    if json_data is None:
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
        if json_match:
            try:
                json_data = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

    # Try finding JSON object/array in text
    if json_data is None:
        brace_start = response_text.find('{')
        brace_end = response_text.rfind('}')
        if brace_start != -1 and brace_end != -1:
            try:
                json_data = json.loads(response_text[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass

    if json_data is None:
        return None

    # Extract task name
    plan.task = json_data.get("task", original_task)

    # Extract steps — handle nested structures
    raw_steps = json_data.get("steps", [])

    step_num = 0
    for raw_step in raw_steps:
        step_num += 1
        agent_raw = raw_step.get("agent", "Gemini")
        desc = raw_step.get("description", raw_step.get("action", raw_step.get("details", "No description")))
        tools = raw_step.get("tools", [])
        code = raw_step.get("code", "")

        # Handle nested expected_output with sub-tasks
        expected = raw_step.get("expected_output", {})
        if isinstance(expected, dict) and "tasks" in expected:
            # This is a meta-step with sub-tasks — expand them
            for sub in expected["tasks"]:
                step_num_inner = step_num
                step_num += 1
                sub_agent = _map_agent_name(sub.get("agent", agent_raw))
                sub_desc = sub.get("description", "Sub-task")
                sub_tools = sub.get("tools", [])

                step = PlanStep(
                    step_number=step_num_inner,
                    agent=sub_agent,
                    description=sub_desc,
                    tools=sub_tools,
                    risk_level=_classify_risk({"description": sub_desc, "agent": sub_agent, "tools": sub_tools})
                )
                plan.steps.append(step)
            continue

        step = PlanStep(
            step_number=step_num,
            agent=_map_agent_name(agent_raw),
            description=desc,
            tools=tools,
            code=code,
            risk_level=_classify_risk(raw_step)
        )
        plan.steps.append(step)

    # Renumber steps sequentially
    for i, step in enumerate(plan.steps):
        step.step_number = i + 1

    if not plan.steps:
        return None

    return plan


# ═══════════════════════════════════════════════════════
#   PLAN EXECUTOR — Runs steps sequentially via bridge
# ═══════════════════════════════════════════════════════

def execute_plan(plan: ActionPlan, bridge_call_fn, progress_callback=None):
    """
    Execute an approved action plan step by step.
    
    Args:
        plan: The approved ActionPlan
        bridge_call_fn: Function to call bridge (agent_name, prompt) -> response
        progress_callback: fn(plan) called after each step
    """
    plan.status = "executing"

    for step in plan.steps:
        # Check for cancellation
        if plan._cancel:
            plan.status = "failed"
            step.error = "Cancelled by user"
            if progress_callback:
                progress_callback(plan)
            break

        # Wait while paused
        while plan._paused:
            time.sleep(0.5)
            if plan._cancel:
                break

        # Skip if marked
        if step.skipped:
            step.status = "skipped"
            if progress_callback:
                progress_callback(plan)
            continue

        # Execute
        step.status = "running"
        if progress_callback:
            progress_callback(plan)

        start_time = time.time()

        try:
            # Build the prompt for this step
            prompt = _build_step_prompt(step, plan)

            # Route to the correct agent
            response = bridge_call_fn({
                "prompt": prompt,
                "project_name": plan.task.replace(" ", "_")[:30],
                "context": f"TRIAD_PLAN_STEP_{step.step_number}",
                "suite_command": True
            })

            step.output = response if isinstance(response, str) else json.dumps(response)
            step.status = "done"
            step.elapsed_seconds = time.time() - start_time

            # Check for artifacts in the response
            _detect_artifacts(step, plan)

        except Exception as e:
            step.status = "failed"
            step.error = str(e)
            step.elapsed_seconds = time.time() - start_time
            plan.status = "failed"

            if progress_callback:
                progress_callback(plan)
            break

        if progress_callback:
            progress_callback(plan)

        # Pause after this step if flagged
        if step.pause_after:
            plan._paused = True
            while plan._paused:
                time.sleep(0.5)
                if plan._cancel:
                    break

    # Final status
    if all(s.status in ("done", "skipped") for s in plan.steps):
        plan.status = "complete"
    elif plan.status != "failed":
        plan.status = "complete"

    if progress_callback:
        progress_callback(plan)


def _build_step_prompt(step: PlanStep, plan: ActionPlan) -> str:
    """Build the execution prompt for a step."""
    prompt = (
        f"SYSTEM OVERRIDE: EXECUTE MODE.\n"
        f"You are executing Step {step.step_number} of a {len(plan.steps)}-step Action Plan.\n"
        f"ORIGINAL TASK: {plan.task}\n"
        f"YOUR ROLE: {step.agent}\n"
        f"YOUR TASK: {step.description}\n"
    )

    if step.tools:
        prompt += f"AVAILABLE TOOLS: {', '.join(step.tools)}\n"

    if step.code:
        prompt += f"\nREFERENCE CODE:\n{step.code}\n"

    if step.user_notes:
        prompt += f"\nUSER NOTES: {step.user_notes}\n"

    # Add context from previous completed steps
    prev_outputs = []
    for prev in plan.steps:
        if prev.step_number < step.step_number and prev.status == "done":
            prev_outputs.append(f"Step {prev.step_number} ({prev.agent}): {prev.output[:300]}")

    if prev_outputs:
        prompt += f"\nPREVIOUS STEP OUTPUTS:\n" + "\n".join(prev_outputs) + "\n"

    prompt += (
        "\nINSTRUCTION: Execute this step NOW. Do not plan or summarize."
        " Produce the actual output/result of the work.\n"
    )

    return prompt


def _detect_artifacts(step: PlanStep, plan: ActionPlan):
    """Detect and MATERIALIZE file artifacts from step output."""
    if not step.output:
        return

    output = step.output

    # Determine output directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    deliverables_dir = os.path.join(base_dir, ".Gemini_state", "deliverables")
    os.makedirs(deliverables_dir, exist_ok=True)

    safe_task = plan.task[:30].replace(" ", "_").replace("/", "_").replace("\\", "_")

    # 1. Detect produce_document() tool calls from agents
    doc_pattern = re.compile(
        r"produce_document\s*\(\s*file_type\s*=\s*['\"](\w+)['\"]"
        r"\s*,\s*content\s*=\s*['\"](.+?)['\"]\s*\)",
        re.DOTALL
    )
    for match in doc_pattern.finditer(output):
        file_type = match.group(1)
        content = match.group(2)

        # Unescape the content
        content = content.replace("\\n", "\n").replace("\\'", "'").replace('\\"', '"')

        # Map file types to extensions (write everything as .md since we can't create real pptx/docx)
        ext_map = {"pptx": ".md", "docx": ".md", "xlsx": ".md", "csv": ".csv",
                    "json": ".json", "py": ".py", "md": ".md", "txt": ".txt"}
        ext = ext_map.get(file_type, ".md")

        filename = f"{safe_task}_Step{step.step_number}_{step.agent}{ext}"
        filepath = os.path.join(deliverables_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                if file_type in ("pptx", "docx"):
                    f.write(f"# {plan.task} — {step.agent} Output\n")
                    f.write(f"*Originally requested as .{file_type}*\n\n")
                f.write(content)
            if filepath not in plan.artifacts:
                plan.artifacts.append(filepath)
            print(f"  >> Document materialized: {filename}", flush=True)
        except Exception as e:
            print(f"  >> Warning: Could not write {filename}: {e}", flush=True)

    # 2. If no produce_document found but output is substantial, save the raw output
    if not doc_pattern.search(output) and len(output) > 200:
        filename = f"{safe_task}_Step{step.step_number}_{step.agent}_output.md"
        filepath = os.path.join(deliverables_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# Step {step.step_number}: {step.agent}\n")
                f.write(f"**Task:** {step.description}\n\n")
                f.write("---\n\n")
                f.write(output)
            if filepath not in plan.artifacts:
                plan.artifacts.append(filepath)
            print(f"  >> Output saved: {filename}", flush=True)
        except Exception as e:
            print(f"  >> Warning: Could not write {filename}: {e}", flush=True)

    # 3. Also detect file path mentions (for tracking)
    path_patterns = [
        r'saved to (\S+\.(?:json|csv|xlsx|pptx|py|md|txt))',
        r'created (\S+\.(?:json|csv|xlsx|pptx|py|md|txt))',
        r'written to (\S+\.(?:json|csv|xlsx|pptx|py|md|txt))',
    ]
    for pattern in path_patterns:
        matches = re.findall(pattern, output, re.IGNORECASE)
        for match in matches:
            if match not in plan.artifacts:
                plan.artifacts.append(match)


# ═══════════════════════════════════════════════════════
#   FEEDBACK / REVISION
# ═══════════════════════════════════════════════════════

def build_revision_prompt(plan: ActionPlan, user_feedback: str) -> str:
    """Build a prompt to send to Gemini for plan revision."""
    prompt = (
        f"SYSTEM OVERRIDE: PLAN REVISION MODE.\n"
        f"You previously created this Action Plan:\n\n"
        f"{plan.to_context_json()}\n\n"
        f"The USER has provided the following feedback:\n"
        f"\"{user_feedback}\"\n\n"
        f"INSTRUCTIONS:\n"
        f"1. Review the feedback and update the plan accordingly.\n"
        f"2. If the feedback improves the plan, incorporate it.\n"
        f"3. If you DISAGREE with any feedback, explain WHY in a 'triad_notes' "
        f"field for that step, and suggest a better approach.\n"
        f"4. Return the REVISED plan in the SAME JSON format with a 'steps' array.\n"
        f"5. Each step must have: agent, description, tools (list), and optionally triad_notes.\n"
        f"6. Return ONLY the JSON. No markdown, no explanation outside the JSON.\n"
    )
    return prompt


def apply_revision(plan: ActionPlan, revised_response: str) -> bool:
    """Apply a revised plan from Gemini's response."""
    # Save current version to history
    plan.revision_history.append({
        "revision": plan.revision_count,
        "steps": [asdict(s) for s in plan.steps],
        "timestamp": datetime.now().isoformat()
    })

    revised = parse_gemini_response(revised_response, plan.task)
    if revised and revised.steps:
        # Preserve user notes from old steps where step numbers match
        old_notes = {s.step_number: s.user_notes for s in plan.steps if s.user_notes}
        plan.steps = revised.steps
        for s in plan.steps:
            if s.step_number in old_notes:
                s.user_notes = old_notes[s.step_number]
        plan.revision_count += 1
        return True
    return False
