"""
test_warroom_protocol.py — Unit tests for War Room Protocol v1.1
"""
import sys, os, json, tempfile, shutil

sys.stdout.reconfigure(encoding="utf-8")

from warroom_protocol import (
    WarRoomReport, ReportStore, WarRoomOrchestrator,
    get_orchestrator, parse_agent_response,
    CMOHandoff, CTOHandoff, CFOHandoff, CEOHandoff, CLOHandoff, CriticHandoff,
    build_typed_handoff, HANDOFF_MODELS, PipelineStep,
)

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} — {detail}")


print("=== 1. Typed Handoff Model Tests ===")

cmo = CMOHandoff(
    marketing_cost=25000,
    projected_revenue=100000,
    market_size_tam=1e9,
    market_size_sam=5e8,
    market_size_som=1e7,
    customer_profile="SaaS buyers aged 25-45",
    cost_per_acquisition=15.0,
)
test("CMOHandoff creation", cmo.marketing_cost == 25000)
test("CMOHandoff TAM typed", cmo.market_size_tam == 1e9)
test("CMOHandoff customer_profile", cmo.customer_profile == "SaaS buyers aged 25-45")
test("CMOHandoff defaults", cmo.competitive_moat == "" and cmo.channels == [])

cto = CTOHandoff(
    technical_feasibility_score=8.5,
    tech_stack=["Python", "FastAPI", "React"],
    infrastructure_cost_estimate=450,
)
test("CTOHandoff creation", cto.technical_feasibility_score == 8.5)
test("CTOHandoff stack", len(cto.tech_stack) == 3)
test("CTOHandoff defaults", cto.development_buffer_weeks == 0.0)

cfo = CFOHandoff(roi_percentage=124.5, breakeven_month=8, npv=50000)
test("CFOHandoff creation", cfo.roi_percentage == 124.5)
test("CFOHandoff breakeven", cfo.breakeven_month == 8)

critic = CriticHandoff(agreement_level=7.5, verdict="REVISE", objections=["Cost too high"])
test("CriticHandoff creation", critic.agreement_level == 7.5)
test("CriticHandoff objections", len(critic.objections) == 1)


print("\n=== 2. build_typed_handoff Tests ===")

raw_cmo = {
    "marketing_cost": 50000,
    "projected_revenue": 200000,
    "demographic_reach": 1000000,
    "cost_per_acquisition": 15.0,
    "extra_junk_field": "should be ignored",
    "customer_profile": "Enterprise CTOs"
}
typed = build_typed_handoff("CMO", raw_cmo)
test("build_typed_handoff returns CMOHandoff", isinstance(typed, CMOHandoff))
test("Typed CMO cost", typed.marketing_cost == 50000)
test("Typed CMO customer_profile", typed.customer_profile == "Enterprise CTOs")
test("Typed CMO defaults filled", typed.market_size_tam == 0.0)

# CTO with nested cfo_ready_metrics
raw_cto = {
    "technical_feasibility_score": 7.0,
    "tech_stack": ["Node.js"],
    "cfo_ready_metrics": {
        "infrastructure_cost_estimate": 900,
        "development_buffer_weeks": 6,
        "tech_debt_risk_premium_pct": 12,
    }
}
typed_cto = build_typed_handoff("CTO", raw_cto)
test("CTO flattens cfo_ready_metrics", typed_cto.infrastructure_cost_estimate == 900)
test("CTO dev buffer from nested", typed_cto.development_buffer_weeks == 6)

# Unknown agent falls back
raw_unknown = {"some": "data"}
result = build_typed_handoff("UNKNOWN_AGENT", raw_unknown)
test("Unknown agent fallback", isinstance(result, dict))


print("\n=== 3. parse_agent_response Tests ===")

mock_cmo_json = json.dumps({
    "marketing_cost": 30000,
    "projected_revenue": 150000,
    "demographic_reach": 500000,
    "cost_per_acquisition": 12.5,
    "market_strategy": "Direct-to-consumer via social media",
    "market_size_tam": 5000000000,
    "customer_profile": "Small business owners",
    "recommendation": "PROCEED",
    "confidence": 0.85,
})
report = parse_agent_response(mock_cmo_json, "CMO", "market", "TestProject")
test("CMO report agent", report.agent == "CMO")
test("CMO report phase", report.phase == "market")
test("CMO handoff is typed dict", "marketing_cost" in report.handoff_payload)
test("CMO handoff has customer_profile", report.handoff_payload.get("customer_profile") == "Small business owners")
test("CMO handoff has TAM", report.handoff_payload.get("market_size_tam") == 5000000000)
test("CMO confidence", report.confidence == 0.85)

# Critic response
mock_critic = json.dumps({
    "agreement_level": 8.5,
    "verdict": "APPROVE",
    "objections": ["Revenue timeline aggressive"],
    "cost_challenge": "Marketing budget unsubstantiated",
    "confidence": 0.7,
})
critic_report = parse_agent_response(mock_critic, "CRITIC", "adversarial", "TestProject")
test("Critic agreement_level", critic_report.agreement_level == 8.5)
test("Critic verdict", critic_report.verdict == "APPROVE")
test("Critic objections", len(critic_report.objections) == 1)
test("Critic handoff typed", "cost_challenge" in critic_report.handoff_payload)

# Plain text fallback
plain_text = "The market looks promising but we need more data on pricing."
plain_report = parse_agent_response(plain_text, "CMO", "market")
test("Plain text fallback", plain_report.confidence == 0.3)
test("Plain text summary", "promising" in plain_report.summary_report)


