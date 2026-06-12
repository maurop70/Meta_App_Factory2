"""
war_room_runner.py — CANONICAL C-Suite War Room debate loop.

WarRoomPipelineRunner carries the full Linear Dependency Protocol:
CEO triage staffing, typed WarRoomReport handoffs, gates, Critic
consensus, Phantom QA, checkpoints, personas, COO budget, prediction
ledger / calibration / revision audits, dynamic Red-Team chaos drills,
and semantic memory recall.

Extracted from api.py's trigger_csuite() closure so the debate loop is
testable in isolation and api.py stays a thin route layer. The runner
holds NO module-level globals: all api.py-owned infrastructure
(_broadcast, _call_agent, _stealth_extract, the warroom executor) is
injected through the constructor.

The legacy dispatch plane (war_room_orchestrator.dispatch_to_csuite)
remains untouched — it still serves the native_sequence() path with its
CIO preflight / Sentinel Queue integrations.
"""

import os
import json
import re
import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import coo_agent
from persona_manager import get_persona_manager
from warroom_protocol import (
    WarRoomReport, PipelineStep, HANDOFF_MODELS,
    ChaosScenario, CHAOS_LIBRARY,
    get_orchestrator, get_report_store, parse_agent_response,
    get_strategy_mode,
)
from wisdom_vault import get_wisdom_vault

logger = logging.getLogger("WarRoomRunner")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Full bench used when CEO triage parsing fails — previously a parse
# failure produced an empty triage list which silently skipped every
# staffed agent except CFO/CRITIC.
_DEFAULT_TRIAGE = ["CMO", "CEO", "CPO", "CTO", "CLO", "CFO", "CRITIC"]

# Phase 6: "HIGH [CMO]: objection text" → (severity, agent, text)
_OBJECTION_TAG_RE = re.compile(
    r'^\s*(HIGH|MEDIUM|LOW)\s*[\[\(]\s*(CMO|CEO|CTO|CFO|CPO|CLO)\s*[\]\)]\s*[:\-—]?\s*(.+)$',
    re.IGNORECASE,
)


