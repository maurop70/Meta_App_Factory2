"""
warroom_protocol.py — War Room Report Contract & Dynamic Orchestrator
═════════════════════════════════════════════════════════════════════════
The universal schema and orchestration engine for Project War Room.

Every agent in the War Room produces a WarRoomReport. The Orchestrator
composes dynamic execution pipelines based on the Commander's intent,
routes reports between agents, and persists everything to the
Boardroom Exchange.

Architecture:
    Commander Input → CEO Orchestrator → Dynamic Pipeline
    → Agent₁ → WarRoomReport → Agent₂ → WarRoomReport → ... → Critic
    → Consensus Check → Approve / Revise Loop

Author: Antigravity Master Architect
Version: 1.1.0
"""

import os
import json
import logging
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from pydantic import BaseModel, Field

logger = logging.getLogger("WarRoom.Protocol")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOARDROOM_DIR = os.path.join(SCRIPT_DIR, "Project_Aether", "Boardroom_Exchange")
REPORTS_DIR = os.path.join(BOARDROOM_DIR, "reports")


# ═══════════════════════════════════════════════════════════════════
# §0  TYPED HANDOFF PAYLOADS — Strictly Typed Agent-to-Agent Contracts
# ═══════════════════════════════════════════════════════════════════

class CMOHandoff(BaseModel):
    """CMO -> CEO/CTO/CFO handoff. Strictly typed for CFO Excel Architect."""
    marketing_cost: float = Field(0.0, description="Total projected marketing spend ($)")
    projected_revenue: float = Field(0.0, description="Projected annual revenue ($)")
    market_size_tam: float = Field(0.0, description="Total Addressable Market ($)")
    market_size_sam: float = Field(0.0, description="Serviceable Addressable Market ($)")
    market_size_som: float = Field(0.0, description="Serviceable Obtainable Market ($)")
    demographic_reach: int = Field(0, description="Target audience size")
    cost_per_acquisition: float = Field(0.0, description="Customer Acquisition Cost ($)")
    customer_profile: str = Field("", description="Ideal customer persona summary")
    market_strategy: str = Field("", description="Go-to-market strategy summary")
    revenue_timeline_months: int = Field(12, description="Months to projected revenue")
    competitive_moat: str = Field("", description="Key competitive advantage")
    channels: List[str] = Field(default_factory=list, description="Marketing channels")


class CEOHandoff(BaseModel):
    """CEO -> CTO/CFO handoff. Strategic validation output."""
    approved_for_phase2: bool = Field(True, description="CEO approves moving to next phase")
    growth_target_alignment: str = Field("UNKNOWN", description="ALIGNED / MISALIGNED / PARTIAL")
    growth_target_annual: float = Field(0.0, description="Annual growth target ($)")
    strategic_direction: str = Field("", description="CEO's strategic guidance")
    scope_creep_flags: List[str] = Field(default_factory=list, description="Detected scope creep items")
    priority_override: Optional[str] = Field(None, description="CEO priority override instruction")


class CTOHandoff(BaseModel):
    """CTO -> CFO handoff. Technical feasibility output for financial modeling."""
    technical_feasibility_score: float = Field(5.0, ge=1.0, le=10.0, description="Feasibility (1-10)")
    project_type: str = Field("DIGITAL", description="DIGITAL / PHYSICAL / HYBRID")
    tech_stack: List[str] = Field(default_factory=list, description="Recommended technology stack")
    implementation_timeline_weeks: float = Field(0.0, description="Estimated dev timeline (weeks)")
    v3_compliance: str = Field("UNKNOWN", description="V3 Resilience Core compliance status")
    pre_deploy_gate_status: str = Field("UNKNOWN", description="PreDeploy gate result")
    infrastructure_cost_estimate: float = Field(0.0, description="Monthly infrastructure cost ($)")
    development_buffer_weeks: float = Field(0.0, description="Buffer weeks for risk")
    tech_debt_risk_premium_pct: float = Field(0.0, description="Tech debt risk premium (%)")
    automation_monitoring_layer: str = Field("", description="Monitoring/automation approach")
    skills_library_blocks: List[str] = Field(default_factory=list, description="Required skill blocks")
    gate_source: str = Field("llm_estimate", description="aether_native or llm_estimate")


class CFOHandoff(BaseModel):
    """CFO -> Critic/CEO handoff. Financial model output."""
    roi_percentage: float = Field(0.0, description="Return on Investment (%)")
    roas: float = Field(0.0, description="Return on Ad Spend (x)")
    breakeven_month: int = Field(0, description="Month when breakeven is reached")
    burn_rate: float = Field(0.0, description="Monthly burn rate ($)")
    total_cost_basis: float = Field(0.0, description="Total project cost ($)")
    npv: float = Field(0.0, description="Net Present Value ($)")
    fragility_index: float = Field(0.0, description="Financial fragility score (0-100)")
    risk_adjusted_roi: float = Field(0.0, description="Risk-adjusted ROI (%)")
    profitability_timeline: str = Field("", description="Path to profitability summary")
    business_plan_summary: str = Field("", description="Executive business plan summary")
    funding_required: float = Field(0.0, description="Capital required ($)")

class CPOHandoff(BaseModel):
    """CPO -> Critic/CEO handoff. Synthesized product strategy output using forced Chain-of-Thought (CoT)."""
    # NODE 1: User Empathy Engine (Forces the UX logic first)
    friction_elimination_notes: List[str] = Field(default_factory=list, description="UI/UX friction points actively mitigated")
    
    # NODE 2: Commercial Strategist (Forces the money logic second)
    value_capture_mechanism: str = Field(..., description="Clear monetization strategy for survival")
    commercial_viability_score: float = Field(5.0, ge=1.0, le=10.0, description="Commercial viability rating")
    
    # NODE 3: MVP Butcher (Synthesizes Nodes 1 & 2 into the final cut)
    cut_features: List[str] = Field(default_factory=list, description="Ruthlessly butchered features to save timeline")
    moscow_must_haves: List[str] = Field(default_factory=list, description="Critical features for launch")
    moscow_should_haves: List[str] = Field(default_factory=list, description="Important differentiators")


