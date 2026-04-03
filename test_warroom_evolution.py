"""
test_warroom_evolution.py — Tests for Phase 1 (Red Team) + Phase 2 (Commander's Intent)
═══════════════════════════════════════════════════════════════════════════════════════════
Covers:
  Phase 1: ChaosScenario, CHAOS_LIBRARY, PIPELINE_ADVERSARIAL_DRILL, run_adversarial_drill
  Phase 2: StrategyMode, STRATEGY_PRESETS, strategy-aware gates, prompt injection
"""

import sys
import os
import json
import tempfile
import shutil

# Ensure Meta_App_Factory is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from warroom_protocol import (
    ChaosScenario, CHAOS_LIBRARY,
    StrategyMode, STRATEGY_PRESETS, get_strategy_mode,
    WarRoomReport, PipelineStep,
    PIPELINE_ADVERSARIAL_DRILL, PIPELINE_REGISTRY,
    WarRoomOrchestrator, ReportStore,
    parse_agent_response,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

_passed = 0
_failed = 0

def _assert(condition, name):
    global _passed, _failed
    if condition:
        print(f"  [PASS] {name}")
        _passed += 1
    else:
        print(f"  [FAIL] {name}")
        _failed += 1


def _make_report(agent, **kwargs):
    """Quick report factory."""
    defaults = {
        "agent": agent, "phase": "test", "project_id": "TestProject",
        "iteration": 1, "raw_response": "test", "timestamp": "2026-01-01T00:00:00",
        "summary_report": f"{agent} summary", "confidence": 0.8,
        "recommendation": "PROCEED", "handoff_payload": {},
    }
    defaults.update(kwargs)
    return WarRoomReport(**defaults)


# ═══════════════════════════════════════════════════════════════
# Phase 1: Red Team / Adversarial Drills
# ═══════════════════════════════════════════════════════════════

print("\n=== PHASE 1: CHAOS SCENARIO TESTS ===")

# 1.1 ChaosScenario model
scenario = ChaosScenario(
    scenario_id="test_crash", type="market_crash", severity=0.8,
    description="Test crisis", injected_constraints={"tam_reduction_pct": 50}
)
_assert(scenario.scenario_id == "test_crash", "ChaosScenario creation")
_assert(scenario.severity == 0.8, "ChaosScenario severity")
_assert(scenario.injected_constraints["tam_reduction_pct"] == 50, "ChaosScenario constraints")

# 1.2 CHAOS_LIBRARY
_assert(len(CHAOS_LIBRARY) == 4, f"CHAOS_LIBRARY has 4 scenarios (got {len(CHAOS_LIBRARY)})")
_assert(CHAOS_LIBRARY[0].scenario_id == "market_crash", "Library[0] is market_crash")
_assert(CHAOS_LIBRARY[1].scenario_id == "api_price_shock", "Library[1] is api_price_shock")
_assert(CHAOS_LIBRARY[2].scenario_id == "competitor_blitz", "Library[2] is competitor_blitz")
_assert(CHAOS_LIBRARY[3].scenario_id == "regulation_shock", "Library[3] is regulation_shock")
_assert(all(0.0 <= s.severity <= 1.0 for s in CHAOS_LIBRARY), "All severities in range")

# 1.3 PIPELINE_ADVERSARIAL_DRILL
_assert(len(PIPELINE_ADVERSARIAL_DRILL) == 4, "Drill pipeline has 4 steps")
_assert(PIPELINE_ADVERSARIAL_DRILL[0].agent_name == "CTO", "Drill starts with CTO")
_assert(PIPELINE_ADVERSARIAL_DRILL[0].phase == "drill_defense", "CTO phase is drill_defense")
_assert(PIPELINE_ADVERSARIAL_DRILL[0].is_gate is True, "CTO is gate in drill")
_assert(PIPELINE_ADVERSARIAL_DRILL[0].gate_threshold == 8.0, "CTO gate threshold is 8.0")
_assert(PIPELINE_ADVERSARIAL_DRILL[3].agent_name == "CRITIC", "Drill ends with CRITIC")
_assert(PIPELINE_ADVERSARIAL_DRILL[3].gate_threshold == 8.0, "CRITIC gate threshold is 8.0")
_assert("adversarial_drill" in PIPELINE_REGISTRY, "Drill in PIPELINE_REGISTRY")

