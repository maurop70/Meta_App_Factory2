"""
test_warroom_e2e.py — End-to-End Stress Test for War Room Orchestrator
======================================================================
Tests the FULL pipeline with realistic agent responses, verifying:
1. Pipeline Selection: "technical feasibility" triggers CTO-first chain
2. Real-time Report Persistence: Reports appear in Boardroom_Exchange/reports/
3. Gate Failure Simulation: CTO threshold at 9.0 correctly halts the pipeline
4. Multi-pipeline routing: Different intents trigger correct chains
5. Iteration 2+ context building: Critic objections flow back correctly

Run: python -X utf8 test_warroom_e2e.py
"""

import sys, os, json, shutil, time

sys.stdout.reconfigure(encoding="utf-8")

from warroom_protocol import (
    WarRoomReport, ReportStore, WarRoomOrchestrator, PipelineStep,
    get_orchestrator, get_report_store, parse_agent_response,
    build_typed_handoff, CMOHandoff, CTOHandoff, CFOHandoff, CriticHandoff,
    PIPELINE_FULL_BUSINESS_PLAN, PIPELINE_TECHNICAL_ASSESSMENT,
    PIPELINE_MARKET_ANALYSIS, PIPELINE_LEGAL_REVIEW, PIPELINE_FINANCIAL_DEEP_DIVE,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
E2E_REPORTS_DIR = os.path.join(SCRIPT_DIR, "Project_Aether", "Boardroom_Exchange", "reports", "_e2e_stress_test")

passed = 0
failed = 0


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} -- {detail}")


# ==================================================================
# SCENARIO 1: Pipeline Selection — Technical Feasibility Intent
# Verifies: CTO-first chain is selected, NOT full business plan
# ==================================================================
print("=" * 60)
print("SCENARIO 1: Pipeline Selection — Technical Feasibility")
print("=" * 60)

orch = WarRoomOrchestrator(store=ReportStore(base_dir=E2E_REPORTS_DIR))

# The exact intent the user specified
intent_1 = "Build a technical feasibility study for an AI-driven logistics tracker"
pipeline_1 = orch.compose_pipeline(intent_1)

test(
    "Technical intent selects CTO-first chain",
    len(pipeline_1) == 2 and pipeline_1[0].agent_name == "CTO",
    f"Got {[s.agent_name for s in pipeline_1]} instead of ['CTO', 'CRITIC']"
)
test(
    "First step is CTO (not CMO)",
    pipeline_1[0].agent_name == "CTO",
)
test(
    "Second step is CRITIC",
    pipeline_1[1].agent_name == "CRITIC",
)
test(
    "CTO step is a gate",
    pipeline_1[0].is_gate is True,
)
test(
    "Pipeline summary correct",
    "CTO" in orch.get_pipeline_summary(pipeline_1) and "CRITIC" in orch.get_pipeline_summary(pipeline_1),
)

# Verify other intents route correctly
pipeline_biz = orch.compose_pipeline("Start-up business plan for new SaaS venture")
test("Business plan intent -> full pipeline", len(pipeline_biz) == 5)

pipeline_mkt = orch.compose_pipeline("Analyze competitor landscape for fitness app")
test("Market intent -> market pipeline", len(pipeline_mkt) == 3 and pipeline_mkt[0].agent_name == "CMO")

pipeline_legal = orch.compose_pipeline("Review trademark compliance for our brand")
test("Legal intent -> legal pipeline", len(pipeline_legal) == 2 and pipeline_legal[0].agent_name == "CLO")

pipeline_fin = orch.compose_pipeline("Deep dive into ROI and cash flow projections")
test("Financial intent -> finance pipeline", len(pipeline_fin) == 2 and pipeline_fin[0].agent_name == "CFO")


# ==================================================================
# SCENARIO 2: Real-time Report Persistence
# Simulates the CTO->CRITIC technical pipeline with realistic data
# ==================================================================
print()
print("=" * 60)
print("SCENARIO 2: Real-time Report Persistence (Vault Check)")
print("=" * 60)

session = orch.start_session("_e2e_stress_test", pipeline_1, intent_1)