class CLOHandoff(BaseModel):
    """CLO -> Critic/CEO handoff. Legal compliance output."""
    compliance_status: str = Field("UNKNOWN", description="CLEAR / WARNING / BLOCKED")
    ip_clearance: str = Field("UNKNOWN", description="IP/trademark clearance status")
    regulatory_risks: List[str] = Field(default_factory=list, description="Identified regulatory risks")
    required_agreements: List[str] = Field(default_factory=list, description="Required legal agreements")
    jurisdiction_notes: str = Field("", description="Jurisdiction-specific notes")


class CriticHandoff(BaseModel):
    """Critic feedback output. Used for consensus loop."""
    agreement_level: float = Field(5.0, ge=1.0, le=10.0, description="Consensus score (1-10)")
    verdict: str = Field("REVISE", description="APPROVE / REVISE / REJECT")
    objections: List[str] = Field(default_factory=list, description="Specific objections")
    cost_challenge: str = Field("", description="Challenge to cost assumptions")
    revenue_challenge: str = Field("", description="Challenge to revenue projections")
    evidence_demanded: str = Field("", description="Specific evidence requested")


# ═══════════════════════════════════════════════════════════════════
# §0.1  CHAOS SCENARIO — Red Team / Adversarial Drill Injection
# ═══════════════════════════════════════════════════════════════════

class ChaosScenario(BaseModel):
    """A simulated crisis injected into agent prompts during Red Team drills."""
    scenario_id: str = Field(..., description="Unique ID e.g. 'market_crash_q3'")
    type: str = Field(..., description="market_crash | api_failure | competitor_launch | regulation_change")
    severity: float = Field(0.5, ge=0.0, le=1.0, description="Crisis severity (0-1)")
    description: str = Field(..., description="Human-readable crisis description")
    injected_constraints: Dict[str, Any] = Field(
        default_factory=dict,
        description="Specific constraints agents must address"
    )


CHAOS_LIBRARY: List[ChaosScenario] = [
    ChaosScenario(
        scenario_id="market_crash", type="market_crash", severity=0.8,
        description="Global market downturn — TAM drops 60%, investor confidence freezes for 18 months",
        injected_constraints={"tam_reduction_pct": 60, "funding_frozen": True, "runway_pressure_months": 6},
    ),
    ChaosScenario(
        scenario_id="api_price_shock", type="api_failure", severity=0.7,
        description="Primary API provider announces 300% price increase with 30-day sunset on current tier",
        injected_constraints={"infra_cost_multiplier": 3.0, "migration_deadline_weeks": 4, "api_alternatives_required": True},
    ),
    ChaosScenario(
        scenario_id="competitor_blitz", type="competitor_launch", severity=0.6,
        description="Well-funded competitor launches identical product with $10M marketing budget and 6-month head start",
        injected_constraints={"competitor_budget": 10_000_000, "market_share_loss_pct": 30, "differentiation_required": True},
    ),
    ChaosScenario(
        scenario_id="regulation_shock", type="regulation_change", severity=0.9,
        description="New data privacy law requires complete architectural overhaul within 90 days or face shutdown",
        injected_constraints={"compliance_deadline_days": 90, "refactor_required": True, "legal_review_mandatory": True},
    ),
]


# ═══════════════════════════════════════════════════════════════════
# §0.2  STRATEGY MODE — Commander's Intent Shadowing
# ═══════════════════════════════════════════════════════════════════

class StrategyMode(BaseModel):
    """Commander's strategic philosophy for this War Room session.

    Selected BEFORE agents begin work. Shapes every prompt and gate threshold.
    """
    mode: str = Field("balanced", description="aggressive_growth | lean_mvp | custom | balanced")
    label: str = Field("Balanced", description="Display label for UI")
    gate_threshold_modifier: float = Field(
        0.0,
        description="Adjusts default gate thresholds. -1.0 = more permissive, +1.0 = stricter"
    )
    risk_tolerance: str = Field("moderate", description="high | moderate | low")
    budget_priority: str = Field("balanced", description="speed | cost | quality | balanced")
    custom_directive: str = Field("", description="Commander's custom strategic guidance")

    def to_prompt_block(self) -> str:
        """Generate the prompt injection block for agent context."""
        if self.mode == "balanced" and not self.custom_directive:
            return ""  # No injection for default balanced mode

        lines = [f"=== STRATEGIC PHILOSOPHY: {self.label} ==="]
        lines.append(f"Risk Tolerance: {self.risk_tolerance.upper()} | Budget Priority: {self.budget_priority.upper()}")

        if self.mode == "aggressive_growth":
            lines.append(
                "Optimize for SPEED and MARKET CAPTURE. Accept higher burn rates for first-mover advantage. "
                "Prioritize TAM capture over profitability. Growth > margins."
            )
        elif self.mode == "lean_mvp":
            lines.append(
                "Optimize for COST EFFICIENCY and VALIDATION. Minimize spend, prove assumptions first. "
                "No feature that isn't directly tied to revenue. Survival > growth."
            )
        if self.custom_directive:
            lines.append(f"Commander's Directive: {self.custom_directive}")

        return "\n".join(lines)


STRATEGY_PRESETS: Dict[str, StrategyMode] = {
    "aggressive_growth": StrategyMode(
        mode="aggressive_growth",
        label="\U0001f680 Aggressive Growth",
        gate_threshold_modifier=-1.0,
        risk_tolerance="high",
        budget_priority="speed",
    ),
    "lean_mvp": StrategyMode(
        mode="lean_mvp",
        label="\U0001f52c Lean MVP",
        gate_threshold_modifier=+1.0,
        risk_tolerance="low",
        budget_priority="cost",
    ),
    "balanced": StrategyMode(
        mode="balanced",
        label="\u2696\ufe0f Balanced",
        gate_threshold_modifier=0.0,
        risk_tolerance="moderate",
        budget_priority="balanced",
    ),
}


def get_strategy_mode(mode: str, custom_directive: str = "") -> StrategyMode:
    """Get a StrategyMode by key, supporting custom directives."""
    if mode == "custom":
        return StrategyMode(
            mode="custom",
            label="\u270f\ufe0f Custom",
            gate_threshold_modifier=0.0,
            risk_tolerance="moderate",
            budget_priority="balanced",
            custom_directive=custom_directive,
        )
    return STRATEGY_PRESETS.get(mode, STRATEGY_PRESETS["balanced"])


# Mapping from agent name -> typed handoff model
HANDOFF_MODELS: Dict[str, type] = {
    "CMO": CMOHandoff,
    "CEO": CEOHandoff,
    "CTO": CTOHandoff,
    "CFO": CFOHandoff,
    "CLO": CLOHandoff,
    "CRITIC": CriticHandoff,
}


