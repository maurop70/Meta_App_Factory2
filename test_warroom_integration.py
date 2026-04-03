"""Integration test: Simulates the full trigger_csuite pipeline with mock data."""
import sys, os, json, shutil

sys.stdout.reconfigure(encoding="utf-8")

from warroom_protocol import (
    WarRoomReport, ReportStore, WarRoomOrchestrator, PipelineStep,
    get_orchestrator, get_report_store, parse_agent_response,
    PIPELINE_FULL_BUSINESS_PLAN,
)

print("=== WAR ROOM INTEGRATION TEST ===\n")

store = get_report_store()
orch = get_orchestrator()

# Commander input
intent = "Build a business plan for an AI tutoring startup"
pipeline = orch.compose_pipeline(intent)
session = orch.start_session("integration_test", pipeline, intent)
print(f"Pipeline: {orch.get_pipeline_summary(pipeline)}")

# ---- CMO ----
mock_cmo = json.dumps({
    "marketing_cost": 45000, "projected_revenue": 250000,
    "market_size_tam": 5000000000, "market_size_sam": 500000000,
    "market_size_som": 15000000, "demographic_reach": 500000,
    "cost_per_acquisition": 22.50,
    "customer_profile": "K-12 parents, ages 30-45",
    "market_strategy": "Social media + content marketing to parent communities",
    "recommendation": "PROCEED", "confidence": 0.88,
})
cmo_report = parse_agent_response(mock_cmo, "CMO", "market", "integration_test", 1)
store.save(cmo_report)
session["reports"]["CMO"] = cmo_report
hp = cmo_report.handoff_payload
print(f"[CMO] TAM=${hp['market_size_tam']:,.0f}, Customer={hp['customer_profile']}")

# ---- CEO ----
ceo_step = PipelineStep(agent_name="CEO", phase="validation", depends_on=["CMO"])
ceo_ctx = orch.build_handoff_context(ceo_step, session["reports"], intent, iteration=1)
print(f"[CEO] Context length: {len(ceo_ctx)} chars")

mock_ceo = json.dumps({
    "approved_for_phase2": True, "growth_target_alignment": "ALIGNED",
    "growth_target_annual": 300000,
    "strategic_direction": "Focus on K-12 market first",
    "recommendation": "PROCEED", "confidence": 0.92,
})
ceo_report = parse_agent_response(mock_ceo, "CEO", "validation", "integration_test", 1)
store.save(ceo_report)
session["reports"]["CEO"] = ceo_report
print(f"[CEO] Approved={ceo_report.handoff_payload['approved_for_phase2']}, Alignment={ceo_report.handoff_payload['growth_target_alignment']}")

# ---- CTO ----
cto_step = PipelineStep(agent_name="CTO", phase="technical", depends_on=["CMO", "CEO"])
cto_ctx = orch.build_handoff_context(cto_step, session["reports"], intent, iteration=1)
assert "marketing_cost" in cto_ctx, "CMO data missing from CTO context"
assert "approved_for_phase2" in cto_ctx, "CEO data missing from CTO context"
print(f"[CTO] Context length: {len(cto_ctx)} chars (CMO + CEO data present)")

mock_cto = json.dumps({
    "technical_feasibility_score": 8.5, "project_type": "DIGITAL",
    "tech_stack": ["Python", "FastAPI", "React", "OpenAI"],
    "implementation_timeline_weeks": 12, "v3_compliance": "COMPLIANT",
    "pre_deploy_gate_status": "PASS",
    "cfo_ready_metrics": {
        "infrastructure_cost_estimate": 650,
        "development_buffer_weeks": 4,
        "tech_debt_risk_premium_pct": 8,
    },
    "recommendation": "PROCEED", "confidence": 0.91,
})
cto_report = parse_agent_response(mock_cto, "CTO", "technical", "integration_test", 1)
store.save(cto_report)
session["reports"]["CTO"] = cto_report
cto_hp = cto_report.handoff_payload
print(f"[CTO] Feasibility={cto_hp['technical_feasibility_score']}/10, Infra=${cto_hp['infrastructure_cost_estimate']}/mo")