# Simulate CTO response (realistic JSON from Gemini fallback)
mock_cto_response = json.dumps({
    "technical_feasibility_score": 7.5,
    "project_type": "DIGITAL",
    "tech_stack": ["Python", "FastAPI", "PostgreSQL", "Redis", "React", "Mapbox GL"],
    "implementation_timeline_weeks": 16,
    "v3_compliance": "COMPLIANT",
    "pre_deploy_gate_status": "CONDITIONAL_PASS",
    "automation_monitoring_layer": "Prometheus + Grafana for fleet telemetry; Redis pub/sub for real-time updates",
    "skills_library_blocks": ["geospatial-engine", "fleet-tracker", "route-optimizer"],
    "cfo_ready_metrics": {
        "infrastructure_cost_estimate": 1200,
        "development_buffer_weeks": 6,
        "tech_debt_risk_premium_pct": 12
    },
    "recommendation": "PROCEED",
    "confidence": 0.82,
    "executive_summary": (
        "The AI-driven logistics tracker is technically feasible with a score of 7.5/10. "
        "Core architecture uses FastAPI backend with PostgreSQL for route data, Redis for real-time "
        "fleet positioning, and Mapbox GL for visualization. Key risk: geospatial computation at scale "
        "requires dedicated GPU instances, adding $1,200/mo to infrastructure. Timeline: 16 weeks "
        "with 6-week buffer for ML model training. V3 Resilience Core is achievable."
    ),
    "risks": [
        {"severity": "HIGH", "description": "GPU compute costs may scale non-linearly with fleet size", "mitigation": "Implement batch processing with 5-minute aggregation windows"},
        {"severity": "MEDIUM", "description": "Mapbox GL licensing for commercial use", "mitigation": "Evaluate OpenStreetMap as fallback"},
        {"severity": "LOW", "description": "Redis single point of failure", "mitigation": "Redis Sentinel cluster configuration"}
    ]
})

cto_report = parse_agent_response(mock_cto_response, "CTO", "technical", "_e2e_stress_test", 1)
cto_path = orch.store.save(cto_report)
session["reports"]["CTO"] = cto_report

# Verify report exists on disk IN REAL TIME
test("CTO report file exists on disk", os.path.exists(cto_path))
test("CTO report filename contains agent", "CTO_technical_" in os.path.basename(cto_path))

# Load it back and verify data integrity
loaded = orch.store.get_latest("_e2e_stress_test", "CTO", ghost_alert=False)
test("Loaded report matches saved", loaded is not None and loaded.agent == "CTO")
test("Feasibility score survives round-trip", loaded.handoff_payload.get("technical_feasibility_score") == 7.5)
test("Tech stack survives round-trip", "FastAPI" in str(loaded.handoff_payload.get("tech_stack", [])))
test("Infra cost flattened from cfo_ready_metrics", loaded.handoff_payload.get("infrastructure_cost_estimate") == 1200)
test("Dev buffer flattened", loaded.handoff_payload.get("development_buffer_weeks") == 6)
test("Risks extracted", len(loaded.risks) == 3)
test("High-severity risk identified", any(r.get("severity") == "HIGH" for r in loaded.risks))
test("Executive summary captured", "logistics" in loaded.summary_report.lower())

# Now simulate CRITIC response
critic_handoff = orch.build_handoff_context(
    PipelineStep(agent_name="CRITIC", phase="adversarial", depends_on=["CTO"]),
    session["reports"], intent_1, iteration=1
)
test("CRITIC context includes CTO data", "technical_feasibility_score" in critic_handoff or "7.5" in critic_handoff)
test("CRITIC context includes infrastructure cost", "1200" in critic_handoff or "infrastructure_cost" in critic_handoff)

mock_critic_response = json.dumps({
    "agreement_level": 7.2,
    "verdict": "REVISE",
    "objections": [
        "GPU cost scaling is underestimated - needs load testing data",
        "16-week timeline assumes no regulatory hurdles for fleet data",
        "No mention of data privacy compliance (GDPR/CCPA) for location tracking"
    ],
    "cost_challenge": "Infrastructure at $1,200/mo assumes linear scaling but GPU batch processing introduces step-function costs",
    "revenue_challenge": "No revenue model provided - this is a cost center analysis only",
    "evidence_demanded": "Load test results for 1000+ concurrent vehicles; GDPR compliance audit",
    "recommendation": "REVISE",
    "confidence": 0.75
})

critic_report = parse_agent_response(mock_critic_response, "CRITIC", "adversarial", "_e2e_stress_test", 1)
critic_path = orch.store.save(critic_report)
session["reports"]["CRITIC"] = critic_report

test("CRITIC report saved", os.path.exists(critic_path))
test("CRITIC agreement_level parsed", critic_report.agreement_level == 7.2)
test("CRITIC objections parsed", len(critic_report.objections) == 3)
test("CRITIC verdict parsed", critic_report.handoff_payload.get("verdict") == "REVISE")