def build_typed_handoff(agent: str, raw_data: Dict[str, Any]) -> BaseModel:
    """Build a strictly typed handoff from raw parsed JSON.

    Extracts only the fields that exist in the typed model,
    using defaults for anything missing. This guarantees the
    downstream agent always gets a complete, typed payload.
    """
    model_cls = HANDOFF_MODELS.get(agent)
    if not model_cls:
        return raw_data  # Fallback for unknown agents

    # For CTO: flatten cfo_ready_metrics into top-level fields
    if agent == "CTO":
        cfo_metrics = raw_data.get("cfo_ready_metrics", {})
        if isinstance(cfo_metrics, dict):
            for k, v in cfo_metrics.items():
                if k not in raw_data:
                    raw_data[k] = v

    # Build model, ignoring unknown fields and using defaults
    valid_fields = {}
    for field_name in model_cls.model_fields:
        if field_name in raw_data:
            valid_fields[field_name] = raw_data[field_name]

    try:
        return model_cls(**valid_fields)
    except Exception as e:
        logger.warning(f"Typed handoff build failed for {agent}: {e}")
        return model_cls()  # Return model with all defaults


# ═══════════════════════════════════════════════════════════════════
# §1  WAR ROOM REPORT — Universal Agent Output Contract
# ═══════════════════════════════════════════════════════════════════

class WarRoomReport(BaseModel):
    """Universal output contract for every War Room agent.

    Every agent (CMO, CFO, CTO, CEO, Critic, etc.) must produce a
    WarRoomReport after completing their analysis. This standardizes
    handoffs, enables structured persistence, and powers the Critic's
    cross-agent consensus scoring.
    """

    # Identity
    agent: str = Field(..., description="Agent identifier (CEO, CMO, CFO, CTO, CLO, CRITIC, etc.)")
    phase: str = Field(..., description="Execution phase (market, financials, legal, technical, validation)")
    project_id: str = Field(default="", description="Project this report belongs to")

    # Content
    display_content: str = Field(
        default="",
        description="Rich markdown string representing the conversational debate output for the UI"
    )
    structured_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pydantic validated JSON data extracted via Stealth Parser"
    )
    
    # Typed Handoff Property
    @property
    def handoff_payload_typed(self) -> BaseModel:
        """Returns the strictly typed Phase 5 handoff payload extracted from structured_data."""
        return build_typed_handoff(self.agent, self.structured_data)

    # Legacy attributes kept for compatibility where needed:
    detailed_report: Dict[str, Any] = Field(default_factory=dict)
    summary_report: str = Field(default="")
    data_tables: List[Dict[str, Any]] = Field(default_factory=list)
    handoff_payload: Dict[str, Any] = Field(default_factory=dict)

    # Risk & Recommendation
    risks: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Identified risks: [{severity: HIGH/MEDIUM/LOW, description: str, mitigation: str}]"
    )
    recommendation: str = Field(
        default="PROCEED",
        description="PROCEED / REVISE / REJECT — agent's verdict on moving forward"
    )

    # Critic-specific fields (populated only when agent == 'CRITIC')
    agreement_level: Optional[float] = Field(
        default=None,
        description="Critic's agreement score (1.0–10.0) — only set by Critic"
    )
    objections: List[str] = Field(
        default_factory=list,
        description="Critic's specific objections — only set by Critic"
    )
    verdict: Optional[str] = Field(
        default=None,
        description="APPROVE / REVISE / REJECT — Critic's formal verdict"
    )

    # Metadata
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO-8601 timestamp of report creation"
    )
    iteration: int = Field(
        default=1,
        description="Which consensus iteration this report was produced in"
    )
    raw_response: str = Field(
        default="",
        description="Original unprocessed agent response text (for debugging)"
    )

    def to_handoff_text(self) -> str:
        """Generate a structured text handoff for the next agent in the pipeline."""
        lines = [
            f"=== {self.agent} Report (Phase: {self.phase}) ===",
            f"Recommendation: {self.recommendation}",
            f"Confidence: {self.confidence:.0%}",
            "",
            "--- Executive Summary ---",
            self.summary_report[:500] if self.summary_report else "(No summary provided)",
            "",
        ]

        # Include key data tables
        if self.data_tables:
            lines.append("--- Key Metrics ---")
            for table in self.data_tables[:3]:  # Limit to 3 tables for prompt size
                for k, v in table.items():
                    lines.append(f"  {k}: {v}")
            lines.append("")

        # Include handoff payload
        if self.handoff_payload:
            lines.append("--- Handoff Data ---")
            for k, v in self.handoff_payload.items():
                lines.append(f"  {k}: {v}")
            lines.append("")

        # Include risks
        if self.risks:
            lines.append("--- Risks ---")
            for risk in self.risks[:5]:
                severity = risk.get("severity", "UNKNOWN")
                desc = risk.get("description", "")
                lines.append(f"  [{severity}] {desc}")

        return "\n".join(lines)

    def to_compressed_summary(self) -> str:
        """Ultra-compressed summary for context window management across iterations."""
        risk_str = ", ".join(r.get("description", "")[:40] for r in self.risks[:2]) or "none"
        return (
            f"{self.agent}: {self.recommendation} "
            f"(conf={self.confidence:.0%}). "
            f"Risks: {risk_str}."
        )


# ═══════════════════════════════════════════════════════════════════
# §2  REPORT STORE — Persistence Layer
# ═══════════════════════════════════════════════════════════════════