class WarRoomPipelineRunner:
    """Runs one full C-Suite boardroom session (triage → consensus)."""

    def __init__(
        self,
        *,
        project_id: str,
        message: str,
        strategy_mode: str = "balanced",
        custom_directive: str = "",
        stress_test: bool = False,
        broadcast: Callable,            # async (msg: dict, project: str) -> None
        call_agent: Callable,           # sync (agent_name: str, topic: str) -> str
        stealth_extract: Callable,      # sync (fields: list, transcript: str) -> dict
        executor,                       # ThreadPoolExecutor for blocking LLM calls
        agents_meta: Dict[str, dict] = None,
        persuasion_setter: Callable = None,  # sync (score: float) -> None
        pre_deploy_available: bool = False,
        script_dir: str = None,
        max_iterations: int = 5,
    ):
        self.project_id = project_id
        self.message = message
        self.msg_lower = message.lower()
        self.strategy = get_strategy_mode(strategy_mode, custom_directive)
        self.stress_test = stress_test

        self._broadcast = broadcast
        self._call_agent = call_agent
        self._stealth_extract = stealth_extract
        self._executor = executor
        self._agents_meta = agents_meta or {}
        self._persuasion_setter = persuasion_setter
        self._pre_deploy_available = pre_deploy_available
        self._script_dir = script_dir or SCRIPT_DIR

        # Session state (was closure/global state in api.py)
        self.topic = f"Commander overrides: {message}"
        self.iteration = 1
        self.max_iterations = max_iterations
        self.persuasion_score: float = 5.0
        self.triage_list: List[str] = []
        self.market_pulse_data: Dict[str, Any] = {}
        self.session: Dict[str, Any] = {}
        self.active_chaos: Optional[ChaosScenario] = None      # Phase 4
        self.semantic_memory_block: str = ""                   # Phase 5
        self.objection_mandates: Dict[str, List[str]] = {}     # Phase 6

        self._store = get_report_store()
        self._orchestrator = get_orchestrator()

        checkpoint_dir = os.path.join("Boardroom_Exchange", "active_sessions")
        os.makedirs(checkpoint_dir, exist_ok=True)
        self._checkpoint_file = os.path.join(checkpoint_dir, f"{project_id}_state.json")

    # ─────────────────────────────────────────────────────────────
    # Broadcast / persuasion plumbing
    # ─────────────────────────────────────────────────────────────

    async def _emit(self, msg: dict):
        await self._broadcast(msg, project=self.project_id)

    def _set_persuasion(self, score: float):
        self.persuasion_score = min(max(score, 1), 10)
        if self._persuasion_setter:
            try:
                self._persuasion_setter(self.persuasion_score)
            except Exception as e:
                logger.warning(f"Persuasion setter failed: {e}")

    # ─────────────────────────────────────────────────────────────
    # Agent execution (port of trigger_agent_response closure)
    # ─────────────────────────────────────────────────────────────

    async def _trigger_agent_response(self, agent_name: str, prompt_override: str = None):
        loop = asyncio.get_running_loop()
        query = prompt_override or self.topic

        # ── Phase 7: Agent Persona Injection ──
        try:
            pm = get_persona_manager()
            query = pm.inject_memory_into_prompt(agent_name, query)
        except Exception as e:
            logger.warning(f"Failed to inject persona memory for {agent_name}: {e}")

        # ── Outcome Loop: calibration injection ──
        # The agent's reconciled prediction-vs-reality record
        # (empty until actuals exist, so cold start is silent).
        try:
            from warroom_outcomes import get_prediction_ledger
            _calib = get_prediction_ledger().calibration_prompt_block(agent_name)
            if _calib:
                query = f"{_calib}\n\n{query}"
        except Exception as e:
            logger.warning(f"Calibration injection failed for {agent_name}: {e}")

        logger.info(f"Triggering {agent_name} response")
        await self._emit({
            "type": "agent_working",
            "agent": agent_name,
            "timestamp": datetime.now().isoformat()
        })

        ledger = None
        try:
            if agent_name == "CPO":
                import cpo_agent
                resp = await loop.run_in_executor(self._executor, cpo_agent.run_cpo, query)
            else:
                resp = await loop.run_in_executor(self._executor, self._call_agent, agent_name, query)
            coo = coo_agent.get_coo()
            ledger = coo.record_usage(self.project_id, agent_name, query, resp or "")

            await self._emit({
                "type": "coo_alert",
                "tokens_total": ledger.total_tokens,
                "budget": ledger.max_budget,
                "status": ledger.status,
                "est_cost": f"${ledger.estimated_cost_usd:.4f}"
            })
        except coo_agent.OpBudgetExceeded as e:
            logger.error(str(e))
            await self._emit({
                "type": "dialogue",
                "agent": "SYSTEM",
                "icon": "🛑",
                "color": "#dc2626",
                "message": f"**[COO OPERATION ABORT]** {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
            raise  # break loop

        agent_meta = self._agents_meta.get(agent_name, {})
        await self._emit({
            "type": "dialogue",
            "agent": agent_name,
            "icon": agent_meta.get("icon", "🤖"),
            "color": agent_meta.get("color", "#3b82f6"),
            "message": resp or f"{agent_name} logic processed.",
            "timestamp": datetime.now().isoformat()
        })

        # ── Stealth Extraction (Dual-Output Pattern) ──
        structured_data = {}
        metadata = {"cost": f"${ledger.estimated_cost_usd:.4f}" if ledger else "$0.00"}

        model_cls = HANDOFF_MODELS.get(agent_name)
        if model_cls and resp:
            fields = list(model_cls.model_fields.keys())
            # Primary: native JSON mode (schema-valid output,
            # no fence-stripping). Legacy free-text extraction
            # kept as fallback.
            structured_data = await loop.run_in_executor(
                self._executor, self._stealth_extract, fields, resp
            )
            if not structured_data:
                stealth_prompt = (
                    f"Extract the following fields from this debate transcript into a strict JSON payload.\n"
                    f"Fields required: {fields}\n"
                    f"Do not summarize. Extract raw values only into JSON format matching the provided Pydantic fields.\n"
                    f"Transcript:\n{resp}"
                )
                try:
                    s_resp = await loop.run_in_executor(self._executor, self._call_agent, "SYSTEM", stealth_prompt)
                    clean_json = re.sub(r'^```[\w]*\n|```$', '', s_resp.strip(), flags=re.MULTILINE).strip()
                    s_start = clean_json.find('{')
                    s_end = clean_json.rfind('}')
                    if s_start != -1 and s_end != -1:
                        structured_data = json.loads(clean_json[s_start:s_end + 1])
                except Exception as e:
                    logger.error(f"Stealth Extraction failed for {agent_name}: {e}")

        return (resp or "", structured_data, metadata)

    # ─────────────────────────────────────────────────────────────
    # Wisdom / performance review
    # ─────────────────────────────────────────────────────────────

    async def _propose_wisdom(self, report):
        try:
            vault = get_wisdom_vault()
            candidate = vault.propose_from_report(report)
            if candidate:
                await self._emit({
                    "type": "wisdom_proposal",
                    "agent": "SYSTEM",
                    "message": f"💡 New insight proposed: {candidate.title}",
                    "standard_id": candidate.standard_id,
                })
        except Exception as e:
            logger.warning(f"Wisdom proposal failed: {e}")

    async def _run_performance_review(self, critic_output: str, score: float, p_type: str = "GLOBAL"):
        """Phase 7: Analyzes a brilliant project plan or absolute failure to extract Win Conditions or Scars."""
        logger.info(f"Triggering Performance Review for {self.project_id}...")
        loop = asyncio.get_running_loop()
        pm = get_persona_manager()

        is_win = score >= 8.0
        if is_win:
            review_prompt = (
                f"The Commander rated this {p_type} project plan {score}/10, a massive success.\n"
                "Analyze the CRITIC's successful verdict and identify 1 specific strategic behavior or tactic "
                "performed by the CTO and/or CFO that made this a success.\n"
                f"Prepend the tactic with the context tag: [{p_type}].\n"
                "Return ONLY a strict JSON object mapping the agent's name to a single bullet point string.\n"
                f"Example: {{\"CTO\": \"[{p_type}] Chose SQLite to minimize dev overhead\"}}\n"
                f"CRITIC VERDICT:\n{critic_output}"
            )
        else:
            review_prompt = (
                f"The Commander rated this {p_type} project plan {score}/10, an absolute failure.\n"
                "Analyze the CRITIC's failed verdict and identify 1 critical mistake "
                "performed by the CTO and/or CFO that caused this rejection.\n"
                f"Prepend the scar with the context tag: [{p_type}].\n"
                "Return ONLY a strict JSON object mapping the agent's name to a single bullet point string.\n"
                f"Example: {{\"CFO\": \"[{p_type}] Proposed budget ignoring critical tax law\"}}\n"
                f"CRITIC VERDICT:\n{critic_output}"
            )

        try:
            resp = await loop.run_in_executor(self._executor, self._call_agent, "SYSTEM", review_prompt)
            clean_json = re.sub(r'^```[\w]*\n|```$', '', resp.strip(), flags=re.MULTILINE).strip()
            start = clean_json.find('{')
            end = clean_json.rfind('}')
            if start != -1 and end != -1:
                insights = json.loads(clean_json[start:end + 1])
                for agent, tactic in insights.items():
                    if is_win:
                        pm.add_win_condition(agent.upper(), tactic)
                        msg = f"New Win Condition added: {tactic}"
                    else:
                        pm.add_scar(agent.upper(), tactic)
                        msg = f"New Scar added: {tactic}"

                    logger.info(f"Agent Persona ({agent}) updated: {tactic}")

                    await self._emit({
                        "type": "persona_update",
                        "agent": agent.upper(),
                        "level_up": is_win,
                        "message": msg,
                        "timestamp": datetime.now().isoformat()
                    })
        except Exception as e:
            logger.error(f"Performance Review failed: {e}")

    # ─────────────────────────────────────────────────────────────
    # Pure helpers (ported verbatim from api.py closures)
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _compress_context(cmo_data: dict, cto_data: dict, cfo_data: dict, critic_data: dict,
                          phantom_verdict: str, phantom_score: int) -> str:
        """Aether Synthesis: Compress iteration context to prevent prompt bloating."""
        summary_parts = []
        cmo_rec = cmo_data.get("recommendation", "UNKNOWN")
        cmo_risks = cmo_data.get("key_risks", [])
        summary_parts.append(f"CMO: {cmo_rec}. Risks: {', '.join(cmo_risks[:2]) if cmo_risks else 'none cited'}.")
        cto_score = cto_data.get("technical_feasibility_score", "N/A")
        cto_rec = cto_data.get("recommendation", "UNKNOWN")
        summary_parts.append(f"CTO: {cto_rec} (Feasibility: {cto_score}/10).")
        cfo_rec = cfo_data.get("recommendation", "UNKNOWN")
        cfo_roi = cfo_data.get("projected_roi", "N/A")
        summary_parts.append(f"CFO: {cfo_rec}. ROI: {cfo_roi}.")
        critic_level = critic_data.get("agreement_level", 5.0)
        critic_verdict = critic_data.get("verdict", "UNKNOWN")
        objections = critic_data.get("objections", [])
        summary_parts.append(
            f"CRITIC: {critic_verdict} ({critic_level}/10). "
            f"Objections: {'; '.join(str(o) for o in objections[:2]) if objections else 'none'}."
        )
        summary_parts.append(f"PHANTOM QA: {phantom_verdict} ({phantom_score}/100).")
        return " | ".join(summary_parts)

    @staticmethod
    def _build_revision_audit(prior: dict, current: dict, iteration: int) -> str:
        """Anti-gaming guard: surface metric changes between
        iterations so the Critic can demand evidence for
        revisions instead of rewarding number-fudging."""
        if not prior or iteration <= 1:
            return ""
        lines = []
        for agent, prev_metrics in prior.items():
            curr_metrics = current.get(agent, {})
            for k, old_v in prev_metrics.items():
                new_v = curr_metrics.get(k)
                try:
                    old_f, new_f = float(old_v), float(new_v)
                except (TypeError, ValueError):
                    continue
                if old_f == 0 or new_f == old_f:
                    continue
                delta_pct = (new_f - old_f) / abs(old_f) * 100
                if abs(delta_pct) >= 10:
                    lines.append(f"- {agent}.{k}: {old_f:g} -> {new_f:g} ({delta_pct:+.0f}%)")
        if not lines:
            return ""
        return (
            "\n\n=== REVISION AUDIT (iteration-over-iteration changes) ===\n"
            + "\n".join(lines)
            + "\nA number that moved this much must be justified by NEW "
              "evidence (cited intel, corrected math), not by the desire "
              "to pass your gate. Treat unjustified revisions as a HIGH "
              "severity objection."
        )

    @staticmethod
    def _numeric_handoff(hp: dict) -> dict:
        out = {}
        for k, v in (hp or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[k] = v
        return out

    @staticmethod
    def _validate_social_media_schema(project_dir: str) -> dict:
        """Phantom Schema Validity: Check Social_Media_Matrix.json for structural integrity."""
        required_keys = {"platforms", "content_calendar", "kpi_targets"}
        matrix_path = os.path.join(project_dir, "Social_Media_Matrix.json")
        if not os.path.exists(matrix_path):
            eos_path = os.path.join(project_dir, "eos", "Social_Media_Matrix.json")
            if os.path.exists(eos_path):
                matrix_path = eos_path
            else:
                return {"valid": True, "note": "Social_Media_Matrix.json not found — schema check skipped."}
        try:
            with open(matrix_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"valid": False, "error": "Root element must be a JSON object."}
            missing = required_keys - set(data.keys())
            if missing:
                return {"valid": False, "error": f"Missing required keys: {', '.join(missing)}"}
            if not isinstance(data.get("platforms"), list) or len(data["platforms"]) == 0:
                return {"valid": False, "error": "platforms must be a non-empty array."}
            return {"valid": True, "platforms_count": len(data["platforms"])}
        except json.JSONDecodeError as e:
            return {"valid": False, "error": f"Invalid JSON: {str(e)[:150]}"}
        except Exception as e:
            return {"valid": False, "error": str(e)[:150]}

    # ─────────────────────────────────────────────────────────────
    # Phase 4: Dynamic Red-Team chaos selection
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def select_dynamic_chaos(cmo_data: dict, cto_data: dict, cfo_data: dict) -> Optional[ChaosScenario]:
        """Pick the chaos drill that attacks the plan's weakest dimension.

        Inspects this iteration's agent metrics and returns the matching
        CHAOS_LIBRARY scenario, or None when every dimension is healthy
        (no drill — chaos is earned, not random).
        """
        def _lib(scenario_id: str) -> Optional[ChaosScenario]:
            return next((s for s in CHAOS_LIBRARY if s.scenario_id == scenario_id), None)

        def _f(d: dict, key: str, default: float = 0.0) -> float:
            try:
                return float(d.get(key, default) or default)
            except (TypeError, ValueError):
                return default

        # Weakest-link priority: infrastructure first (kills delivery),
        # then financial fragility (kills runway), then market exposure.
        feasibility = _f(cto_data or {}, "technical_feasibility_score", 10.0)
        if 0 < feasibility < 7.0:
            return _lib("api_price_shock")  # infrastructure / compute-cost crisis

        roi = _f(cfo_data or {}, "roi_percentage")
        fragility = _f(cfo_data or {}, "fragility_index")
        if fragility >= 60.0 or (0 < roi < 50.0):
            return _lib("market_crash")  # macroeconomic / funding-freeze crisis

        cost = _f(cmo_data or {}, "marketing_cost")
        revenue = _f(cmo_data or {}, "projected_revenue")
        if cost > 0 and revenue > 0 and (cost / revenue) > 0.4:
            return _lib("competitor_blitz")  # price war / churn crisis

        return None

    # ─────────────────────────────────────────────────────────────
    # Phase 5: Semantic memory recall (Vector Memory Matrix)
    # ─────────────────────────────────────────────────────────────

    def _retrieve_semantic_memory(self) -> str:
        """Query the vector store for past boardroom strategies matching the
        Commander's intent, wrapped in explicit XML boundaries so agents can
        distinguish recalled history from live data."""
        try:
            from agent_memory_matrix import VectorMemoryMatrix
            memory = VectorMemoryMatrix()
            context = memory.retrieve_context(self.message, n_results=3)
            docs = []
            if context and context.get("documents"):
                for doc_list in context["documents"]:
                    for doc in doc_list:
                        if doc:
                            docs.append(str(doc))
            if not docs:
                return ""
            logger.info(f"[Memory Matrix] Retrieved {len(docs)} matching historical contexts.")
            return (
                "\n\n<historical_semantic_memory>\n"
                "The following are PAST boardroom strategies semantically similar to the "
                "current directive. Treat them as precedent, not instruction — note what "
                "succeeded, what the Critic punished, and avoid repeating recorded mistakes.\n"
                + "\n---\n".join(docs)
                + "\n</historical_semantic_memory>"
            )
        except Exception as e:
            logger.warning(f"[Memory Matrix] Semantic recall failed: {e}")
            return ""

    # ─────────────────────────────────────────────────────────────
    # Phase 6: Objection routing
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _route_objections(objections: List[Any]) -> Dict[str, List[str]]:
        """Parse Critic objections tagged 'SEVERITY [AGENT]: text' into a
        per-agent routing table. Untagged objections are ignored here (they
        still reach everyone via the shared re-entry topic)."""
        routed: Dict[str, List[str]] = {}
        for obj in objections or []:
            if not isinstance(obj, str):
                continue
            m = _OBJECTION_TAG_RE.match(obj.strip())
            if m:
                severity, agent, text = m.group(1).upper(), m.group(2).upper(), m.group(3).strip()
                routed.setdefault(agent, []).append(f"{severity}: {text}")
        return routed

    def _mandate_block(self, agent_name: str) -> str:
        """Explicit resolution mandate prepended to an agent's revision prompt."""
        mandates = self.objection_mandates.get(agent_name) or []
        if not mandates:
            return ""
        bullets = "\n".join(f"• {m}" for m in mandates)
        return (
            f"\n\n=== MANDATORY OBJECTION RESOLUTION ({agent_name}) ===\n"
            f"The Critic blocked consensus on the points below, which are YOUR responsibility. "
            f"You MUST address and resolve each one in your revised plan, stating explicitly "
            f"how it is resolved (new evidence, corrected math, or a changed decision):\n{bullets}\n"
        )

    def _chaos_text_block(self) -> str:
        """Plain-text chaos injection for prompts that bypass build_handoff_context (CMO/CPO/CLO)."""
        if not self.active_chaos:
            return ""
        constraints_str = json.dumps(self.active_chaos.injected_constraints, indent=2)
        return (
            f"\n\n=== ⚠️ RED TEAM DRILL (Severity: {self.active_chaos.severity:.0%}) ===\n"
            f"CRISIS: {self.active_chaos.description}\n"
            f"Constraints:\n{constraints_str}\n"
            f"YOU MUST demonstrate your strategy SURVIVES this scenario.\n"
            f"Adjust your numbers, timeline, and risk assessment accordingly.\n"
            f"If your original plan cannot survive, propose a PIVOT."
        )

    # ─────────────────────────────────────────────────────────────
    # Phase 8: Session checkpoint mechanics
    # ─────────────────────────────────────────────────────────────

    def _save_checkpoint(self, last_agent: str):
        coo = coo_agent.get_coo()
        ledger = coo.get_ledger(self.project_id)

        def serialize_report(rep):
            if hasattr(rep, 'model_dump'):
                return rep.model_dump()
            elif hasattr(rep, 'dict'):
                return rep.dict()
            if isinstance(rep, dict):
                return rep
            return {}

        state = {
            "last_agent": last_agent,
            "coo": {
                "tokens_in": ledger.tokens_in,
                "tokens_out": ledger.tokens_out,
                "iteration": ledger.iteration_count
            },
            "reports": {k: serialize_report(v) for k, v in self.session['reports'].items()}
        }
        try:
            with open(self._checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed writing checkpoint: {e}")

    def _restore_checkpoint(self):
        if not os.path.exists(self._checkpoint_file):
            return
        try:
            with open(self._checkpoint_file, "r", encoding="utf-8") as f:
                chk = json.load(f)

            coo_agent.get_coo().restore_ledger(
                self.project_id,
                chk['coo']['tokens_in'],
                chk['coo']['tokens_out'],
                chk['coo']['iteration']
            )

            for k, v in chk['reports'].items():
                if 'metadata' not in v:
                    v['metadata'] = {}
                v['metadata']['is_resumed'] = True
                self.session['reports'][k] = WarRoomReport(**v)

            logger.info(f"Resumed debate {self.project_id} from {chk.get('last_agent', 'known')} checkpoint.")
            asyncio.create_task(self._emit({
                "type": "dialogue",
                "agent": "SYSTEM",
                "icon": "💾",
                "color": "#10b981",
                "message": f"**[STATE RECOVERY]** Resuming debate from {chk.get('last_agent', 'previous')} checkpoint...",
                "timestamp": datetime.now().isoformat()
            }))
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")

    # ─────────────────────────────────────────────────────────────
    # CEO triage
    # ─────────────────────────────────────────────────────────────

    async def _run_ceo_triage(self) -> List[str]:
        await self._emit({
            "type": "intervention",
            "agent": "CEO",
            "message": "Staffing Project: Evaluating Commander Intent...",
            "timestamp": datetime.now().isoformat()
        })

        triage_prompt = (
            "You are the CEO. You must dynamically select the most efficient War Room team to handle the following objective.\n"
            f"Objective: '{self.message}'\n"
            "Available Agents: [CMO, CFO, CTO, CLO, CRITIC, ARCHITECT]\n"
            "Rules:\n"
            "1. Return ONLY a valid JSON array of strings containing the selected agent names in order.\n"
            "2. The Minimum Squad is 2 agents. The final agent should act as the gate (typically CRITIC or CTO).\n"
            "3. Output MUST be only JSON, e.g. [\"CTO\", \"ARCHITECT\", \"CRITIC\"]\n"
            "Team Selection:"
        )
        loop = asyncio.get_running_loop()
        triage_resp = await loop.run_in_executor(self._executor, self._call_agent, "CEO", triage_prompt)

        triage_list = []
        try:
            clean_resp = re.sub(r'```(?:json)?', '', triage_resp).strip()
            triage_list = json.loads(clean_resp)
            if not isinstance(triage_list, list):
                triage_list = []
        except Exception as e:
            logger.error(f"CEO Triage parsing failed: {e} | Raw: {triage_resp}")

        if not triage_list:
            # Hardening: a failed triage used to produce an empty list that
            # skipped every staffed agent. Fall back to the full bench.
            logger.warning("CEO Triage empty/unparseable — falling back to full C-Suite bench.")
            triage_list = list(_DEFAULT_TRIAGE)
        return [str(a).upper().strip() for a in triage_list]

    # ─────────────────────────────────────────────────────────────
    # Main session
    # ─────────────────────────────────────────────────────────────

    async def run_session(self):
        """Execute the full Linear Dependency Protocol debate to consensus."""
        try:
            # Broadcast START_DEBATE event via the Server-Sent Events/WS stream
            await self._emit({
                "type": "intervention",
                "agent": "SYSTEM",
                "message": f"START_DEBATE — Strategy: {self.strategy.label} | Stress Test: {self.stress_test}",
                "timestamp": datetime.now().isoformat()
            })

            # ── UPGRADE 6: CEO Triage (Dynamic Hierarchy Composition) ──
            self.triage_list = await self._run_ceo_triage()

            # ── WAR ROOM PROTOCOL INTEGRATION ──────────────────────
            pipeline = self._orchestrator.compose_pipeline(self.message, triage_override=self.triage_list)
            self.session = self._orchestrator.start_session(
                self.project_id, pipeline, self.message,
                strategy_mode=self.strategy, stress_test=self.stress_test,
            )
            logger.info(f"War Room Session: {self._orchestrator.get_pipeline_summary(pipeline)}")

            # ── Phase 5: Semantic memory recall (pre-loop, once) ──
            self.semantic_memory_block = self._retrieve_semantic_memory()
            if self.semantic_memory_block:
                await self._emit({
                    "type": "dialogue",
                    "agent": "SYSTEM",
                    "icon": "🧠",
                    "color": "#a855f7",
                    "message": "**SEMANTIC RECALL** Historical boardroom strategies matching this intent were retrieved and injected into CEO + Critic briefings.",
                    "timestamp": datetime.now().isoformat()
                })

            self._restore_checkpoint()

            await self._run_consensus_loop()

            logger.info("Sequential C-Suite Chain Completed.")
            self._orchestrator.end_session(
                self.project_id,
                'consensus_reached' if self.iteration <= self.max_iterations else 'max_iterations'
            )
        except Exception as e:
            logger.error(f"C-Suite Trigger Chain failed: {e}")
            self._orchestrator.end_session(self.project_id, f'error: {str(e)[:100]}')

    async def _run_consensus_loop(self):
        reports = self.session['reports']

        while self.iteration <= self.max_iterations:
            iteration = self.iteration
            logger.info(f"=== LINEAR DEPENDENCY PROTOCOL — Iteration {iteration} ===")
            await self._emit({
                "type": "consensus_iteration",
                "iteration": iteration,
                "max_iterations": self.max_iterations,
                "timestamp": datetime.now().isoformat()
            })
            await self._emit({
                "type": "dialogue",
                "agent": "SYSTEM",
                "icon": "🔄",
                "color": "#eab308",
                "message": f"**Linear Dependency Protocol — Iteration {iteration}/{self.max_iterations}**\nPhase 1 → 1.5 → 2 → 3 → 4 chain initiating.",
                "timestamp": datetime.now().isoformat()
            })

            # ═══════════════════════════════════════════════════
            # PHASE 1: THE FOUNDATION — Market Pulse
            # ═══════════════════════════════════════════════════
            from strategic_sentiment import get_strategic_sentiment
            self.market_pulse_data = get_strategic_sentiment().analyze_market(self.project_id)
            verdict_str = self.market_pulse_data.get("verdict", "NEUTRAL")

            pivot_instruction = ""
            if verdict_str == "BEARISH":
                pivot_instruction = "\nWARNING: The Market Pulse is currently BEARISH (Low momentum, negative sentiment). You MUST present a 'Pivot Option' (e.g., lower CAC channels, feature pruning) in your strategy."

            cmo_prompt_override = f"{self.topic}\n\n[MARKET PULSE]: {self.market_pulse_data}\n{pivot_instruction}"
            # Phase 6: targeted objection mandates / Phase 4: chaos for revision runs
            if iteration > 1:
                cmo_prompt_override += self._mandate_block("CMO")
                cmo_prompt_override += self._chaos_text_block()

            await self._emit({
                "type": "market_pulse",
                "verdict": verdict_str,
                "velocity": self.market_pulse_data.get("trend_velocity", 5.0),
                "sentiment": self.market_pulse_data.get("public_sentiment_score", 0.0)
            })

            await self._emit({
                "type": "dialogue",
                "agent": "SYSTEM",
                "icon": "📊",
                "color": "#a855f7",
                "message": f"**PHASE 1: THE FOUNDATION**\nFetching Strategic Sentiment... Market Pulse: {verdict_str}. CMO pulling market research & quantifying costs...\nCPO & CLO running concurrently with the CMO → CEO → CTO dependency chain.",
                "timestamp": datetime.now().isoformat()
            })

            # ═══════════════════════════════════════════════════
            # PHASE 2 (Optimization): PARALLEL FOUNDATION NODES
            # CPO ∥ CLO ∥ (CMO → CEO → CTO). CPO/CLO have zero
            # upstream dependencies; the chain stays strictly
            # sequential because CTO assesses the CEO-validated
            # CMO strategy (Linear Dependency Protocol).
            # ═══════════════════════════════════════════════════
            foundation: Dict[str, Any] = {}

            async def run_cpo_node():
                if "CPO" not in self.triage_list:
                    logger.info("COO: Skipping CPO per CEO Triage.")
                    return
                await self._emit({
                    "type": "dialogue",
                    "agent": "SYSTEM",
                    "icon": "🎨",
                    "color": "#ec4899",
                    "message": "**PHASE 1.2: THE PRODUCT OFFICER**\nCPO evaluating Commerciability & UX Friction...",
                    "timestamp": datetime.now().isoformat()
                })
                cpo_handoff = f"Provide a MoSCoW prioritization and UX alignment report based on intention: '{self.message}'"
                if iteration > 1:
                    cpo_handoff += self._mandate_block("CPO")
                if 'CPO' not in reports:
                    cpo_resp, cpo_data, cpo_meta = await self._trigger_agent_response('CPO', cpo_handoff)
                    _cpo_report = parse_agent_response(cpo_resp, 'CPO', 'product', self.project_id, iteration,
                                                       structured_data=cpo_data, metadata=cpo_meta)
                    self._store.save(_cpo_report)
                    reports['CPO'] = _cpo_report
                    self._save_checkpoint('CPO')

            async def run_clo_node():
                if "CLO" not in self.triage_list:
                    logger.info("COO: Skipping CLO per CEO Triage.")
                    return
                await self._emit({
                    "type": "dialogue",
                    "agent": "SYSTEM",
                    "icon": "⚖️",
                    "color": "#64748b",
                    "message": "**PHASE 1.8: THE LEGAL OFFICER**\nCLO evaluating IP Security & Compliance...",
                    "timestamp": datetime.now().isoformat()
                })
                clo_handoff = f"Provide a rapid IP mapping and compliance scan for intention: '{self.message}'"
                if iteration > 1:
                    clo_handoff += self._mandate_block("CLO")
                if 'CLO' not in reports:
                    clo_resp, clo_data, clo_meta = await self._trigger_agent_response('CLO', clo_handoff)
                    _clo_report = parse_agent_response(clo_resp, 'CLO', 'legal', self.project_id, iteration,
                                                       structured_data=clo_data, metadata=clo_meta)
                    self._store.save(_clo_report)
                    reports['CLO'] = _clo_report
                    self._save_checkpoint('CLO')

            async def run_dependency_chain():
                # 1a. CMO: Market Research + Cost Quantification
                if "CMO" in self.triage_list:
                    if 'CMO' not in reports:
                        cmo_resp, cmo_data_raw, cmo_meta = await self._trigger_agent_response('CMO', cmo_prompt_override)
                        _cmo_report = parse_agent_response(cmo_resp, 'CMO', 'market', self.project_id, iteration,
                                                           structured_data=cmo_data_raw, metadata=cmo_meta)
                        self._store.save(_cmo_report)
                        await self._propose_wisdom(_cmo_report)
                        reports['CMO'] = _cmo_report
                        self._save_checkpoint('CMO')

                    cmo_report = reports['CMO']
                    cmo_hp = cmo_report.handoff_payload  # Strictly typed CMOHandoff fields
                    foundation.update({
                        "cmo_hp": cmo_hp,
                        "cmo_data": cmo_hp,
                        "cmo_marketing_cost": cmo_hp.get("marketing_cost", 0),
                        "cmo_projected_revenue": cmo_hp.get("projected_revenue", 0),
                        "cmo_demographic_reach": cmo_hp.get("demographic_reach", 0),
                        "cmo_cpa": cmo_hp.get("cost_per_acquisition", 0),
                        "cmo_recommendation": cmo_report.recommendation,
                        "cmo_strategy": cmo_hp.get(
                            "market_strategy",
                            cmo_report.detailed_report[:300] if isinstance(cmo_report.detailed_report, str) else "N/A"
                        ),
                    })
                else:
                    logger.info("COO: Skipping CMO per CEO Triage.")
                    foundation.update({
                        "cmo_hp": {}, "cmo_data": {},
                        "cmo_marketing_cost": 0, "cmo_projected_revenue": 0,
                        "cmo_demographic_reach": 0, "cmo_cpa": 0,
                        "cmo_recommendation": "SKIPPED", "cmo_strategy": "N/A",
                    })

                # 1b. CEO: Validate CMO strategy against growth targets
                foundation["ceo_alignment"] = "UNKNOWN"
                if "CEO" in self.triage_list:
                    ceo_handoff = self._orchestrator.build_handoff_context(
                        PipelineStep(agent_name='CEO', phase='validation', depends_on=['CMO']),
                        reports,
                        self.message,
                        iteration=iteration,
                        market_pulse=self.market_pulse_data,
                        chaos_scenario=self.active_chaos if iteration > 1 else None,
                        wisdom_vault=get_wisdom_vault(),
                    )
                    # Phase 5: CEO receives historical semantic memory
                    ceo_handoff += self.semantic_memory_block
                    if iteration > 1:
                        ceo_handoff += self._mandate_block("CEO")
                    if 'CEO' not in reports:
                        ceo_resp, ceo_data_raw, ceo_meta = await self._trigger_agent_response('CEO', ceo_handoff)
                        _ceo_report = parse_agent_response(ceo_resp, 'CEO', 'validation', self.project_id, iteration,
                                                           structured_data=ceo_data_raw, metadata=ceo_meta)
                        self._store.save(_ceo_report)
                        await self._propose_wisdom(_ceo_report)
                        reports['CEO'] = _ceo_report
                        self._save_checkpoint('CEO')

                    ceo_report = reports['CEO']
                    ceo_hp = ceo_report.handoff_payload  # Strictly typed CEOHandoff fields
                    ceo_approved = ceo_hp.get("approved_for_phase2", True)
                    foundation["ceo_alignment"] = ceo_hp.get("growth_target_alignment", "UNKNOWN")
                    ceo_target = ceo_hp.get("growth_target_annual", 0)

                    if not ceo_approved:
                        await self._emit({
                            "type": "dialogue",
                            "agent": "SYSTEM",
                            "icon": "⚠️",
                            "color": "#f59e0b",
                            "message": f"**Phase 1 GATE: CEO flags MISALIGNMENT**\nAlignment: {foundation['ceo_alignment']} | Growth Target: ${ceo_target:,.0f}\nRevision required. Cycling back.",
                            "timestamp": datetime.now().isoformat()
                        })
                else:
                    logger.info("COO: Skipping CEO validation per CEO Triage.")

                # PHASE 1.5: THE ENGINEER — CTO
                await self._emit({
                    "type": "dialogue",
                    "agent": "SYSTEM",
                    "icon": "🔧",
                    "color": "#06b6d4",
                    "message": f"**PHASE 1.5: THE ENGINEER**\nCTO assessing Technical Feasibility of CMO strategy...\n• Strategy: {str(foundation.get('cmo_strategy', 'N/A'))[:100]}...\n• CEO Alignment: {foundation.get('ceo_alignment', 'UNKNOWN')}",
                    "timestamp": datetime.now().isoformat()
                })

                # CTO receives CMO strategy + CEO validation via orchestrator handoff
                foundation.setdefault("cto_data", {})
                foundation.setdefault("cto_hp", {})
                if "CTO" in self.triage_list:
                    cto_handoff = self._orchestrator.build_handoff_context(
                        PipelineStep(agent_name='CTO', phase='technical', depends_on=['CMO', 'CEO']),
                        reports,
                        self.message,
                        iteration=iteration,
                        market_pulse=self.market_pulse_data,
                        chaos_scenario=self.active_chaos if iteration > 1 else None,
                        wisdom_vault=get_wisdom_vault(),
                    )
                    if iteration > 1:
                        cto_handoff += self._mandate_block("CTO")
                    if 'CTO' not in reports:
                        cto_resp, cto_data_raw, cto_meta = await self._trigger_agent_response('CTO', cto_handoff)
                        _cto_report = parse_agent_response(cto_resp, 'CTO', 'technical', self.project_id, iteration,
                                                           structured_data=cto_data_raw, metadata=cto_meta)
                        self._store.save(_cto_report)
                        await self._propose_wisdom(_cto_report)
                        reports['CTO'] = _cto_report
                        self._save_checkpoint('CTO')

                    cto_report = reports['CTO']
                    cto_hp = cto_report.handoff_payload  # Strictly typed CTOHandoff fields

                    cto_feasibility = float(cto_hp.get("technical_feasibility_score", 5))
                    cto_timeline = cto_hp.get("implementation_timeline_weeks", 0)
                    dev_buffer = cto_hp.get("development_buffer_weeks", 0)
                    # Compute development_buffer_weeks if LLM didn't provide it
                    if not dev_buffer and cto_timeline:
                        dev_buffer = round(cto_timeline * 1.5, 1) if cto_feasibility < 7 else cto_timeline

                    foundation.update({
                        "cto_hp": cto_hp,
                        "cto_data": cto_hp,
                        "cto_feasibility": cto_feasibility,
                        "cto_project_type": cto_hp.get("project_type", "DIGITAL"),
                        "cto_tech_stack": cto_hp.get("tech_stack", []),
                        "cto_automation_layer": cto_hp.get("automation_monitoring_layer", ""),
                        "cto_skills_blocks": cto_hp.get("skills_library_blocks", []),
                        "cto_timeline": cto_timeline,
                        "cto_v3_compliance": cto_hp.get("v3_compliance", "UNKNOWN"),
                        "cto_pre_deploy": cto_hp.get("pre_deploy_gate_status", "UNKNOWN"),
                        "cto_recommendation": cto_report.recommendation,
                        "infra_cost": cto_hp.get("infrastructure_cost_estimate", 0),
                        "dev_buffer": dev_buffer,
                        "tech_debt_premium": cto_hp.get("tech_debt_risk_premium_pct", 0),
                        "gate_source": cto_hp.get(
                            "gate_source",
                            "aether_native" if self._pre_deploy_available else "llm_estimate"
                        ),
                    })

                    # TECHNICAL GATE CHECK via Orchestrator
                    _cto_gate_step = PipelineStep(agent_name='CTO', phase='technical', is_gate=True, gate_threshold=4.0)
                    _cto_gate_result = self._orchestrator.check_gate(_cto_gate_step, cto_report)
                    if not _cto_gate_result['passed']:
                        await self._emit({
                            "type": "dialogue",
                            "agent": "SYSTEM",
                            "icon": "🛑",
                            "color": "#ef4444",
                            "message": f"**TECHNICAL GATE FAILURE**\n{_cto_gate_result['reason']}\nCFO modeling BLOCKED. CTO recommends: {foundation['cto_recommendation']}.\nRevision required.",
                            "timestamp": datetime.now().isoformat()
                        })
                else:
                    logger.info("COO: Skipping CTO per CEO Triage.")
                    foundation.update({
                        "cto_feasibility": 0.0, "cto_project_type": "GLOBAL",
                        "cto_timeline": 0, "dev_buffer": 0, "infra_cost": 0,
                        "tech_debt_premium": 0, "cto_pre_deploy": "UNKNOWN",
                    })

            try:
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(run_cpo_node())
                    tg.create_task(run_clo_node())
                    tg.create_task(run_dependency_chain())
            except BaseExceptionGroup as eg:
                # Preserve the original single-exception contract
                # (e.g. coo_agent.OpBudgetExceeded must reach run_session's handler).
                raise eg.exceptions[0] from eg

            cmo_hp = foundation.get("cmo_hp", {})
            cmo_data = foundation.get("cmo_data", {})
            cmo_marketing_cost = foundation.get("cmo_marketing_cost", 0)
            cmo_projected_revenue = foundation.get("cmo_projected_revenue", 0)
            cto_hp = foundation.get("cto_hp", {})
            cto_data = foundation.get("cto_data", {})
            cto_feasibility = foundation.get("cto_feasibility", 0.0)
            cto_project_type = foundation.get("cto_project_type", "GLOBAL")
            cto_timeline = foundation.get("cto_timeline", 0)
            dev_buffer = foundation.get("dev_buffer", 0)
            infra_cost = foundation.get("infra_cost", 0)
            tech_debt_premium = foundation.get("tech_debt_premium", 0)
            cto_pre_deploy = foundation.get("cto_pre_deploy", "UNKNOWN")

            # ═══════════════════════════════════════════════════
            # PHASE 2: THE MODEL — CFO
            # ═══════════════════════════════════════════════════
            await self._emit({
                "type": "dialogue",
                "agent": "SYSTEM",
                "icon": "💰",
                "color": "#22c55e",
                "message": f"**PHASE 2: THE MODEL**\nCFO building Business Plan utilizing CTO Phase 1.5 USE Output:\n• Timeline: {cto_timeline}wk (Buffer: {dev_buffer}wk)\n• Infra Cost: ${infra_cost:,.0f}/mo | Tech Debt Premium: {tech_debt_premium}%\n• Gate Status: {cto_pre_deploy}",
                "timestamp": datetime.now().isoformat()
            })

            # ── AETHER-NATIVE CFO EXCEL EXTRACTION ──────────────────
            # Run the mathematical generation using native python/pandas
            native_cfo_msg = ""
            cfo_native_result = {}
            try:
                from cfo_excel_architect import get_cfo_architect
                cfo_arch = get_cfo_architect()
                cfo_native_result = cfo_arch.generate_business_plan(
                    project_id=self.project_id,
                    cmo_data=cmo_data,
                    cto_data=cto_data,
                    market_pulse=self.market_pulse_data
                )
                if cfo_native_result.get("status") == "success":
                    native_cfo_msg = (
                        f"\n\n=== Native Excel Architect Output ===\n"
                        f"- Excel Artifact Generated: {cfo_native_result.get('file_name')}\n"
                        f"- Fragility Index: {cfo_native_result.get('fragility_index')}/100\n"
                        f"- Total Computed Cost Basis: ${cfo_native_result.get('total_cost'):,.2f}\n"
                        f"- Baseline ROI: {cfo_native_result.get('roi_percentage')}%\n"
                        f"- Risk-Adjusted ROI: {cfo_native_result.get('risk_adjusted_roi')}%\n"
                        f"- Net Present Value (NPV): ${cfo_native_result.get('npv'):,.2f}\n"
                    )
                    await self._emit({
                        "type": "dialogue",
                        "agent": "SYSTEM",
                        "icon": "📊",
                        "color": "#10b981",
                        "message": f"**CFO EXCEL ARCHITECT**\nNative Fragility Report generated: {cfo_native_result.get('file_name')}\nTotal Cost Basis: ${cfo_native_result.get('total_cost'):,.0f} | Risk-Adj ROI: {cfo_native_result.get('risk_adjusted_roi')}%",
                        "timestamp": datetime.now().isoformat()
                    })
            except Exception as e:
                logger.warning(f"Native CFO failed: {e}")

            # CFO LLM receives upstream reports via orchestrator + native Excel output
            cfo_handoff = self._orchestrator.build_handoff_context(
                PipelineStep(agent_name='CFO', phase='financials', depends_on=['CMO', 'CEO', 'CTO']),
                reports,
                self.message,
                iteration=iteration,
                market_pulse=self.market_pulse_data,
                chaos_scenario=self.active_chaos if iteration > 1 else None,
                wisdom_vault=get_wisdom_vault(),
            )
            # Append Native Excel results if available
            if native_cfo_msg:
                cfo_handoff += native_cfo_msg
            if iteration > 1:
                cfo_handoff += self._mandate_block("CFO")
            cfo_resp, cfo_data, cfo_meta = await self._trigger_agent_response('CFO', cfo_handoff)

            # ── WAR ROOM: Parse CFO into typed WarRoomReport ──
            cfo_report = parse_agent_response(cfo_resp, 'CFO', 'financials', self.project_id, iteration,
                                              structured_data=cfo_data, metadata=cfo_meta)

            # ═══════════════════════════════════════════════════
            # PHASE 3 (Optimization): MATHEMATICAL HANDOFF RIGOR
            # If the native Excel Architect computed the model,
            # its figures are ground truth — overwrite the LLM's
            # narrative numbers BEFORE the report is stored,
            # handed to the Critic, or captured as predictions.
            # ═══════════════════════════════════════════════════
            if native_cfo_msg and cfo_native_result.get("status") == "success":
                _native_sync = {
                    "roi_percentage": cfo_native_result.get("roi_percentage"),
                    "roas": cfo_native_result.get("roas"),
                    "total_cost_basis": cfo_native_result.get("total_cost"),
                    "npv": cfo_native_result.get("npv"),
                    "fragility_index": cfo_native_result.get("fragility_index"),
                    "risk_adjusted_roi": cfo_native_result.get("risk_adjusted_roi"),
                }
                _synced_keys = []
                for k, v in _native_sync.items():
                    if v is None:
                        continue
                    try:
                        v = float(v)
                    except (TypeError, ValueError):
                        continue
                    cfo_report.handoff_payload[k] = v
                    cfo_report.detailed_report[k] = v
                    _synced_keys.append(k)
                if _synced_keys:
                    cfo_report.metadata["native_excel_synced"] = _synced_keys
                    logger.info(f"[CFO SYNC] LLM narrative aligned to native Excel truth: {_synced_keys}")

            self._store.save(cfo_report)
            await self._propose_wisdom(cfo_report)
            reports['CFO'] = cfo_report
            cfo_hp = cfo_report.handoff_payload  # Strictly typed CFOHandoff fields (Excel-synced)

            cfo_roi = cfo_hp.get("roi_percentage", 0)
            cfo_roas = cfo_hp.get("roas", 0)
            cfo_breakeven = cfo_hp.get("breakeven_month", 0)

            # ═══════════════════════════════════════════════════
            # PHASE 4 (Optimization): DYNAMIC RED-TEAM CHAOS
            # Select the drill that attacks this plan's weakest
            # dimension; the Critic evaluates survival now, and
            # the C-Suite must adapt next iteration if blocked.
            # ═══════════════════════════════════════════════════
            self.active_chaos = self.select_dynamic_chaos(cmo_hp, cto_hp, cfo_hp)
            if self.active_chaos:
                await self._emit({
                    "type": "dialogue",
                    "agent": "RED_TEAM",
                    "icon": "🚨",
                    "color": "#dc2626",
                    "message": (
                        f"**DYNAMIC RED TEAM DRILL SELECTED** — `{self.active_chaos.scenario_id}` "
                        f"(severity {self.active_chaos.severity:.0%})\n{self.active_chaos.description}\n"
                        f"The Critic will evaluate whether this plan SURVIVES the scenario."
                    ),
                    "timestamp": datetime.now().isoformat()
                })

            # ═══════════════════════════════════════════════════
            # PHASE 3: THE ADVERSARY — CRITIC
            # ═══════════════════════════════════════════════════
            await self._emit({
                "type": "dialogue",
                "agent": "SYSTEM",
                "icon": "🔍",
                "color": "#ef4444",
                "message": f"**PHASE 3: THE ADVERSARY**\nCRITIC evaluating completed Business Plan:\n• CMO Cost: ${cmo_marketing_cost:,.0f} | Revenue: ${cmo_projected_revenue:,.0f}\n• CFO ROI: {cfo_roi}% | ROAS: {cfo_roas}x | Breakeven: Month {cfo_breakeven}",
                "timestamp": datetime.now().isoformat()
            })

            # CRITIC receives ALL upstream reports via orchestrator handoff
            critic_handoff = self._orchestrator.build_handoff_context(
                PipelineStep(agent_name='CRITIC', phase='adversarial', depends_on=['CMO', 'CEO', 'CTO', 'CFO']),
                reports,
                self.message,
                iteration=iteration,
                market_pulse=self.market_pulse_data,
                chaos_scenario=self.active_chaos,
                wisdom_vault=get_wisdom_vault(),
            )
            # Phase 5: Critic receives historical semantic memory
            critic_handoff += self.semantic_memory_block

            # ── Outcome Loop: base rates (this plan vs. all past plans) ──
            try:
                from warroom_outcomes import get_prediction_ledger
                _current_claims = {}
                _current_claims.update(self._numeric_handoff(cmo_hp if "CMO" in self.triage_list else {}))
                _current_claims.update(self._numeric_handoff(cto_hp))
                _current_claims.update(self._numeric_handoff(cfo_hp))
                _base_rates = get_prediction_ledger().base_rate_block(_current_claims)
                if _base_rates:
                    critic_handoff += f"\n\n{_base_rates}"
            except Exception as e:
                logger.warning(f"Base-rate injection failed: {e}")

            # ── Anti-gaming: revision audit for iterations > 1 ──
            _current_metrics = {
                "CMO": self._numeric_handoff(cmo_hp if "CMO" in self.triage_list else {}),
                "CTO": self._numeric_handoff(cto_hp),
                "CFO": self._numeric_handoff(cfo_hp),
            }
            critic_handoff += self._build_revision_audit(
                self.session.get('prior_metrics'), _current_metrics, iteration
            )

            # ═══════════════════════════════════════════════════
            # PHASE 3 & 4: ASYNCHRONOUS PARALLELISM
            # Run CRITIC Evaluation & Phantom UI Pathfinder concurrently
            # ═══════════════════════════════════════════════════
            from phantom_ui_pathfinder import run_ui_audit

            # Phase Detection Logic
            is_architecture_phase = any(kw in self.msg_lower for kw in ["initialize", "architect", "genesis"])

            if is_architecture_phase:
                await self._emit({
                    "type": "dialogue",
                    "agent": "PHANTOM_QA",
                    "icon": "👻",
                    "color": "#14b8a6",
                    "message": "Playwright Deep Audit: SKIPPED (Architecture Phase Detected). UI testing deferred to deployment.",
                    "timestamp": datetime.now().isoformat()
                })

                critic_tuple = await self._trigger_agent_response('CRITIC', critic_handoff)
                phantom_ui_res = {"verdict": "SKIPPED", "score": 100, "errors": []}
            else:
                # Tell frontend that parallel execution is starting
                await self._emit({
                    "type": "dialogue",
                    "agent": "SYSTEM",
                    "icon": "👻",
                    "color": "#14b8a6",
                    "message": "**PHASE 3 & 4 PARALLEL EXECUTION**\nCritic reviewing logic while Phantom Pathfinder headless UI stress test runs...",
                    "timestamp": datetime.now().isoformat()
                })

                critic_task = asyncio.create_task(self._trigger_agent_response('CRITIC', critic_handoff))
                phantom_task = asyncio.to_thread(run_ui_audit, self.project_id)
                critic_tuple, phantom_ui_res = await asyncio.gather(critic_task, phantom_task)
            critic_resp, critic_data, critic_meta = critic_tuple

            # ── WAR ROOM: Parse CRITIC into typed WarRoomReport ──
            critic_report = parse_agent_response(critic_resp, 'CRITIC', 'adversarial', self.project_id, iteration,
                                                 structured_data=critic_data, metadata=critic_meta)

            # Extract Critic Agreement Level from typed report.
            # Fallback parses only an explicit "agreement[_level]: N"
            # statement and clamps to the 1-10 scale.
            critic_score = float(critic_report.agreement_level or 0)
            if critic_score == 0:
                score_match = re.search(r'(?i)agreement[_\s]*(?:level|score)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:/\s*10)?', critic_resp)
                _parsed = float(score_match.group(1)) if score_match else 5.0
                critic_score = _parsed if 1.0 <= _parsed <= 10.0 else 5.0
                critic_report.agreement_level = critic_score

            # Objection ledger: HIGH-severity objections block consensus
            # regardless of the scalar score.
            _high_objections = [
                o for o in (critic_report.objections or [])
                if isinstance(o, str) and o.strip().upper().startswith("HIGH")
            ]

            self._store.save(critic_report, is_gate=True, gate_score=critic_score)
            await self._propose_wisdom(critic_report)
            reports['CRITIC'] = critic_report

            # ── Phase 7: Performance Review (The Learning Engine) ──
            if critic_score >= 8.0 or critic_score <= 4.0:
                asyncio.create_task(self._run_performance_review(critic_resp, critic_score, cto_project_type))

            # Update Persuasion Score (UI Meter)
            self._set_persuasion(critic_score)
            await self._emit({
                "type": "persuasion_update",
                "score": self.persuasion_score,
                "reason": (
                    f"Critic: {critic_data.get('verdict', 'N/A')} ({self.persuasion_score}/10) | "
                    f"Cost Challenge: {str(critic_data.get('cost_challenge', 'N/A'))[:60]}"
                )
            })

            # ═══════════════════════════════════════════════════
            # EVALUATE AUDITOR VERDICT (Phase 4 Results)
            # ═══════════════════════════════════════════════════
            phantom_verdict = phantom_ui_res.get("verdict", "FAIL")
            phantom_score = phantom_ui_res.get("score", 0)

            if phantom_verdict == "FAIL":
                errors = phantom_ui_res.get("errors", [])
                err_str = errors[0] if errors else "General UI Failure"
                logger.error(f"Phantom UI Gate execution failed: {err_str}")

            # Schema Validity: Social_Media_Matrix.json
            project_dir = os.path.join(self._script_dir, "projects", self.project_id)
            schema_result = self._validate_social_media_schema(project_dir)
            if not schema_result.get("valid", True):
                phantom_verdict = "FAIL"
                logger.warning(f"Schema Validity FAILED: {schema_result.get('error')}")

            # Broadcast Phantom QA verdict
            schema_status = "✅ Valid" if schema_result.get("valid") else f"❌ {schema_result.get('error', 'Invalid')}"
            await self._emit({
                "type": "dialogue",
                "agent": "SYSTEM",
                "icon": "👻",
                "color": "#14b8a6",
                "message": (
                    f"**Phantom QA Audit Report:**\n"
                    f"Verdict: {phantom_verdict} | Score: {phantom_score}/100\n"
                    f"Schema Validity: {schema_status}\n"
                    f"Safe for Execution: {'✅ YES' if phantom_verdict == 'PASS' else '❌ NO'}"
                ),
                "timestamp": datetime.now().isoformat()
            })

            # ═══════════════════════════════════════════════════
            # EXIT CONDITION: Critic > 9.0 AND Phantom PASS/SKIPPED
            # AND no standing HIGH-severity objections
            # ═══════════════════════════════════════════════════
            if _high_objections and critic_score > 9.0:
                await self._emit({
                    "type": "dialogue",
                    "agent": "SYSTEM",
                    "icon": "⛔",
                    "color": "#f97316",
                    "message": (
                        f"**CONSENSUS BLOCKED — STANDING HIGH OBJECTIONS**\n"
                        f"Score {critic_score}/10 met the bar, but unresolved HIGH objections block approval:\n"
                        + "\n".join(f"• {o}" for o in _high_objections[:3])
                    ),
                    "timestamp": datetime.now().isoformat()
                })

            if critic_score > 9.0 and phantom_verdict in ["PASS", "SKIPPED"] and not _high_objections:
                logger.info("LINEAR DEPENDENCY PROTOCOL: Consensus Reached!")

                # ── Outcome Loop: capture the approved plan's claims
                # as tracked predictions (the confrontation with
                # reality starts here). Runs AFTER the Phase 3 Excel
                # sync, so predictions track computed truth.
                try:
                    from warroom_outcomes import get_prediction_ledger
                    _preds = get_prediction_ledger().capture_from_reports(
                        self.project_id, reports, iteration)
                    if _preds:
                        await self._emit({
                            "type": "dialogue",
                            "agent": "SYSTEM",
                            "icon": "📒",
                            "color": "#0ea5e9",
                            "message": (
                                f"**PREDICTION LEDGER ARMED**\n"
                                f"{len(_preds)} quantitative claims from this plan are now "
                                f"tracked against reality (POST /api/warroom/outcomes/"
                                f"{self.project_id}/actual to reconcile). Tripwires will demand "
                                f"a reconvene if assumptions are violated."
                            ),
                            "timestamp": datetime.now().isoformat()
                        })
                except Exception as e:
                    logger.error(f"Prediction capture failed: {e}")
                await self._emit({
                    "type": "consensus_iteration",
                    "iteration": iteration,
                    "max_iterations": self.max_iterations,
                    "status": "CONSENSUS",
                    "timestamp": datetime.now().isoformat()
                })
                await self._emit({
                    "type": "dialogue",
                    "agent": "SYSTEM",
                    "icon": "✅",
                    "color": "#10b981",
                    "message": (
                        f"**CONSENSUS REACHED (Iteration {iteration})**\n"
                        f"Critic: {critic_score}/10 ✅ | Phantom QA: {phantom_verdict} ✅\n"
                        f"Business Plan: CMO ${cmo_marketing_cost:,.0f} → CTO {cto_feasibility}/10 → CFO ROI {cfo_roi}% → APPROVED\n"
                        f"Safe for Execution. Deliberation terminated."
                    ),
                    "timestamp": datetime.now().isoformat()
                })
                break

            # ── Aether Memory Compression for next iteration ──
            compressed = self._compress_context(cmo_data, cto_data, cfo_data, critic_data,
                                                phantom_verdict, phantom_score)
            # Build re-entry topic with Critic's specific objections
            cost_challenge = critic_data.get("cost_challenge", "No specific cost challenge.")
            revenue_challenge = critic_data.get("revenue_challenge", "No specific revenue challenge.")
            self.topic = (
                f"ITERATION {iteration} FAILED CONSENSUS — REVISE AND RESUBMIT:\n\n"
                f"Previous Results: {compressed}\n\n"
                f"CRITIC COST CHALLENGE: {cost_challenge}\n"
                f"CRITIC REVENUE CHALLENGE: {revenue_challenge}\n"
                f"Critic Objections: {'; '.join(str(o) for o in critic_data.get('objections', []))}\n"
                f"Evidence Demanded: {critic_data.get('evidence_demanded', 'N/A')}\n"
                f"Phantom Verdict: {phantom_verdict} (Score: {phantom_score}/100)\n\n"
                f"CMO: Revise your marketing_cost and projected_revenue to address the Critic's challenges.\n"
                f"Original directive: {self.message}"
            )

            # ── Phase 6: route tagged objections to their owners ──
            self.objection_mandates = self._route_objections(critic_report.objections)
            if self.objection_mandates:
                _routing_summary = " | ".join(
                    f"{agent}: {len(items)}" for agent, items in self.objection_mandates.items()
                )
                await self._emit({
                    "type": "dialogue",
                    "agent": "SYSTEM",
                    "icon": "🎯",
                    "color": "#f97316",
                    "message": f"**OBJECTION ROUTING** Standing objections assigned for mandatory resolution → {_routing_summary}",
                    "timestamp": datetime.now().isoformat()
                })

            # ── Re-open the debate for revision ──
            # The `if 'X' not in reports` guards exist for checkpoint
            # resume, but they also froze first-iteration outputs:
            # CMO/CEO/CTO/CPO/CLO never re-ran, so the revision
            # directive above never reached them. Snapshot this
            # iteration's numbers for the Critic's revision audit,
            # then clear the stale reports. CRITIC stays — its
            # feedback is injected into iteration>1 contexts.
            self.session['prior_metrics'] = _current_metrics
            for _stale_agent in ("CMO", "CEO", "CPO", "CTO", "CLO"):
                reports.pop(_stale_agent, None)
            self._save_checkpoint('ITERATION_RESET')

            self.iteration += 1

        if self.iteration > self.max_iterations:
            await self._emit({
                "type": "consensus_iteration",
                "iteration": self.max_iterations,
                "max_iterations": self.max_iterations,
                "status": "MAX_REACHED",
                "timestamp": datetime.now().isoformat()
            })
            await self._emit({
                "type": "dialogue",
                "agent": "SYSTEM",
                "icon": "🛑",
                "color": "#ef4444",
                "message": f"Linear Dependency Protocol: Max iterations ({self.max_iterations}) reached without consensus. Awaiting Commander hard override.",
                "timestamp": datetime.now().isoformat()
            })