# 1.4 Chaos injection in build_handoff_context
print("\n=== PHASE 1: CHAOS INJECTION TESTS ===")
tmp = tempfile.mkdtemp()
try:
    store = ReportStore(base_dir=tmp)
    orch = WarRoomOrchestrator(store=store)
    step = PipelineStep(agent_name="CTO", phase="drill_defense", depends_on=[])
    chaos = CHAOS_LIBRARY[0]  # market_crash

    ctx_no_chaos = orch.build_handoff_context(step, {}, "Build a SaaS app")
    _assert("RED TEAM DRILL" not in ctx_no_chaos, "No chaos = no drill banner")

    ctx_with_chaos = orch.build_handoff_context(step, {}, "Build a SaaS app", chaos_scenario=chaos)
    _assert("RED TEAM DRILL" in ctx_with_chaos, "Chaos injects RED TEAM DRILL banner")
    _assert("market_crash" in ctx_with_chaos.lower() or "TAM drops 60%" in ctx_with_chaos, "Crisis description injected")
    _assert("tam_reduction_pct" in ctx_with_chaos, "Constraints injected")
    _assert("SURVIVES" in ctx_with_chaos, "Survival mandate in prompt")
    _assert("PIVOT" in ctx_with_chaos, "Pivot instruction in prompt")

    # 1.5 Dry-run adversarial drill
    print("\n=== PHASE 1: DRY-RUN DRILL TESTS ===")
    session = orch.start_session("DrillTest", PIPELINE_ADVERSARIAL_DRILL, "Build an AI logistics tracker")
    session["reports"] = {
        "CMO": _make_report("CMO"),
        "CTO": _make_report("CTO", handoff_payload={"technical_feasibility_score": 7.5}),
    }
    result = orch.run_adversarial_drill(session, scenario=chaos)
    _assert(result["status"] == "dry_run", "Dry-run status")
    _assert(result["scenario"].scenario_id == "market_crash", "Dry-run scenario correct")
    _assert("CTO" in result["drill_contexts"], "Dry-run has CTO context")
    _assert("CRITIC" in result["drill_contexts"], "Dry-run has CRITIC context")
    _assert("RED TEAM DRILL" in result["drill_contexts"]["CTO"], "CTO context has drill banner")
    _assert("RED TEAM DRILL" in result["drill_contexts"]["CRITIC"], "CRITIC context has drill banner")

    # 1.6 Live drill — passes on first iteration
    print("\n=== PHASE 1: LIVE DRILL TESTS ===")

    def _mock_agent_pass(agent_name, prompt):
        """Mock agent that always returns high scores."""
        if agent_name == "CRITIC":
            return json.dumps({
                "agreement_level": 9.0, "verdict": "APPROVE",
                "objections": [], "confidence": 0.9,
            })
        if agent_name == "CTO":
            return json.dumps({
                "technical_feasibility_score": 9.0, "recommendation": "BUILD",
                "tech_stack": ["FastAPI"], "confidence": 0.9,
            })
        return json.dumps({"recommendation": "PROCEED", "confidence": 0.8})

    session2 = orch.start_session("DrillPass", PIPELINE_ADVERSARIAL_DRILL, "Test project")
    session2["reports"] = {"CMO": _make_report("CMO")}
    result_pass = orch.run_adversarial_drill(session2, scenario=chaos, agent_call_fn=_mock_agent_pass)
    _assert(result_pass["status"] == "passed", "Drill passes with high scores")
    _assert(result_pass["iterations"] == 1, "Passed on iteration 1")
    _assert(result_pass["final_score"] >= 8.0, f"Final score >= 8.0 (got {result_pass['final_score']})")
    _assert(result_pass["escalation_reason"] is None, "No escalation needed")

    # 1.7 Live drill — fails and escalates
    def _mock_agent_fail(agent_name, prompt):
        """Mock agent that always returns low scores."""
        if agent_name == "CRITIC":
            return json.dumps({
                "agreement_level": 4.0, "verdict": "REJECT",
                "objections": ["Unrealistic TAM assumptions", "No pivot plan"],
                "confidence": 0.3,
            })
        return json.dumps({"recommendation": "PROCEED", "confidence": 0.5})

    session3 = orch.start_session("DrillFail", PIPELINE_ADVERSARIAL_DRILL, "Test project")
    session3["reports"] = {"CMO": _make_report("CMO")}
    result_fail = orch.run_adversarial_drill(session3, scenario=chaos, max_retries=2, agent_call_fn=_mock_agent_fail)
    _assert(result_fail["status"] == "escalated", "Drill escalates on failure")
    _assert(result_fail["iterations"] == 2, f"Exhausted 2 retries (got {result_fail['iterations']})")
    _assert(result_fail["final_score"] < 8.0, "Final score below threshold")
    _assert(result_fail["escalation_reason"] is not None, "Escalation reason provided")
    _assert("market_crash" in result_fail["escalation_reason"], "Escalation mentions scenario")

    # 1.8 Session stores drill_results
    _assert(session2.get("drill_results") is not None, "Passed drill stored in session")
    _assert(session2["drill_results"]["status"] == "passed", "Session drill status is passed")
    _assert(session3.get("drill_results") is not None, "Failed drill stored in session")
    _assert(session3["drill_results"]["status"] == "escalated", "Session drill status is escalated")