print("\n=== 4. Pipeline Selection Tests ===")

o = get_orchestrator()

p1 = o.compose_pipeline("Start-up business plan for AI SaaS product")
test("Startup -> full_business_plan", len(p1) == 5 and p1[0].agent_name == "CMO")

p2 = o.compose_pipeline("Is this architecture technically feasible?")
test("Architecture -> technical_assessment", len(p2) == 2 and p2[0].agent_name == "CTO")

p3 = o.compose_pipeline("Analyze competitor landscape and marketing positioning")
test("Competitor -> market_analysis", len(p3) == 3 and p3[0].agent_name == "CMO")

p4 = o.compose_pipeline("Review ROI and financial projections")
test("ROI -> financial_deep_dive", len(p4) == 2 and p4[0].agent_name == "CFO")

p5 = o.compose_pipeline("Check trademark and IP compliance")
test("Trademark -> legal_review", len(p5) == 2 and p5[0].agent_name == "CLO")

p6 = o.compose_pipeline("evaluate this thing")
test("Generic -> full_business_plan (default)", len(p6) == 5)

summary = o.get_pipeline_summary(p1)
test("Pipeline summary ASCII-safe", ">" in summary and "\u2192" not in summary, summary)


print("\n=== 5. ReportStore Tests ===")

test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_reports_tmp")
os.makedirs(test_dir, exist_ok=True)
store = ReportStore(base_dir=test_dir)

r = WarRoomReport(
    agent="CMO", phase="market", project_id="TestProject",
    summary_report="Test summary", confidence=0.9,
    handoff_payload={"marketing_cost": 25000, "customer_profile": "Test"},
)
path = store.save(r)
test("Report saved", os.path.exists(path))

loaded = store.get_latest("TestProject", "CMO", ghost_alert=False)
test("Report loaded", loaded is not None and loaded.agent == "CMO")
test("Loaded confidence", loaded.confidence == 0.9)
test("Loaded handoff", loaded.handoff_payload.get("marketing_cost") == 25000)

# Ghost Retrieval
missing = store.get_latest("TestProject", "CFO", ghost_alert=True)
test("Ghost returns None", missing is None)
alerts_path = os.path.join(test_dir, "ghost_alerts.json")
test("Ghost alert file created", os.path.exists(alerts_path))
if os.path.exists(alerts_path):
    with open(alerts_path) as f:
        alerts = json.load(f)
    test("Ghost alert content", alerts[0]["missing_agent"] == "CFO")
    test("Ghost alert severity", alerts[0]["severity"] == "HIGH")

# All project reports
all_reports = store.get_all_for_project("TestProject")
test("get_all_for_project", len(all_reports) >= 1)


print("\n=== 6. Gate Check Tests ===")

step_cto = PipelineStep(agent_name="CTO", phase="technical", is_gate=True, gate_threshold=4.0)
cto_report = WarRoomReport(
    agent="CTO", phase="technical",
    handoff_payload={"technical_feasibility_score": 7.5}
)
gate_result = o.check_gate(step_cto, cto_report)
test("CTO gate passes (7.5 >= 4.0)", gate_result["passed"] is True)

cto_report_low = WarRoomReport(
    agent="CTO", phase="technical",
    handoff_payload={"technical_feasibility_score": 3.0}
)
gate_result_low = o.check_gate(step_cto, cto_report_low)
test("CTO gate fails (3.0 < 4.0)", gate_result_low["passed"] is False)

step_critic = PipelineStep(agent_name="CRITIC", phase="adversarial", is_gate=True, gate_threshold=8.0)
critic_report = WarRoomReport(
    agent="CRITIC", phase="adversarial",
    agreement_level=9.0
)
gate_critic = o.check_gate(step_critic, critic_report)
test("Critic gate passes (9.0 >= 8.0)", gate_critic["passed"] is True)

critic_report_low = WarRoomReport(
    agent="CRITIC", phase="adversarial",
    agreement_level=6.0
)
gate_critic_low = o.check_gate(step_critic, critic_report_low)
test("Critic gate fails (6.0 < 8.0)", gate_critic_low["passed"] is False)


print("\n=== 7. Handoff Context Builder Tests ===")

step = PipelineStep(agent_name="CFO", phase="financials", depends_on=["CMO", "CTO"])
cmo_report = WarRoomReport(
    agent="CMO", phase="market", project_id="TestProject",
    summary_report="Market is $1B TAM. Strategy: direct social media.",
    confidence=0.8,
    handoff_payload={"marketing_cost": 30000, "projected_revenue": 150000},
)
cto_rpt = WarRoomReport(
    agent="CTO", phase="technical", project_id="TestProject",
    summary_report="Feasible with Python/FastAPI. 8 week timeline.",
    confidence=0.9,
    handoff_payload={"technical_feasibility_score": 8.0, "infrastructure_cost_estimate": 400},
)
context = o.build_handoff_context(
    step, {"CMO": cmo_report, "CTO": cto_rpt},
    "Build a business plan for AI tutoring app"
)
test("Context includes CMO data", "marketing_cost: 30000" in context)
test("Context includes CTO data", "infrastructure_cost_estimate: 400" in context)
test("Context includes directive", "AI tutoring app" in context)
test("Context includes CFO mission", "financial model" in context.lower())


# Cleanup
shutil.rmtree(test_dir, ignore_errors=True)

print(f"\n{'='*50}")
print(f"RESULTS: {passed} passed, {failed} failed, {passed+failed} total")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print(f"FAILURES DETECTED: {failed}")
    sys.exit(1)