# Verify all reports for project
all_reports = orch.store.get_all_for_project("_e2e_stress_test")
test("Total reports in vault: 2", len(all_reports) == 2)

# List actual files on disk
report_dir = os.path.join(E2E_REPORTS_DIR, "_e2e_stress_test")
if os.path.exists(report_dir):
    files = [f for f in os.listdir(report_dir) if f.endswith(".json")]
    test(f"Vault contains {len(files)} JSON files", len(files) == 2)
    for f in sorted(files):
        size = os.path.getsize(os.path.join(report_dir, f))
        print(f"    -> {f} ({size:,} bytes)")


# ==================================================================
# SCENARIO 3: Gate Failure Simulation
# Set CTO threshold to 9.0 — score of 7.5 should BLOCK
# ==================================================================
print()
print("=" * 60)
print("SCENARIO 3: Gate Failure Simulation (Threshold = 9.0)")
print("=" * 60)

# Create a gate step with threshold 9.0 (simulating the user's request)
strict_gate = PipelineStep(
    agent_name="CTO",
    phase="technical",
    is_gate=True,
    gate_threshold=9.0  # Impossibly strict - should block 7.5
)

gate_result = orch.check_gate(strict_gate, cto_report)
test(
    "Gate BLOCKS at 7.5 < 9.0",
    gate_result["passed"] is False,
    f"Expected blocked, got: {gate_result}"
)
test(
    "Gate reason explains threshold",
    "9.0" in gate_result["reason"] and "7.5" in gate_result["reason"],
    gate_result["reason"]
)
test(
    "Gate score is 7.5",
    gate_result["score"] == 7.5,
)

# Now test with normal threshold (should pass)
normal_gate = PipelineStep(
    agent_name="CTO",
    phase="technical",
    is_gate=True,
    gate_threshold=4.0
)
normal_result = orch.check_gate(normal_gate, cto_report)
test(
    "Gate PASSES at 7.5 >= 4.0",
    normal_result["passed"] is True,
)

# Test CRITIC gate failure
strict_critic_gate = PipelineStep(
    agent_name="CRITIC",
    phase="adversarial",
    is_gate=True,
    gate_threshold=8.0  # 7.2 < 8.0 should fail
)
critic_gate = orch.check_gate(strict_critic_gate, critic_report)
test(
    "CRITIC gate BLOCKS at 7.2 < 8.0",
    critic_gate["passed"] is False,
)

# Test CRITIC gate pass
lenient_critic_gate = PipelineStep(
    agent_name="CRITIC",
    phase="adversarial",
    is_gate=True,
    gate_threshold=7.0  # 7.2 >= 7.0 should pass
)
lenient_result = orch.check_gate(lenient_critic_gate, critic_report)
test(
    "CRITIC gate PASSES at 7.2 >= 7.0",
    lenient_result["passed"] is True,
)


# ==================================================================
# SCENARIO 4: Iteration 2 Context (Revision Loop)
# Verify CRITIC objections flow back into CTO's next iteration
# ==================================================================
print()
print("=" * 60)
print("SCENARIO 4: Iteration 2 Context (Revision Loop)")
print("=" * 60)

# Build CTO context for iteration 2 — should include CRITIC's objections
cto_step_iter2 = PipelineStep(agent_name="CTO", phase="technical", depends_on=[])
iter2_context = orch.build_handoff_context(
    cto_step_iter2,
    session["reports"],
    intent_1,
    iteration=2,
)

test(
    "Iteration 2 context includes CRITIC feedback header",
    "CRITIC FEEDBACK" in iter2_context,
    f"Context preview: {iter2_context[:200]}..."
)
test(
    "Iteration 2 context includes CRITIC score",
    "7.2" in iter2_context,
)
test(
    "Iteration 2 context includes CRITIC objections",
    "GPU" in iter2_context or "GDPR" in iter2_context,
)
test(
    "Iteration 2 context says 'address these objections'",
    "address" in iter2_context.lower() and "objection" in iter2_context.lower(),
)

# Verify compressed summary for context window management
cmo_stub = WarRoomReport(agent="CMO", phase="market", confidence=0.85, recommendation="PROCEED",
                         risks=[{"severity": "HIGH", "description": "Market saturation risk"}])
compressed = cmo_stub.to_compressed_summary()
test("Compressed summary is compact", len(compressed) < 100, compressed)
test("Compressed includes key data", "PROCEED" in compressed and "85%" in compressed)