finally:
    shutil.rmtree(tmp, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
# Phase 2: Commander's Intent / Strategic Mirror
# ═══════════════════════════════════════════════════════════════

print("\n=== PHASE 2: STRATEGY MODE MODEL TESTS ===")

# 2.1 StrategyMode creation
aggressive = STRATEGY_PRESETS["aggressive_growth"]
_assert(aggressive.mode == "aggressive_growth", "Aggressive mode string")
_assert(aggressive.gate_threshold_modifier == -1.0, "Aggressive lowers thresholds")
_assert(aggressive.risk_tolerance == "high", "Aggressive risk tolerance")
_assert(aggressive.budget_priority == "speed", "Aggressive budget priority")

lean = STRATEGY_PRESETS["lean_mvp"]
_assert(lean.mode == "lean_mvp", "Lean mode string")
_assert(lean.gate_threshold_modifier == +1.0, "Lean raises thresholds")
_assert(lean.risk_tolerance == "low", "Lean risk tolerance")
_assert(lean.budget_priority == "cost", "Lean budget priority")

balanced = STRATEGY_PRESETS["balanced"]
_assert(balanced.gate_threshold_modifier == 0.0, "Balanced has no modifier")

# 2.2 get_strategy_mode
custom = get_strategy_mode("custom", "Focus on enterprise clients only")
_assert(custom.mode == "custom", "Custom mode via get_strategy_mode")
_assert(custom.custom_directive == "Focus on enterprise clients only", "Custom directive preserved")
fallback = get_strategy_mode("nonexistent")
_assert(fallback.mode == "balanced", "Unknown mode falls back to balanced")

# 2.3 to_prompt_block
print("\n=== PHASE 2: PROMPT INJECTION TESTS ===")
agg_block = aggressive.to_prompt_block()
_assert("STRATEGIC PHILOSOPHY" in agg_block, "Aggressive has philosophy header")
_assert("SPEED" in agg_block, "Aggressive mentions SPEED")
_assert("MARKET CAPTURE" in agg_block, "Aggressive mentions market capture")
_assert("HIGH" in agg_block, "Aggressive shows HIGH risk tolerance")

lean_block = lean.to_prompt_block()
_assert("COST EFFICIENCY" in lean_block, "Lean mentions cost efficiency")
_assert("LOW" in lean_block, "Lean shows LOW risk tolerance")
_assert("Survival" in lean_block, "Lean mentions survival")

balanced_block = balanced.to_prompt_block()
_assert(balanced_block == "", "Balanced produces empty block (no injection)")

custom_block = custom.to_prompt_block()
_assert("enterprise clients" in custom_block, "Custom directive appears in block")

# 2.4 Strategy injection in build_handoff_context
print("\n=== PHASE 2: STRATEGY CONTEXT INJECTION TESTS ===")
tmp2 = tempfile.mkdtemp()
try:
    store2 = ReportStore(base_dir=tmp2)
    orch2 = WarRoomOrchestrator(store=store2)
    step = PipelineStep(agent_name="CMO", phase="market_research", depends_on=[])

    ctx_no_strategy = orch2.build_handoff_context(step, {}, "Build a SaaS app")
    _assert("STRATEGIC PHILOSOPHY" not in ctx_no_strategy, "No strategy = no injection")

    ctx_aggressive = orch2.build_handoff_context(step, {}, "Build a SaaS app", strategy_mode=aggressive)
    _assert("STRATEGIC PHILOSOPHY" in ctx_aggressive, "Aggressive strategy injected")
    _assert("SPEED" in ctx_aggressive, "Aggressive context mentions SPEED")

    ctx_lean = orch2.build_handoff_context(step, {}, "Build a SaaS app", strategy_mode=lean)
    _assert("COST EFFICIENCY" in ctx_lean, "Lean strategy injected")

    ctx_balanced = orch2.build_handoff_context(step, {}, "Build a SaaS app", strategy_mode=balanced)
    _assert("STRATEGIC PHILOSOPHY" not in ctx_balanced, "Balanced = no injection")

    ctx_custom = orch2.build_handoff_context(step, {}, "Build a SaaS app", strategy_mode=custom)
    _assert("enterprise clients" in ctx_custom, "Custom directive injected into context")

    # 2.5 Combined: Strategy + Chaos
    print("\n=== PHASE 2: COMBINED STRATEGY + CHAOS ===")
    ctx_combo = orch2.build_handoff_context(
        step, {}, "Build a SaaS app",
        strategy_mode=aggressive, chaos_scenario=CHAOS_LIBRARY[0]
    )
    _assert("STRATEGIC PHILOSOPHY" in ctx_combo, "Strategy present in combo")
    _assert("RED TEAM DRILL" in ctx_combo, "Chaos present in combo")
    _assert("SPEED" in ctx_combo, "Aggressive philosophy in combo")
    _assert("TAM drops" in ctx_combo, "Crisis description in combo")

    # 2.6 Strategy-modified gates
    print("\n=== PHASE 2: STRATEGY-MODIFIED GATE TESTS ===")
    cto_step = PipelineStep(agent_name="CTO", phase="feasibility", depends_on=[], is_gate=True, gate_threshold=4.0)
    cto_report = _make_report("CTO", handoff_payload={"technical_feasibility_score": 3.5})

    # Without strategy: 3.5 < 4.0 → FAIL
    gate_default = orch2.check_gate(cto_step, cto_report)
    _assert(gate_default["passed"] is False, "Default gate: 3.5 < 4.0 fails")
    _assert(gate_default["effective_threshold"] == 4.0, "Default effective threshold is 4.0")

    # Aggressive (-1.0): effective = 3.0, 3.5 >= 3.0 → PASS
    gate_agg = orch2.check_gate(cto_step, cto_report, strategy_mode=aggressive)
    _assert(gate_agg["passed"] is True, "Aggressive gate: 3.5 >= 3.0 passes")
    _assert(gate_agg["effective_threshold"] == 3.0, "Aggressive effective threshold is 3.0")

    # Lean (+1.0): effective = 5.0, 3.5 < 5.0 → FAIL
    gate_lean = orch2.check_gate(cto_step, cto_report, strategy_mode=lean)
    _assert(gate_lean["passed"] is False, "Lean gate: 3.5 < 5.0 fails")
    _assert(gate_lean["effective_threshold"] == 5.0, "Lean effective threshold is 5.0")

    # CRITIC gate with strategy
    critic_step = PipelineStep(agent_name="CRITIC", phase="adversarial", depends_on=[], is_gate=True, gate_threshold=7.0)
    critic_report = _make_report("CRITIC", agreement_level=6.5)

    gate_critic_default = orch2.check_gate(critic_step, critic_report)
    _assert(gate_critic_default["passed"] is False, "Critic default: 6.5 < 7.0 fails")

    gate_critic_agg = orch2.check_gate(critic_step, critic_report, strategy_mode=aggressive)
    _assert(gate_critic_agg["passed"] is True, "Critic aggressive: 6.5 >= 6.0 passes")
    _assert(gate_critic_agg["effective_threshold"] == 6.0, "Critic aggressive threshold is 6.0")

    # CEO gate: not affected by modifier
    ceo_step = PipelineStep(agent_name="CEO", phase="validation", depends_on=[], is_gate=True)
    ceo_report = _make_report("CEO", handoff_payload={"approved_for_phase2": True, "growth_target_alignment": "ALIGNED"})
    gate_ceo = orch2.check_gate(ceo_step, ceo_report, strategy_mode=lean)
    _assert(gate_ceo["passed"] is True, "CEO gate unaffected by strategy modifier")
    _assert(gate_ceo["effective_threshold"] is None, "CEO gate has no effective_threshold")

    # 2.7 start_session stores strategy_mode and stress_test
    print("\n=== PHASE 2: SESSION METADATA TESTS ===")
    session_agg = orch2.start_session(
        "AggressiveProject",
        PIPELINE_ADVERSARIAL_DRILL,
        "Build fast",
        strategy_mode=aggressive,
        stress_test=True,
    )
    _assert(session_agg["strategy_mode"].mode == "aggressive_growth", "Session stores strategy_mode")
    _assert(session_agg["stress_test"] is True, "Session stores stress_test flag")
    _assert(session_agg["drill_results"] is None, "Drill results start as None")

    session_default = orch2.start_session("DefaultProject", PIPELINE_ADVERSARIAL_DRILL, "Build something")
    _assert(session_default["strategy_mode"].mode == "balanced", "Default strategy is balanced")
    _assert(session_default["stress_test"] is False, "Default stress_test is False")

    # 2.8 Threshold floor: modifier can't push below 1.0
    print("\n=== PHASE 2: THRESHOLD FLOOR TEST ===")
    low_gate = PipelineStep(agent_name="CTO", phase="test", depends_on=[], is_gate=True, gate_threshold=1.5)
    # Aggressive: 1.5 - 1.0 = 0.5, floored to 1.0
    extreme_agg = StrategyMode(mode="aggressive_growth", label="Extreme", gate_threshold_modifier=-2.0, risk_tolerance="high", budget_priority="speed")
    gate_floor = orch2.check_gate(low_gate, cto_report, strategy_mode=extreme_agg)
    _assert(gate_floor["effective_threshold"] == 1.0, f"Floor at 1.0 (got {gate_floor['effective_threshold']})")

finally:
    shutil.rmtree(tmp2, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
# Run existing tests to verify backward compat
# ═══════════════════════════════════════════════════════════════
print("\n=== BACKWARD COMPATIBILITY: check_gate without strategy ===")
tmp3 = tempfile.mkdtemp()
try:
    store3 = ReportStore(base_dir=tmp3)
    orch3 = WarRoomOrchestrator(store=store3)

    # Old-style call without strategy_mode should still work
    cto_step_v1 = PipelineStep(agent_name="CTO", phase="feasibility", depends_on=[], is_gate=True, gate_threshold=4.0)
    cto_report_v1 = _make_report("CTO", handoff_payload={"technical_feasibility_score": 7.5})
    gate_v1 = orch3.check_gate(cto_step_v1, cto_report_v1)
    _assert(gate_v1["passed"] is True, "v1 compat: 7.5 >= 4.0 passes without strategy")

    # build_handoff_context without new params
    step_v1 = PipelineStep(agent_name="CMO", phase="test", depends_on=[])
    ctx_v1 = orch3.build_handoff_context(step_v1, {}, "Test intent")
    _assert("WAR ROOM BRIEFING" in ctx_v1, "v1 compat: build_handoff_context works without new params")

    # start_session without new params
    session_v1 = orch3.start_session("V1Project", [step_v1], "Test intent")
    _assert(session_v1["status"] == "active", "v1 compat: start_session works without new params")

finally:
    shutil.rmtree(tmp3, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
# Results
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"RESULTS: {_passed} passed, {_failed} failed, {_passed + _failed} total")
print(f"{'='*60}")
if _failed == 0:
    print("ALL TESTS PASSED")
else:
    print(f"FAILURES DETECTED: {_failed}")
    sys.exit(1)