class ReportStore:
    """Persists WarRoomReports to the Boardroom Exchange file system.

    Storage layout:
        Boardroom_Exchange/reports/{project_id}/{agent}_{phase}_{timestamp}.json
    """

    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or REPORTS_DIR

    def _project_dir(self, project_id: str) -> str:
        d = os.path.join(self.base_dir, project_id)
        os.makedirs(d, exist_ok=True)
        return d

    def save(self, report: WarRoomReport, is_gate: bool = False, gate_score: float = 0.0) -> str:
        """Save a report to disk. Returns the file path.
        
        If is_gate=True, evaluates gate_score to generate the final Vision/Autopsy document.
        """
        project_id = report.project_id or "unassigned"
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        filename = f"{report.agent}_{report.phase}_{ts}.json"
        filepath = os.path.join(self._project_dir(project_id), filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, indent=2, default=str)

        logger.info(f"Report saved: {filepath}")
        
        # ── War Room Verdict Generator (Phase 5) ──
        if is_gate:
            self._generate_verdict_document(project_id, gate_score)
            
        return filepath

    def _generate_verdict_document(self, project_id: str, gate_score: float):
        """Compile all display_content for the project into a final document."""
        reports = self.get_all_for_project(project_id)
        if not reports:
            return
            
        verdict_type = "[APPROVED] Project_Vision.md" if gate_score >= 7.0 else "[FAILED_GATE] Project_Autopsy.md"
        doc_path = os.path.join(self.base_dir, project_id, verdict_type)
        
        content = [f"# {verdict_type.replace('.md', '')}\n", f"**Project:** {project_id} | **Score:** {gate_score}/10\n", "---"]
        for r in reports:
            content.append(f"\n## 🤖 {r.agent} ({r.phase.upper()})")
            if r.metadata:
                cost = r.metadata.get('cost', '$0.00')
                content.append(f"*Execution Cost: {cost}*")
            content.append(f"\n{r.display_content}\n---")
            
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content))
        logger.info(f"War Room Verdict compiled: {doc_path}")

    def get_latest(self, project_id: str, agent: str, phase: str = None,
                   ghost_alert: bool = True) -> Optional[WarRoomReport]:
        """Retrieve the most recent report for a given agent/project.

        Ghost Retrieval: If ghost_alert=True and no report is found,
        a GhostAlert is logged and returned as metadata, signaling
        a pipeline break to the War Room dashboard.
        """
        pdir = self._project_dir(project_id)
        pattern = f"{agent}_"
        if phase:
            pattern += f"{phase}_"

        matching = sorted(
            [f for f in os.listdir(pdir) if f.startswith(pattern) and f.endswith(".json")],
            reverse=True
        )
        if not matching:
            if ghost_alert:
                self._emit_ghost_alert(project_id, agent, phase)
            return None

        filepath = os.path.join(pdir, matching[0])
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return WarRoomReport(**data)
        except Exception as e:
            logger.warning(f"Failed to load report {filepath}: {e}")
            if ghost_alert:
                self._emit_ghost_alert(project_id, agent, phase, error=str(e))
            return None

    def _emit_ghost_alert(self, project_id: str, agent: str,
                          phase: str = None, error: str = None):
        """Ghost Retrieval Alert: Signal a pipeline break.

        Logs the alert and writes a ghost_alerts.json file for the
        Phantom QA Elite dashboard to pick up.
        """
        alert = {
            "type": "GHOST_ALERT",
            "project_id": project_id,
            "missing_agent": agent,
            "missing_phase": phase or "any",
            "error": error,
            "severity": "HIGH",
            "timestamp": datetime.now().isoformat(),
            "message": (
                f"Pipeline Break: No report found for {agent}"
                f"{f' (phase={phase})' if phase else ''} "
                f"in project {project_id}. "
                f"The execution chain may be incomplete."
            ),
        }
        logger.warning(f"GHOST ALERT: {alert['message']}")

        # Persist ghost alerts for Phantom QA dashboard
        alerts_path = os.path.join(self.base_dir, "ghost_alerts.json")
        try:
            existing = []
            if os.path.exists(alerts_path):
                with open(alerts_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing.append(alert)
            # Keep last 100 alerts
            existing = existing[-100:]
            with open(alerts_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist ghost alert: {e}")

    def get_all_for_project(self, project_id: str) -> List[WarRoomReport]:
        """Retrieve all reports for a project, sorted by timestamp."""
        pdir = self._project_dir(project_id)
        reports = []
        for fname in sorted(os.listdir(pdir)):
            if not fname.endswith(".json"):
                continue
            filepath = os.path.join(pdir, fname)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                reports.append(WarRoomReport(**data))
            except Exception as e:
                logger.warning(f"Skipping corrupt report {filepath}: {e}")
        return reports

    def get_latest_iteration_reports(self, project_id: str, iteration: int) -> List[WarRoomReport]:
        """Get all reports from a specific iteration for consensus scoring."""
        all_reports = self.get_all_for_project(project_id)
        return [r for r in all_reports if r.iteration == iteration]

    def clear_project(self, project_id: str):
        """Remove all reports for a project (use before starting fresh pipeline)."""
        pdir = self._project_dir(project_id)
        for fname in os.listdir(pdir):
            if fname.endswith(".json"):
                os.remove(os.path.join(pdir, fname))
        logger.info(f"Cleared all reports for project: {project_id}")


# ═══════════════════════════════════════════════════════════════════
# §3  REPORT PARSER — Convert Raw Agent Output to WarRoomReport
# ═══════════════════════════════════════════════════════════════════

def parse_agent_response(
    raw_text: str,
    agent: str,
    phase: str,
    project_id: str = "",
    iteration: int = 1,
    structured_data: dict = None,
    metadata: dict = None
) -> WarRoomReport:
    """Parse an agent's raw LLM response into a structured WarRoomReport.
    
    In Phase 5, the raw_text becomes display_content for the UI, and
    structured_data is entirely produced by the Flash Stealth Parser.
    """
    structured_data = structured_data or {}
    metadata = metadata or {}
    
    report = WarRoomReport(
        agent=agent,
        phase=phase,
        project_id=project_id,
        display_content=raw_text.strip(),
        structured_data=structured_data,
        metadata=metadata,
        timestamp=datetime.now().isoformat(),
    )
    
    # ── Map Critic Specifics if applicable ──
    if agent in ("CRITIC", "Critic", "The_Critic"):
        report.agreement_level = float(structured_data.get("agreement_level", 5.0))
        report.verdict = structured_data.get("verdict", "REVISE")
        report.objections = structured_data.get("objections", [])
        
    return report


# ═══════════════════════════════════════════════════════════════════
# §4  PIPELINE STEP — Single Unit of the Execution Chain
# ═══════════════════════════════════════════════════════════════════

class PipelineStep(BaseModel):
    """A single step in the War Room execution pipeline."""

    agent_name: str = Field(..., description="Agent to invoke (CMO, CFO, CTO, CEO, CRITIC)")
    phase: str = Field(..., description="Phase label for this step")
    depends_on: List[str] = Field(
        default_factory=list,
        description="Agent names whose reports are required before this step runs"
    )
    parallel_with: List[str] = Field(
        default_factory=list,
        description="Agent names that can run concurrently with this step"
    )
    is_gate: bool = Field(
        default=False,
        description="If True, a failure/REJECT from this step halts the pipeline"
    )
    gate_threshold: Optional[float] = Field(
        default=None,
        description="Minimum score threshold for gate steps (e.g., CTO feasibility >= 4.0)"
    )

    class Config:
        arbitrary_types_allowed = True


# ═══════════════════════════════════════════════════════════════════
# §5  WAR ROOM ORCHESTRATOR — Dynamic Pipeline Engine
# ═══════════════════════════════════════════════════════════════════

# ── Pipeline Templates ──────────────────────────────────────────
PIPELINE_FULL_BUSINESS_PLAN = [
    PipelineStep(
        agent_name="CMO", phase="market",
        depends_on=[],
        is_gate=False
    ),
    PipelineStep(
        agent_name="CEO", phase="validation",
        depends_on=["CMO"],
        is_gate=True, gate_threshold=None  # CEO gate is boolean (approved_for_phase2)
    ),
    PipelineStep(
        agent_name="CTO", phase="technical",
        depends_on=["CMO", "CEO"],
        is_gate=True, gate_threshold=4.0  # Feasibility score >= 4.0
    ),
    PipelineStep(
        agent_name="CFO", phase="financials",
        depends_on=["CMO", "CEO", "CTO"],
        is_gate=False
    ),
    PipelineStep(
        agent_name="CRITIC", phase="adversarial",
        depends_on=["CMO", "CEO", "CTO", "CFO"],
        parallel_with=["PHANTOM_QA"],
        is_gate=True, gate_threshold=8.0  # Critic agreement >= 8/10
    ),
]

PIPELINE_TECHNICAL_ASSESSMENT = [
    PipelineStep(
        agent_name="CTO", phase="technical",
        depends_on=[],
        is_gate=True, gate_threshold=4.0
    ),
    PipelineStep(
        agent_name="CRITIC", phase="adversarial",
        depends_on=["CTO"],
        is_gate=True, gate_threshold=7.0
    ),
]

PIPELINE_MARKET_ANALYSIS = [
    PipelineStep(
        agent_name="CMO", phase="market",
        depends_on=[],
        is_gate=False
    ),
    PipelineStep(
        agent_name="CEO", phase="validation",
        depends_on=["CMO"],
        is_gate=False
    ),
    PipelineStep(
        agent_name="CRITIC", phase="adversarial",
        depends_on=["CMO", "CEO"],
        is_gate=True, gate_threshold=7.0
    ),
]

PIPELINE_LEGAL_REVIEW = [
    PipelineStep(
        agent_name="CLO", phase="legal",
        depends_on=[],
        is_gate=False
    ),
    PipelineStep(
        agent_name="CRITIC", phase="adversarial",
        depends_on=["CLO"],
        is_gate=True, gate_threshold=7.0
    ),
]

PIPELINE_FINANCIAL_DEEP_DIVE = [
    PipelineStep(
        agent_name="CFO", phase="financials",
        depends_on=[],
        is_gate=False
    ),
    PipelineStep(
        agent_name="CRITIC", phase="adversarial",
        depends_on=["CFO"],
        is_gate=True, gate_threshold=7.0
    ),
]

# ── Adversarial Drill Pipeline (Red Team) ────────────────────────
PIPELINE_ADVERSARIAL_DRILL = [
    PipelineStep(
        agent_name="CTO", phase="drill_defense",
        depends_on=[],
        is_gate=True, gate_threshold=8.0
    ),
    PipelineStep(
        agent_name="CMO", phase="drill_defense",
        depends_on=[],
        is_gate=False
    ),
    PipelineStep(
        agent_name="CFO", phase="drill_defense",
        depends_on=["CTO", "CMO"],
        is_gate=False
    ),
    PipelineStep(
        agent_name="CRITIC", phase="drill_verdict",
        depends_on=["CTO", "CMO", "CFO"],
        is_gate=True, gate_threshold=8.0
    ),
]

# Registry of available pipeline templates
PIPELINE_REGISTRY: Dict[str, List[PipelineStep]] = {
    "full_business_plan": PIPELINE_FULL_BUSINESS_PLAN,
    "technical_assessment": PIPELINE_TECHNICAL_ASSESSMENT,
    "market_analysis": PIPELINE_MARKET_ANALYSIS,
    "legal_review": PIPELINE_LEGAL_REVIEW,
    "financial_deep_dive": PIPELINE_FINANCIAL_DEEP_DIVE,
    "adversarial_drill": PIPELINE_ADVERSARIAL_DRILL,
}


class WarRoomOrchestrator:
    """Dynamic pipeline engine for the War Room.

    The Orchestrator:
    1. Analyzes the Commander's intent to select the right pipeline
    2. Composes the execution chain (or allows CEO to override)
    3. Manages state: who has reported, who's pending, who needs revision
    4. Persists all reports via ReportStore
    5. Returns structured results for the broadcast layer (api.py)
    """

    def __init__(self, store: ReportStore = None):
        self.store = store or ReportStore()
        self.active_pipelines: Dict[str, Dict] = {}  # project_id → pipeline state

    def compose_pipeline(self, intent: str, project_type: str = None, triage_override: List[str] = None) -> List[PipelineStep]:
        """Analyze Commander's intent and select the appropriate pipeline.

        Uses the CEO Triage output if provided, falling back to keywords.

        Args:
            intent: The Commander's raw input / directive
            project_type: Optional explicit pipeline name override
            triage_override: CEO generated list of agents (e.g. ["CMO", "CTO", "CRITIC"])

        Returns:
            Ordered list of PipelineSteps
        """
        # ── UPGRADE 6: Dynamic Hierarchy Composition (CEO Triage) ──
        if triage_override and isinstance(triage_override, list) and len(triage_override) > 0:
            logger.info(f"Pipeline overridden by CEO Triage: {triage_override}")
            dynamic_pipeline = []
            
            # Filter valid agents
            valid_registry = ["CEO", "CMO", "CFO", "CTO", "CLO", "CRITIC", "ARCHITECT"]
            valid_agents = [a.upper().strip() for a in triage_override if a.upper().strip() in valid_registry]
            
            # Minimum Squad Rule
            if len(valid_agents) == 1:
                logger.warning("CEO picked single agent. Forcing CRITIC to form a Minimum Squad.")
                valid_agents.append("CRITIC" if valid_agents[0] != "CRITIC" else "CTO")
                
            if not valid_agents:
                logger.warning("CEO Triage returned no valid agents, falling back.")
            else:
                for i, agent in enumerate(valid_agents):
                    is_last = (i == len(valid_agents) - 1)
                    # Next step depends on all previous steps
                    deps = valid_agents[:i]
                    
                    # The final agent is always enforced as a gate
                    step = PipelineStep(
                        agent_name=agent,
                        phase=f"dynamic_step_{i+1}",
                        depends_on=deps,
                        is_gate=is_last,
                        gate_threshold=7.0 if is_last else 0.0
                    )
                    dynamic_pipeline.append(step)
                return dynamic_pipeline

        # Explicit override
        if project_type and project_type in PIPELINE_REGISTRY:
            logger.info(f"Pipeline override: {project_type}")
            return PIPELINE_REGISTRY[project_type]

        intent_lower = intent.lower()

        # ── Keyword-based pipeline selection ──
        # Full business plan triggers (most comprehensive)
        full_plan_keywords = ["start-up", "startup", "business plan", "new venture",
                              "launch", "commercializ", "full analysis"]
        if any(kw in intent_lower for kw in full_plan_keywords):
            logger.info("Pipeline selected: full_business_plan (venture keywords)")
            return PIPELINE_FULL_BUSINESS_PLAN

        # Technical-focused
        tech_keywords = ["architect", "feasib", "technical", "stack",
                         "infrastructure", "deploy", "build"]
        if any(kw in intent_lower for kw in tech_keywords) and not any(
            kw in intent_lower for kw in ["market", "revenue", "customer", "brand"]
        ):
            logger.info("Pipeline selected: technical_assessment (tech keywords)")
            return PIPELINE_TECHNICAL_ASSESSMENT

        # Legal-focused (check BEFORE market — "trademark" + "brand" should route to legal)
        legal_keywords = ["legal", "compliance", "patent", "trademark", "ip ",
                          "intellectual property", "regulation", "agreement", "license"]
        if any(kw in intent_lower for kw in legal_keywords):
            logger.info("Pipeline selected: legal_review (legal keywords)")
            return PIPELINE_LEGAL_REVIEW

        # Market-focused
        market_keywords = ["competitor", "market", "customer", "audience",
                           "brand", "positioning", "demographic"]
        if any(kw in intent_lower for kw in market_keywords) and not any(
            kw in intent_lower for kw in ["financial", "budget", "roi", "cost"]
        ):
            logger.info("Pipeline selected: market_analysis (market keywords)")
            return PIPELINE_MARKET_ANALYSIS

        # Finance-focused (without broader context)
        finance_keywords = ["financ", "budget", "roi", "cash flow", "burn rate",
                            "breakeven", "investment", "funding"]
        if any(kw in intent_lower for kw in finance_keywords) and not any(
            kw in intent_lower for kw in ["market", "customer", "technical"]
        ):
            logger.info("Pipeline selected: financial_deep_dive (finance keywords)")
            return PIPELINE_FINANCIAL_DEEP_DIVE

        # Default: full business plan (covers everything)
        logger.info("Pipeline selected: full_business_plan (default)")
        return PIPELINE_FULL_BUSINESS_PLAN

    def get_pipeline_summary(self, pipeline: List[PipelineStep]) -> str:
        """Human-readable summary of a pipeline for UI display."""
        steps = " > ".join(step.agent_name for step in pipeline)
        gates = [s.agent_name for s in pipeline if s.is_gate]
        return f"Chain: {steps} | Gates: {', '.join(gates) if gates else 'none'}"

    def build_handoff_context(
        self,
        step: PipelineStep,
        reports: Dict[str, WarRoomReport],
        commander_intent: str,
        iteration: int = 1,
        market_pulse: Dict[str, Any] = None,
        chaos_scenario: ChaosScenario = None,
        strategy_mode: StrategyMode = None,
        wisdom_vault=None,
        project_type: str = "universal",
    ) -> str:
        """Build the prompt/context for an agent based on upstream reports.

        This replaces the hardcoded handoff string construction in api.py
        with a dynamic, report-driven approach.

        Args:
            step: The pipeline step to build context for
            reports: Dict of {agent_name: WarRoomReport} from completed steps
            commander_intent: The original Commander input
            iteration: Current consensus iteration number
            market_pulse: Strategic sentiment data (if available)
            chaos_scenario: If set, injects a Red Team crisis into the prompt
            strategy_mode: Commander's strategic philosophy for this session
            wisdom_vault: If set, injects relevant corporate standards
            project_type: Project type for standard applicability filtering

        Returns:
            Structured prompt string for the agent
        """
        sections = []

        # Header
        sections.append(
            f"=== WAR ROOM BRIEFING \u2014 {step.agent_name} ({step.phase.upper()}) ===\n"
            f"Iteration: {iteration}\n"
            f"Commander's Directive: {commander_intent}\n"
        )

        # \u2500\u2500 Strategy Mode (Commander's Intent) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        if strategy_mode:
            strategy_block = strategy_mode.to_prompt_block()
            if strategy_block:
                sections.append(strategy_block)

        # \u2500\u2500 Chaos Scenario (Red Team Drill) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        if chaos_scenario:
            constraints_str = json.dumps(chaos_scenario.injected_constraints, indent=2)
            sections.append(
                f"=== \u26a0\ufe0f RED TEAM DRILL (Severity: {chaos_scenario.severity:.0%}) ===\n"
                f"CRISIS: {chaos_scenario.description}\n"
                f"Constraints:\n{constraints_str}\n"
                f"YOU MUST demonstrate your strategy SURVIVES this scenario.\n"
                f"Adjust your numbers, timeline, and risk assessment accordingly.\n"
                f"If your original plan cannot survive, propose a PIVOT."
            )

        # \u2500\u2500 Corporate Standards (Wisdom Vault) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        if wisdom_vault:
            try:
                standards_block = wisdom_vault.inject_corporate_standards(
                    step.agent_name, project_type=project_type,
                )
                if standards_block:
                    sections.append(standards_block)
            except Exception as e:
                logger.warning(f"Wisdom Vault injection failed: {e}")


        # Market pulse (if available)
        if market_pulse:
            verdict = market_pulse.get("verdict", "NEUTRAL")
            velocity = market_pulse.get("trend_velocity", 5.0)
            sentiment = market_pulse.get("public_sentiment_score", 0.0)
            sections.append(
                f"[MARKET PULSE] Verdict: {verdict} | Velocity: {velocity} | Sentiment: {sentiment}"
            )
            if verdict == "BEARISH":
                sections.append(
                    "⚠️ WARNING: Market is BEARISH. You MUST present a Pivot Option."
                )

        # Upstream reports (dependencies)
        for dep_agent in step.depends_on:
            if dep_agent in reports:
                dep_report = reports[dep_agent]
                sections.append(dep_report.to_handoff_text())

        # Iteration context (for iterations > 1)
        if iteration > 1 and "CRITIC" in reports:
            critic = reports["CRITIC"]
            sections.append(
                f"\n=== CRITIC FEEDBACK (Iteration {iteration - 1}) ===\n"
                f"Score: {critic.agreement_level}/10 | Verdict: {critic.verdict}\n"
                f"Objections: {'; '.join(critic.objections) if critic.objections else 'none'}\n"
                f"YOU MUST address these objections in your revised analysis."
            )

        # Agent-specific instructions
        agent_instructions = {
            "CMO": (
                "Produce your Market Positioning & Revenue Strategy Report.\n"
                "Your output MUST include JSON with these fields:\n"
                "marketing_cost, projected_revenue, demographic_reach, "
                "cost_per_acquisition, market_strategy, recommendation, "
                "revenue_timeline_months, key_risks, confidence (0-1)."
            ),
            "CEO": (
                "Validate the upstream reports against the Commander's strategic intent.\n"
                "Check for scope creep, misalignment, and strategic coherence.\n"
                "Your output MUST include JSON with:\n"
                "approved_for_phase2, growth_target_alignment, growth_target_annual, "
                "strategic_direction, recommendation, confidence (0-1)."
            ),
            "CTO": (
                "Assess Technical Feasibility using the Universal Stack Evaluator.\n"
                "Your output MUST include JSON with:\n"
                "technical_feasibility_score (1-10), project_type, tech_stack (array), "
                "implementation_timeline_weeks, v3_compliance, pre_deploy_gate_status, "
                "cfo_ready_metrics: {infrastructure_cost_estimate, development_buffer_weeks, "
                "tech_debt_risk_premium_pct}, recommendation, confidence (0-1)."
            ),
            "CFO": (
                "Build the financial model using EXACT numbers from CMO and CTO.\n"
                "Do NOT invent your own numbers — use the handoff data above.\n"
                "Your output MUST include JSON with:\n"
                "roi_percentage, roas, breakeven_month, burn_rate, "
                "profitability_timeline, business_plan_summary, "
                "recommendation, confidence (0-1)."
            ),
            "CLO": (
                "Conduct legal & compliance review.\n"
                "Your output MUST include JSON with:\n"
                "compliance_status, ip_clearance, regulatory_risks, "
                "required_agreements, recommendation, confidence (0-1)."
            ),
            "CRITIC": (
                "EVALUATE THE COMPLETED REPORTS. You are the Adversary.\n"
                "Challenge: (1) Are the numbers realistic? (2) Is the ROI achievable? "
                "(3) Is the timeline credible? (4) What are they not telling you?\n"
                "Your output MUST include JSON with:\n"
                "agreement_level (1-10 float), verdict (APPROVE/REVISE/REJECT), "
                "objections (array of strings), cost_challenge, revenue_challenge, "
                "evidence_demanded, confidence (0-1)."
            ),
        }

        if step.agent_name in agent_instructions:
            sections.append(f"\n--- Your Mission ---\n{agent_instructions[step.agent_name]}")

        return "\n\n".join(sections)

    def check_gate(
        self,
        step: PipelineStep,
        report: WarRoomReport,
        strategy_mode: StrategyMode = None,
    ) -> Dict[str, Any]:
        """Evaluate whether a gate step passes or blocks the pipeline.

        Args:
            step: The gate step to evaluate
            report: The agent's report
            strategy_mode: If set, applies threshold modifier from Commander's Intent

        Returns:
            {passed: bool, reason: str, score: float, effective_threshold: float}
        """
        if not step.is_gate:
            return {"passed": True, "reason": "Not a gate step", "score": None, "effective_threshold": None}

        # Calculate effective threshold with strategy modifier
        modifier = strategy_mode.gate_threshold_modifier if strategy_mode else 0.0

        # CEO gate: boolean approval (no threshold modifier applies)
        if step.agent_name == "CEO":
            approved = report.handoff_payload.get("approved_for_phase2", True)
            alignment = report.handoff_payload.get("growth_target_alignment", "UNKNOWN")
            return {
                "passed": bool(approved),
                "reason": f"CEO alignment: {alignment}" if approved else f"CEO flags MISALIGNMENT: {alignment}",
                "score": 1.0 if approved else 0.0,
                "effective_threshold": None,
            }

        # CTO gate: feasibility score threshold (strategy-modified)
        if step.agent_name == "CTO" and step.gate_threshold:
            effective = max(1.0, step.gate_threshold + modifier)
            score = float(report.handoff_payload.get("technical_feasibility_score", 5.0))
            passed = score >= effective
            symbol = ">=" if passed else "<"
            return {
                "passed": passed,
                "reason": f"CTO Feasibility: {score}/10 ({symbol} {effective})",
                "score": score,
                "effective_threshold": effective,
            }

        # CRITIC gate: agreement level threshold (strategy-modified)
        if step.agent_name == "CRITIC" and step.gate_threshold:
            effective = max(1.0, step.gate_threshold + modifier)
            score = float(report.agreement_level or 5.0)
            passed = score >= effective
            symbol = ">=" if passed else "<"
            return {
                "passed": passed,
                "reason": f"Critic Agreement: {score}/10 ({symbol} {effective})",
                "score": score,
                "effective_threshold": effective,
            }

        # Generic gate: check recommendation
        passed = report.recommendation not in ("REJECT",)
        return {
            "passed": passed,
            "reason": f"{step.agent_name} recommendation: {report.recommendation}",
            "score": report.confidence,
            "effective_threshold": None,
        }


    def start_session(
        self,
        project_id: str,
        pipeline: List[PipelineStep],
        intent: str,
        strategy_mode: StrategyMode = None,
        stress_test: bool = False,
    ) -> Dict:
        """Initialize a new War Room session for a project.

        Args:
            project_id: Unique project identifier
            pipeline: Ordered pipeline steps
            intent: Commander's original directive
            strategy_mode: Commander's strategic philosophy
            stress_test: If True, run adversarial drill after pipeline

        Returns:
            Session metadata for tracking.
        """
        session = {
            "project_id": project_id,
            "pipeline": pipeline,
            "intent": intent,
            "reports": {},
            "iteration": 1,
            "max_iterations": 5,
            "status": "active",
            "started_at": datetime.now().isoformat(),
            "consensus_reached": False,
            "strategy_mode": strategy_mode or STRATEGY_PRESETS["balanced"],
            "stress_test": stress_test,
            "drill_results": None,
        }
        self.active_pipelines[project_id] = session
        mode_label = session["strategy_mode"].label if hasattr(session["strategy_mode"], "label") else "Balanced"
        logger.info(
            f"War Room session started: {project_id} | "
            f"Pipeline: {self.get_pipeline_summary(pipeline)} | "
            f"Strategy: {mode_label} | Stress Test: {stress_test}"
        )
        return session

    def run_adversarial_drill(
        self,
        session: Dict,
        scenario: ChaosScenario = None,
        max_retries: int = 3,
        agent_call_fn: Callable = None,
    ) -> Dict[str, Any]:
        """Execute a Red Team adversarial drill on an active session.

        Injects a chaos scenario and requires agents to defend their strategy.
        Auto-revises up to max_retries before escalating to Commander.

        Args:
            session: The active War Room session (must have reports already)
            scenario: Specific chaos scenario (random from library if None)
            max_retries: Max auto-revisions before escalation
            agent_call_fn: Callable(agent_name, prompt) -> str for live calls
                          If None, returns dry-run result with drill context

        Returns:
            {
                "status": "passed" | "failed" | "escalated" | "dry_run",
                "scenario": ChaosScenario,
                "iterations": int,
                "final_score": float,
                "drill_reports": Dict[str, WarRoomReport],
                "escalation_reason": str or None
            }
        """
        import random as _rand

        # Select scenario
        if scenario is None:
            scenario = _rand.choice(CHAOS_LIBRARY)

        logger.info(
            f"[RED TEAM] Drill started: {scenario.scenario_id} "
            f"(severity: {scenario.severity:.0%}) on project {session['project_id']}"
        )

        drill_reports: Dict[str, WarRoomReport] = {}
        drill_pipeline = PIPELINE_ADVERSARIAL_DRILL
        strategy = session.get("strategy_mode")

        # Dry-run mode (no live agent calls)
        if agent_call_fn is None:
            # Build the drill context for each agent to verify injection
            contexts = {}
            for step in drill_pipeline:
                ctx = self.build_handoff_context(
                    step, session["reports"], session["intent"],
                    iteration=1, chaos_scenario=scenario, strategy_mode=strategy,
                )
                contexts[step.agent_name] = ctx
            return {
                "status": "dry_run",
                "scenario": scenario,
                "iterations": 0,
                "final_score": 0.0,
                "drill_reports": {},
                "drill_contexts": contexts,
                "escalation_reason": None,
            }

        # Live drill with agent calls
        for iteration in range(1, max_retries + 1):
            logger.info(f"[RED TEAM] Iteration {iteration}/{max_retries}")

            for step in drill_pipeline:
                # Build chaos-injected context
                ctx = self.build_handoff_context(
                    step, {**session["reports"], **drill_reports},
                    session["intent"], iteration=iteration,
                    chaos_scenario=scenario, strategy_mode=strategy,
                )
                # Call agent
                raw_response = agent_call_fn(step.agent_name, ctx)
                report = parse_agent_response(
                    raw_response, step.agent_name, step.phase,
                    session["project_id"], iteration,
                )
                drill_reports[step.agent_name] = report
                self.store.save(report)

            # Check CRITIC verdict
            critic_report = drill_reports.get("CRITIC")
            if critic_report:
                score = critic_report.agreement_level or 0.0
                if score >= 8.0:
                    logger.info(f"[RED TEAM] PASSED at iteration {iteration} (score: {score}/10)")
                    session["drill_results"] = {
                        "status": "passed",
                        "scenario": scenario.model_dump(),
                        "iterations": iteration,
                        "final_score": score,
                    }
                    return {
                        "status": "passed",
                        "scenario": scenario,
                        "iterations": iteration,
                        "final_score": score,
                        "drill_reports": drill_reports,
                        "escalation_reason": None,
                    }

        # Exhausted retries — escalate to Commander
        final_score = 0.0
        if "CRITIC" in drill_reports:
            final_score = drill_reports["CRITIC"].agreement_level or 0.0

        escalation_reason = (
            f"Red Team drill '{scenario.scenario_id}' failed after {max_retries} iterations. "
            f"Final CRITIC score: {final_score}/10 (required: 8.0). "
            f"Crisis: {scenario.description}"
        )
        logger.warning(f"[RED TEAM] ESCALATING: {escalation_reason}")

        session["drill_results"] = {
            "status": "escalated",
            "scenario": scenario.model_dump(),
            "iterations": max_retries,
            "final_score": final_score,
            "escalation_reason": escalation_reason,
        }
        return {
            "status": "escalated",
            "scenario": scenario,
            "iterations": max_retries,
            "final_score": final_score,
            "drill_reports": drill_reports,
            "escalation_reason": escalation_reason,
        }

    def get_session(self, project_id: str) -> Optional[Dict]:
        """Get the active session for a project."""
        return self.active_pipelines.get(project_id)

    def end_session(self, project_id: str, status: str = "completed"):
        """Close a War Room session."""
        if project_id in self.active_pipelines:
            self.active_pipelines[project_id]["status"] = status
            self.active_pipelines[project_id]["ended_at"] = datetime.now().isoformat()
            logger.info(f"War Room session ended: {project_id} ({status})")


# ═══════════════════════════════════════════════════════════════════
# §6  MODULE-LEVEL SINGLETONS
# ═══════════════════════════════════════════════════════════════════

_report_store = None
_orchestrator = None


def get_report_store() -> ReportStore:
    """Get or create the global ReportStore singleton."""
    global _report_store
    if _report_store is None:
        _report_store = ReportStore()
    return _report_store


def get_orchestrator() -> WarRoomOrchestrator:
    """Get or create the global WarRoomOrchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WarRoomOrchestrator(store=get_report_store())
    return _orchestrator
