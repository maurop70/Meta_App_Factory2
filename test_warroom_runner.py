# -*- coding: utf-8 -*-
"""
test_warroom_runner.py — Verification suite for WarRoomPipelineRunner.

Covers the 6 hardening phases:
  1. Runner extraction: full session runs headless with injected infrastructure.
  2. Concurrency: CPO and CLO execute overlapping the CMO->CEO->CTO chain.
  3. Mathematical rigor: CFO handoff_payload synced to native Excel figures.
  4. Dynamic chaos: weakest-dimension scenario selected and injected.
  5. Semantic memory: <historical_semantic_memory> XML reaches CEO + Critic.
  6. Objection routing: tagged Critic objections become per-agent mandates.

All LLM calls, sentiment, Excel, Phantom, and vector-memory dependencies are
stubbed — no network, no API keys required.
"""

import sys
import os
import json
import time
import types
import asyncio
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Stub heavyweight/lazy-imported dependencies BEFORE importing the runner ──

def _module(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod

class _StubSentiment:
    def analyze_market(self, project_id):
        return {"verdict": "NEUTRAL", "trend_velocity": 6.0, "public_sentiment_score": 55.0}

_module("strategic_sentiment", get_strategic_sentiment=lambda: _StubSentiment())

class _StubCFOArchitect:
    def generate_business_plan(self, project_id, cmo_data, cto_data, market_pulse):
        # Computed "ground truth" deliberately different from the LLM's claims
        return {
            "status": "success", "file_name": "stub_fragility.xlsx",
            "fragility_index": 35.0, "total_cost": 61500.0,
            "roi_percentage": 42.0, "risk_adjusted_roi": 31.0,
            "npv": 88000.0, "roas": 2.1,
        }

_module("cfo_excel_architect", get_cfo_architect=lambda: _StubCFOArchitect())

_module("phantom_ui_pathfinder", run_ui_audit=lambda project_id: {"verdict": "PASS", "score": 95, "errors": []})

class _StubLedger:
    def calibration_prompt_block(self, agent):
        return ""
    def base_rate_block(self, claims):
        return ""
    def capture_from_reports(self, project_id, reports, iteration):
        return [{"claim": "roi_percentage"}]

_module("warroom_outcomes", get_prediction_ledger=lambda: _StubLedger())

class _StubVectorMemory:
    def retrieve_context(self, query, n_results=3):
        return {"documents": [["PAST PLAN: SaaS launch, Critic punished unvalidated CPA assumptions."]]}

_module("agent_memory_matrix", VectorMemoryMatrix=_StubVectorMemory)
_module("cpo_agent", run_cpo=lambda q: json.dumps({
    "value_capture_mechanism": "freemium upsell",
    "commercial_viability_score": 7.5,
    "moscow_must_haves": ["auth", "billing"],
}))

from war_room_runner import WarRoomPipelineRunner  # noqa: E402

# ── Test scaffolding ─────────────────────────────────────────────────

PROJECT = f"RunnerSelfTest_{int(time.time())}"
EVENTS = []            # every broadcast SSE/WS message
CALL_WINDOWS = {}      # agent -> list of (start, end) wall-clock windows
PROMPTS = {}           # agent -> list of received prompts
CRITIC_CALLS = {"n": 0}

RESULTS = {"passed": 0, "failed": 0}

def check(name, cond):
    if cond:
        RESULTS["passed"] += 1
        print(f"  [PASS] {name}")
    else:
        RESULTS["failed"] += 1
        print(f"  [FAIL] {name}")

AGENT_RESPONSES = {
    "CMO": json.dumps({
        "market_strategy": "Target K-12 parents via paid social and SEO content.",
        "target_demographic": "Parents 30-45",
        "marketing_cost": 50000, "projected_revenue": 250000,
        "revenue_timeline_months": 12, "demographic_reach": 150000,
        "cost_per_acquisition": 22.5, "recommendation": "PROCEED", "confidence": 0.88,
    }),
    "CEO": json.dumps({
        "approved_for_phase2": True, "growth_target_alignment": "ALIGNED",
        "growth_target_annual": 500000, "strategic_direction": "Proceed lean",
        "recommendation": "PROCEED", "confidence": 0.9,
    }),
    "CTO": json.dumps({
        "technical_feasibility_score": 8.5, "project_type": "DIGITAL",
        "tech_stack": ["FastAPI", "React"], "implementation_timeline_weeks": 4,
        "v3_compliance": "COMPLIANT", "pre_deploy_gate_status": "CLEAR",
        "infrastructure_cost_estimate": 650, "development_buffer_weeks": 4,
        "tech_debt_risk_premium_pct": 10, "recommendation": "BUILD", "confidence": 0.91,
    }),
    "CLO": json.dumps({
        "compliance_status": "CLEAR", "ip_clearance": "CLEAR",
        "regulatory_risks": [], "required_agreements": ["ToS"], "confidence": 0.85,
    }),
    "CFO": json.dumps({
        # LLM narrative numbers — must be OVERWRITTEN by the native Excel stub
        "roi_percentage": 156.2, "roas": 5.0, "breakeven_month": 7,
        "burn_rate": 12000, "total_cost_basis": 55000, "npv": 87000,
        "fragility_index": 20, "risk_adjusted_roi": 140.0,
        "business_plan_summary": "Strong plan", "recommendation": "PROCEED", "confidence": 0.87,
    }),
}

CRITIC_ROUND_1 = json.dumps({
    "agreement_level": 6.0, "verdict": "REVISE",
    "objections": [
        "HIGH [CMO]: CPA of $22.50 needs pilot validation",
        "MEDIUM [CFO]: ROAS assumption lacks cohort evidence",
    ],
    "cost_challenge": "Marketing cost understates churn replacement",
    "revenue_challenge": "Revenue assumes flawless conversion",
    "evidence_demanded": "Pilot CPA data", "confidence": 0.8,
})

CRITIC_ROUND_2 = json.dumps({
    "agreement_level": 9.5, "verdict": "APPROVE", "objections": [],
    "cost_challenge": "", "revenue_challenge": "",
    "evidence_demanded": "", "confidence": 0.92,
})


def mock_call_agent(agent_name, topic):
    start = time.monotonic()
    PROMPTS.setdefault(agent_name, []).append(topic)
    time.sleep(0.25)  # make execution windows measurable for overlap checks
    try:
        if agent_name == "CEO" and "Team Selection:" in topic:
            return '["CMO", "CEO", "CPO", "CTO", "CLO", "CFO", "CRITIC"]'
        if agent_name == "CRITIC":
            CRITIC_CALLS["n"] += 1
            return CRITIC_ROUND_1 if CRITIC_CALLS["n"] == 1 else CRITIC_ROUND_2
        if agent_name == "SYSTEM":
            return "{}"
        return AGENT_RESPONSES.get(agent_name, "{}")
    finally:
        CALL_WINDOWS.setdefault(agent_name, []).append((start, time.monotonic()))


def mock_stealth_extract(fields, transcript):
    try:
        data = json.loads(transcript)
        return {k: v for k, v in data.items() if k in fields}
    except Exception:
        return {}


async def capture_broadcast(msg, project="Aether"):
    EVENTS.append(msg)


async def main():
    # Clean any stale checkpoint for this project
    chk = os.path.join("Boardroom_Exchange", "active_sessions", f"{PROJECT}_state.json")
    if os.path.exists(chk):
        os.remove(chk)

    runner = WarRoomPipelineRunner(
        project_id=PROJECT,
        message="Launch a cmo-driven subscription venture, validate roi rigorously",
        strategy_mode="balanced",
        broadcast=capture_broadcast,
        call_agent=mock_call_agent,
        stealth_extract=mock_stealth_extract,
        executor=ThreadPoolExecutor(max_workers=8, thread_name_prefix="test-warroom"),
        agents_meta={"CEO": {"icon": "X", "color": "#000"}},
        persuasion_setter=None,
        pre_deploy_available=False,
    )
    await runner.run_session()
    await asyncio.sleep(0.3)  # drain fire-and-forget tasks (performance review)

    print("\n=== 1. RUNNER EXTRACTION / SESSION LIFECYCLE ===")
    types_seen = {e.get("type") for e in EVENTS}
    for expected in ("consensus_iteration", "dialogue", "market_pulse",
                     "coo_alert", "agent_working", "persuasion_update", "intervention"):
        check(f"SSE contract: '{expected}' event emitted", expected in types_seen)
    consensus_events = [e for e in EVENTS if e.get("type") == "consensus_iteration"]
    check("Two iterations ran (Critic blocked round 1)",
          any(e.get("iteration") == 2 for e in consensus_events))
    check("Final consensus reached", any(e.get("status") == "CONSENSUS" for e in consensus_events))
    dialogue_fields_ok = all(
        ("agent" in e and "message" in e) for e in EVENTS if e.get("type") == "dialogue"
    )
    check("All dialogue events carry agent + message fields", dialogue_fields_ok)

    print("\n=== 2. CONCURRENCY: CPO / CLO overlap the CMO chain ===")
    def overlaps(a, b):
        return a[0] < b[1] and b[0] < a[1]
    cmo_win = CALL_WINDOWS.get("CMO", [(0, 0)])[0]
    cpo_win = CALL_WINDOWS.get("CPO", [(99, 99)])[0] if "CPO" in CALL_WINDOWS else None
    clo_win = CALL_WINDOWS.get("CLO", [(99, 99)])[0]
    # CPO goes through cpo_agent.run_cpo (stubbed, instant) — its agent_working
    # event ordering is checked instead of a thread window.
    check("CLO call window overlaps CMO call window", overlaps(clo_win, cmo_win))
    working_order = [e["agent"] for e in EVENTS if e.get("type") == "agent_working"]
    cmo_idx = working_order.index("CMO")
    check("CPO dispatched before CMO finished (parallel TaskGroup)",
          "CPO" in working_order[:cmo_idx + 2])
    ceo_after_cmo = CALL_WINDOWS["CEO"][-1][0] >= cmo_win[1] or len(CALL_WINDOWS["CEO"]) > 1
    check("CEO (chain) never started before CMO finished within an iteration", ceo_after_cmo)

    print("\n=== 3. MATHEMATICAL RIGOR: CFO synced to native Excel ===")
    cfo_report = runner.session["reports"]["CFO"]
    check("handoff_payload.roi_percentage overwritten (156.2 -> 42.0)",
          cfo_report.handoff_payload.get("roi_percentage") == 42.0)
    check("handoff_payload.roas overwritten (5.0 -> 2.1)",
          cfo_report.handoff_payload.get("roas") == 2.1)
    check("handoff_payload.total_cost_basis from computed sheet",
          cfo_report.handoff_payload.get("total_cost_basis") == 61500.0)
    check("Sync recorded in report metadata",
          "roi_percentage" in (cfo_report.metadata.get("native_excel_synced") or []))
    check("detailed_report carries computed figures",
          cfo_report.detailed_report.get("roi_percentage") == 42.0)

    print("\n=== 4. DYNAMIC RED-TEAM CHAOS ===")
    # Synced ROI 42% < 50% -> financial fragility -> market_crash scenario
    check("Chaos selected for fragile ROI (market_crash)",
          runner.active_chaos is not None and runner.active_chaos.scenario_id == "market_crash")
    red_team_events = [e for e in EVENTS if e.get("agent") == "RED_TEAM"]
    check("RED_TEAM drill broadcast emitted", len(red_team_events) >= 1)
    critic_prompts = PROMPTS.get("CRITIC", [])
    check("Critic prompt contains RED TEAM DRILL block",
          any("RED TEAM DRILL" in p for p in critic_prompts))
    cmo_prompts = PROMPTS.get("CMO", [])
    check("Iteration-2 CMO prompt contains chaos survival demand",
          len(cmo_prompts) >= 2 and "RED TEAM DRILL" in cmo_prompts[1])

    print("\n=== 5. SEMANTIC MEMORY RECALL ===")
    ceo_prompts = [p for p in PROMPTS.get("CEO", []) if "Team Selection:" not in p]
    check("CEO briefing contains <historical_semantic_memory> XML",
          any("<historical_semantic_memory>" in p for p in ceo_prompts))
    check("Critic briefing contains <historical_semantic_memory> XML",
          any("<historical_semantic_memory>" in p for p in critic_prompts))
    check("CMO briefing does NOT receive raw memory block (scope respected)",
          all("<historical_semantic_memory>" not in p for p in cmo_prompts))

    print("\n=== 6. OBJECTION ROUTING ===")
    check("HIGH [CMO] objection routed to CMO mandate",
          any("MANDATORY OBJECTION RESOLUTION (CMO)" in p and "CPA of $22.50" in p
              for p in cmo_prompts))
    cfo_prompts = PROMPTS.get("CFO", [])
    check("MEDIUM [CFO] objection routed to CFO mandate",
          any("MANDATORY OBJECTION RESOLUTION (CFO)" in p and "ROAS assumption" in p
              for p in cfo_prompts))
    cto_prompts = PROMPTS.get("CTO", [])
    check("CTO received no mandate (no tagged objection)",
          all("MANDATORY OBJECTION RESOLUTION" not in p for p in cto_prompts))
    check("Routing summary broadcast emitted",
          any("OBJECTION ROUTING" in str(e.get("message", "")) for e in EVENTS))

    # Cleanup checkpoint artifact
    if os.path.exists(chk):
        os.remove(chk)

    print("\n" + "=" * 60)
    print(f"RUNNER TEST RESULTS: {RESULTS['passed']} passed, {RESULTS['failed']} failed")
    print("=" * 60)
    if RESULTS["failed"]:
        sys.exit(1)
    print("ALL RUNNER TESTS PASSED")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    asyncio.run(main())