# ==================================================================
# SCENARIO 5: Ghost Retrieval — Missing Agent Alert
# ==================================================================
print()
print("=" * 60)
print("SCENARIO 5: Ghost Retrieval (Pipeline Break Detection)")
print("=" * 60)

# Try to get a report for an agent that hasn't run
missing = orch.store.get_latest("_e2e_stress_test", "COO", ghost_alert=True)
test("Missing COO returns None", missing is None)

# Check ghost alert was written
alerts_path = os.path.join(E2E_REPORTS_DIR, "ghost_alerts.json")
test("Ghost alerts file created", os.path.exists(alerts_path))
if os.path.exists(alerts_path):
    with open(alerts_path) as f:
        alerts = json.load(f)
    latest = alerts[-1]
    test("Ghost alert for COO", latest["missing_agent"] == "COO")
    test("Ghost alert severity HIGH", latest["severity"] == "HIGH")
    test("Ghost alert has project_id", latest["project_id"] == "_e2e_stress_test")
    test("Ghost alert has message", "Pipeline Break" in latest["message"])


# ==================================================================
# SCENARIO 6: Full Business Plan Pipeline (5-Agent Chain)
# Verifies data flows correctly through all 5 agents
# ==================================================================
print()
print("=" * 60)
print("SCENARIO 6: Full 5-Agent Pipeline Data Flow")
print("=" * 60)

full_intent = "Launch a new AI tutoring startup for K-12 students"
full_pipeline = orch.compose_pipeline(full_intent)
full_session = orch.start_session("_e2e_full_plan", full_pipeline, full_intent)

# CMO
cmo_resp = json.dumps({
    "marketing_cost": 35000, "projected_revenue": 200000,
    "market_size_tam": 8000000000, "market_size_sam": 800000000,
    "market_size_som": 20000000,
    "demographic_reach": 750000, "cost_per_acquisition": 18.50,
    "customer_profile": "Parents of K-12 students, household income $75k+",
    "market_strategy": "Content marketing via education blogs + school partnerships",
    "revenue_timeline_months": 9,
    "competitive_moat": "Personalized AI learning paths with progress tracking",
    "channels": ["Instagram", "Facebook Groups", "School District Partnerships"],
    "recommendation": "PROCEED", "confidence": 0.9,
    "executive_summary": "K-12 AI tutoring TAM is $8B. Focus on parents via education content."
})
cmo_r = parse_agent_response(cmo_resp, "CMO", "market", "_e2e_full_plan", 1)
orch.store.save(cmo_r)
full_session["reports"]["CMO"] = cmo_r

# Verify CMO typed handoff has the critical fields for CFO Excel Architect
cmo_hp = cmo_r.handoff_payload
test("CMO handoff has market_size_tam", cmo_hp.get("market_size_tam") == 8000000000)
test("CMO handoff has customer_profile", "K-12" in cmo_hp.get("customer_profile", ""))
test("CMO handoff has channels", len(cmo_hp.get("channels", [])) == 3)
test("CMO handoff has competitive_moat", len(cmo_hp.get("competitive_moat", "")) > 0)

# CEO validates
ceo_ctx = orch.build_handoff_context(
    PipelineStep(agent_name="CEO", phase="validation", depends_on=["CMO"]),
    full_session["reports"], full_intent
)
test("CEO context includes CMO TAM", "8000000000" in ceo_ctx or "8,000,000,000" in ceo_ctx or "market_size_tam" in ceo_ctx)

ceo_resp = json.dumps({
    "approved_for_phase2": True, "growth_target_alignment": "ALIGNED",
    "growth_target_annual": 250000, "strategic_direction": "Focus K-8 first, expand to high school Year 2",
    "recommendation": "PROCEED", "confidence": 0.88
})
ceo_r = parse_agent_response(ceo_resp, "CEO", "validation", "_e2e_full_plan", 1)
orch.store.save(ceo_r)
full_session["reports"]["CEO"] = ceo_r

# CTO — verify it gets BOTH CMO and CEO data
cto_ctx = orch.build_handoff_context(
    PipelineStep(agent_name="CTO", phase="technical", depends_on=["CMO", "CEO"]),
    full_session["reports"], full_intent
)
test("CTO context has CMO strategy", "content marketing" in cto_ctx.lower() or "marketing_cost" in cto_ctx)
test("CTO context has CEO approval", "approved_for_phase2" in cto_ctx or "ALIGNED" in cto_ctx)