# Gate check
gate_step = PipelineStep(agent_name="CTO", phase="technical", is_gate=True, gate_threshold=4.0)
gate = orch.check_gate(gate_step, cto_report)
print(f"[GATE] {gate['reason']} -> {'PASS' if gate['passed'] else 'BLOCKED'}")
assert gate["passed"], "CTO gate should pass at 8.5"

# ---- CFO ----
cfo_step = PipelineStep(agent_name="CFO", phase="financials", depends_on=["CMO", "CEO", "CTO"])
cfo_ctx = orch.build_handoff_context(cfo_step, session["reports"], intent, iteration=1)
assert "infrastructure_cost_estimate" in cfo_ctx, "CTO infra cost missing from CFO context"
assert "marketing_cost" in cfo_ctx, "CMO data missing from CFO context"
print(f"[CFO] Context length: {len(cfo_ctx)} chars (CMO + CEO + CTO data present)")

mock_cfo = json.dumps({
    "roi_percentage": 156.2, "roas": 5.5, "breakeven_month": 7,
    "burn_rate": 8500, "npv": 87000, "fragility_index": 22,
    "business_plan_summary": "Strong unit economics with $22.50 CPA...",
    "recommendation": "PROCEED", "confidence": 0.87,
})
cfo_report = parse_agent_response(mock_cfo, "CFO", "financials", "integration_test", 1)
store.save(cfo_report)
session["reports"]["CFO"] = cfo_report
cfo_hp = cfo_report.handoff_payload
print(f"[CFO] ROI={cfo_hp['roi_percentage']}%, Breakeven=Month {cfo_hp['breakeven_month']}, NPV=${cfo_hp['npv']:,.0f}")

# ---- CRITIC ----
critic_step = PipelineStep(agent_name="CRITIC", phase="adversarial", depends_on=["CMO", "CEO", "CTO", "CFO"])
critic_ctx = orch.build_handoff_context(critic_step, session["reports"], intent, iteration=1)
print(f"[CRITIC] Context length: {len(critic_ctx)} chars (ALL upstream data present)")

mock_critic = json.dumps({
    "agreement_level": 8.7, "verdict": "APPROVE",
    "objections": ["CPA of $22.50 needs validation with pilot data"],
    "cost_challenge": "Marketing budget assumes organic growth which is unproven",
    "revenue_challenge": "Revenue timeline aggressive for edu market",
    "evidence_demanded": "Pilot data from 100 users", "confidence": 0.8,
})
critic_report = parse_agent_response(mock_critic, "CRITIC", "adversarial", "integration_test", 1)
store.save(critic_report)
session["reports"]["CRITIC"] = critic_report
print(f"[CRITIC] Score={critic_report.agreement_level}/10, Verdict={critic_report.handoff_payload['verdict']}")

# ---- Persistence Verification ----
print("\n--- Persistence Check ---")
all_reports = store.get_all_for_project("integration_test")
print(f"Reports on disk: {len(all_reports)}")
for r in all_reports:
    print(f"  {r.agent}/{r.phase}: conf={r.confidence:.0%}, rec={r.recommendation}")
assert len(all_reports) == 5, f"Expected 5 reports, got {len(all_reports)}"

# ---- Ghost Retrieval Test ----
print("\n--- Ghost Retrieval ---")
missing = store.get_latest("integration_test", "COO", ghost_alert=True)
assert missing is None
alerts_path = os.path.join(store.base_dir, "ghost_alerts.json")
if os.path.exists(alerts_path):
    with open(alerts_path) as f:
        alerts = json.load(f)
    print(f"Ghost alert logged: {alerts[-1]['message'][:60]}...")

# Cleanup
orch.end_session("integration_test", "consensus_reached")
test_dir = os.path.join(store.base_dir, "integration_test")
shutil.rmtree(test_dir, ignore_errors=True)
if os.path.exists(alerts_path):
    os.remove(alerts_path)

print("\n=== INTEGRATION TEST PASSED ===")
print("Full CMO > CEO > CTO > CFO > CRITIC pipeline verified.")
print("Typed handoffs, gate checks, context building, persistence all working.")