cto_resp = json.dumps({
    "technical_feasibility_score": 8.0, "project_type": "DIGITAL",
    "tech_stack": ["Python", "FastAPI", "React", "OpenAI", "PostgreSQL"],
    "implementation_timeline_weeks": 10,
    "cfo_ready_metrics": {"infrastructure_cost_estimate": 500, "development_buffer_weeks": 3, "tech_debt_risk_premium_pct": 5},
    "v3_compliance": "COMPLIANT", "pre_deploy_gate_status": "PASS",
    "recommendation": "PROCEED", "confidence": 0.9
})
cto_r = parse_agent_response(cto_resp, "CTO", "technical", "_e2e_full_plan", 1)
orch.store.save(cto_r)
full_session["reports"]["CTO"] = cto_r

# CFO — verify ALL upstream data flows in
cfo_ctx = orch.build_handoff_context(
    PipelineStep(agent_name="CFO", phase="financials", depends_on=["CMO", "CEO", "CTO"]),
    full_session["reports"], full_intent
)
test("CFO context has CMO marketing_cost", "35000" in cfo_ctx or "marketing_cost" in cfo_ctx)
test("CFO context has CTO infra cost", "500" in cfo_ctx or "infrastructure_cost" in cfo_ctx)
test("CFO context has CEO growth target", "250000" in cfo_ctx or "growth_target" in cfo_ctx)

cfo_resp = json.dumps({
    "roi_percentage": 142.8, "roas": 5.7, "breakeven_month": 6,
    "burn_rate": 12000, "npv": 95000, "fragility_index": 18,
    "total_cost_basis": 82000, "risk_adjusted_roi": 118.5,
    "business_plan_summary": "Strong unit economics: $18.50 CPA yields 5.7x ROAS",
    "funding_required": 50000,
    "recommendation": "PROCEED", "confidence": 0.85
})
cfo_r = parse_agent_response(cfo_resp, "CFO", "financials", "_e2e_full_plan", 1)
orch.store.save(cfo_r)
full_session["reports"]["CFO"] = cfo_r

# Verify CFO typed handoff has ALL financial fields
cfo_hp = cfo_r.handoff_payload
test("CFO handoff has roi_percentage", cfo_hp.get("roi_percentage") == 142.8)
test("CFO handoff has npv", cfo_hp.get("npv") == 95000)
test("CFO handoff has fragility_index", cfo_hp.get("fragility_index") == 18)
test("CFO handoff has funding_required", cfo_hp.get("funding_required") == 50000)

# CRITIC — verify ALL 4 upstream reports flow in
critic_ctx = orch.build_handoff_context(
    PipelineStep(agent_name="CRITIC", phase="adversarial", depends_on=["CMO", "CEO", "CTO", "CFO"]),
    full_session["reports"], full_intent
)
test("CRITIC context has CMO data", "CMO Report" in critic_ctx)
test("CRITIC context has CEO data", "CEO Report" in critic_ctx)
test("CRITIC context has CTO data", "CTO Report" in critic_ctx)
test("CRITIC context has CFO data", "CFO Report" in critic_ctx)
test("CRITIC context total length reasonable", 2000 < len(critic_ctx) < 10000, f"Length: {len(critic_ctx)}")

# Final report count
all_full = orch.store.get_all_for_project("_e2e_full_plan")
test("Full pipeline produced 4 reports", len(all_full) == 4)

orch.end_session("_e2e_full_plan")


# ==================================================================
# CLEANUP
# ==================================================================
print()
print("-" * 60)
print("Cleaning up test artifacts...")

# Clean up e2e test directories
for test_project in ["_e2e_stress_test", "_e2e_full_plan"]:
    test_dir = os.path.join(E2E_REPORTS_DIR, test_project)
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir, ignore_errors=True)
# Clean ghost alerts
if os.path.exists(alerts_path):
    os.remove(alerts_path)
# Remove empty parent dirs
if os.path.exists(E2E_REPORTS_DIR):
    try:
        os.rmdir(E2E_REPORTS_DIR)
    except OSError:
        pass

print("Cleanup complete.")

# ==================================================================
# FINAL RESULTS
# ==================================================================
print()
print("=" * 60)
print(f"E2E STRESS TEST RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
print("=" * 60)
if failed == 0:
    print("ALL SCENARIOS PASSED - War Room Orchestrator is E2E verified.")
else:
    print(f"FAILURES DETECTED: {failed}")
    sys.exit(1)
