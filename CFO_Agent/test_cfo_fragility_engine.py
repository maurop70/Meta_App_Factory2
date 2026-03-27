"""
test_cfo_fragility_engine.py — Phantom QA Elite Test Suite
═══════════════════════════════════════════════════════════
Target: CFO Fragility Engine (Sub-Agent of CFO)
Endpoint: https://humanresource.app.n8n.cloud/webhook/cfo-execution-controller

Tests run both locally (direct HTTP) and can be triggered via
Phantom QA's /api/test/skeptic endpoint for full integration.

Test Categories:
  1. Valid Payload — Full pipeline (Fragility, ROI, NPV, Reconciliation)
  2. Gatekeeper — Missing field combinations (400 validation)
  3. Math Safety — Zero/edge values that could cause division errors
  4. Data Integrity — Verify calculation accuracy
  5. Stress — Concurrent webhook hits
  6. Malformed Input — Bad JSON, wrong types, oversized payloads
"""

import sys, json, time, asyncio, aiohttp, traceback
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

WEBHOOK_URL = "https://humanresource.app.n8n.cloud/webhook/cfo-execution-controller"
AGENT_NAME = "CFO Fragility Engine"

# ══════════════════════════════════════════════════════════
#  TEST PAYLOADS
# ══════════════════════════════════════════════════════════

VALID_PAYLOAD = {
    "cmo_spend": {"total": 50000, "allocated": 42000},
    "architect_risk": {
        "structural_score": 82, "logic_score": 78,
        "security_score": 85, "composite_score": 81.6
    },
    "campaign_list": [
        {"name": "Q2 Product Launch", "budget": 15000, "projected_revenue": 45000},
        {"name": "Brand Awareness", "budget": 12000, "projected_revenue": 18000},
        {"name": "Retention Program", "budget": 8000, "projected_revenue": 24000}
    ]
}

ZERO_EVERYTHING = {
    "cmo_spend": {"total": 0, "allocated": 0},
    "architect_risk": {"composite_score": 0},
    "campaign_list": [{"name": "Edge", "budget": 0, "projected_revenue": 0}]
}

SINGLE_CAMPAIGN = {
    "cmo_spend": {"total": 100000, "allocated": 100000},
    "architect_risk": {"structural_score": 100, "logic_score": 100, "security_score": 100, "composite_score": 100},
    "campaign_list": [
        {"name": "Mega Campaign", "budget": 50000, "projected_revenue": 200000}
    ]
}

NEGATIVE_VALUES = {
    "cmo_spend": {"total": -5000, "allocated": -3000},
    "architect_risk": {"composite_score": -10},
    "campaign_list": [{"name": "Negative Test", "budget": -100, "projected_revenue": 500}]
}

HUGE_CAMPAIGN_LIST = {
    "cmo_spend": {"total": 1000000, "allocated": 800000},
    "architect_risk": {"composite_score": 75},
    "campaign_list": [
        {"name": f"Campaign_{i}", "budget": 1000, "projected_revenue": 2500}
        for i in range(50)
    ]
}


# ══════════════════════════════════════════════════════════
#  TEST RUNNER
# ══════════════════════════════════════════════════════════

class TestResult:
    def __init__(self, name, category, passed, details, duration_ms, response=None):
        self.name = name
        self.category = category
        self.passed = passed
        self.details = details
        self.duration_ms = duration_ms
        self.response = response

    def to_dict(self):
        d = {
            "test_name": self.name,
            "category": self.category,
            "passed": self.passed,
            "details": self.details,
            "duration_ms": round(self.duration_ms, 1),
        }
        if self.response and not self.passed:
            d["response_preview"] = str(self.response)[:300]
        return d


async def post_webhook(session, payload, timeout=30):
    """Send a POST to the CFO webhook and return (status, body, elapsed_ms)."""
    start = time.time()
    try:
        async with session.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as r:
            elapsed = (time.time() - start) * 1000
            text = await r.text()
            try:
                body = json.loads(text) if text.strip() else {}
            except Exception:
                body = {"_raw": text[:300]}
            return r.status, body, elapsed
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return 0, {"_error": str(e)[:200]}, elapsed


async def run_all_tests():
    results = []
    start_time = time.time()

    print(f"\n{'='*70}")
    print(f"  PHANTOM QA ELITE — Test Suite: {AGENT_NAME}")
    print(f"  Target: {WEBHOOK_URL}")
    print(f"{'='*70}\n")

    async with aiohttp.ClientSession() as session:

        # ────────────────────────────────────────────────────
        # CATEGORY 1: Valid Payload — Full Pipeline
        # ────────────────────────────────────────────────────
        print("  [1/6] VALID PAYLOAD — Full Pipeline")
        status, body, ms = await post_webhook(session, VALID_PAYLOAD)
        t = TestResult(
            "Valid payload returns 200", "valid_payload",
            status == 200, f"Status: {status}", ms, body
        )
        results.append(t)
        print(f"    {'PASS' if t.passed else 'FAIL'} {t.name} ({ms:.0f}ms)")

        # Verify response structure
        if body.get("agent") == "CFO":
            results.append(TestResult("Agent field is 'CFO'", "valid_payload", True, "OK", 0))
            print(f"    PASS Agent field is 'CFO'")
        else:
            results.append(TestResult("Agent field is 'CFO'", "valid_payload", False, f"Got: {body.get('agent')}", 0, body))
            print(f"    FAIL Agent field is 'CFO' (got {body.get('agent')})")

        report = body.get("report", {})
        checks = [
            ("fragility_index", 18.4, "Fragility Index = 100 - 81.6 = 18.4"),
            ("composite_score", 81.6, "Composite matches input"),
            ("portfolio_roi_pct", 148.57, "ROI = (87000-35000)/35000*100"),
            ("total_spend", 35000, "Sum of budgets"),
            ("total_revenue", 87000, "Sum of revenues"),
            ("spend_utilization_pct", 84.0, "42000/50000*100"),
            ("unallocated", 8000.0, "50000-42000"),
            ("campaign_count", 3, "Three campaigns"),
        ]
        for field, expected, desc in checks:
            actual = report.get(field)
            passed = actual == expected
            t = TestResult(
                f"Report.{field} = {expected}", "data_integrity",
                passed, f"Expected {expected}, got {actual}. {desc}", 0
            )
            results.append(t)
            icon = "PASS" if passed else "FAIL"
            print(f"    {icon} {field}: {actual} (expected {expected})")

        # Check file naming convention
        fname = body.get("file_name", "")
        has_correct_name = fname.startswith("WarRoom_CFO_Report_")
        t = TestResult(
            "File naming: WarRoom_CFO_Report_[TS].xlsx", "valid_payload",
            has_correct_name, f"Got: {fname}", 0
        )
        results.append(t)
        print(f"    {'PASS' if has_correct_name else 'FAIL'} File naming: {fname}")

        # Check campaigns analysis
        campaigns = report.get("campaigns", [])
        if len(campaigns) == 3:
            c0 = campaigns[0]
            roi_check = c0.get("roi_pct") == 200.0
            t = TestResult(
                "Q2 Launch ROI = 200%", "data_integrity",
                roi_check, f"(45000-15000)/15000*100 = 200. Got: {c0.get('roi_pct')}", 0
            )
            results.append(t)
            print(f"    {'PASS' if roi_check else 'FAIL'} Q2 Launch ROI: {c0.get('roi_pct')}%")

        # ────────────────────────────────────────────────────
        # CATEGORY 2: Gatekeeper — Missing Fields
        # ────────────────────────────────────────────────────
        print(f"\n  [2/6] GATEKEEPER — Missing Field Validation")

        missing_tests = [
            ({}, "Empty payload", ["cmo_spend", "architect_risk", "campaign_list"]),
            ({"cmo_spend": {}}, "Only cmo_spend", ["architect_risk", "campaign_list"]),
            ({"architect_risk": {}}, "Only architect_risk", ["cmo_spend", "campaign_list"]),
            ({"campaign_list": []}, "Only campaign_list", ["cmo_spend", "architect_risk"]),
            ({"cmo_spend": {}, "architect_risk": {}}, "Missing campaign_list", ["campaign_list"]),
        ]

        for payload, desc, expected_missing in missing_tests:
            status, body, ms = await post_webhook(session, payload, timeout=10)
            passed = status == 400
            actual_missing = body.get("missing_fields", [])
            fields_match = set(actual_missing) == set(expected_missing)

            t = TestResult(
                f"Gatekeeper: {desc} → 400", "gatekeeper",
                passed and fields_match,
                f"Status: {status}, missing: {actual_missing}", ms, body
            )
            results.append(t)
            icon = "PASS" if t.passed else "FAIL"
            print(f"    {icon} {desc}: status={status}, missing={actual_missing}")

        # ────────────────────────────────────────────────────
        # CATEGORY 3: Math Safety — Edge Values
        # ────────────────────────────────────────────────────
        print(f"\n  [3/6] MATH SAFETY — Edge Values")

        edge_tests = [
            (ZERO_EVERYTHING, "All zeros (div-by-zero guard)"),
            (NEGATIVE_VALUES, "Negative values"),
            (SINGLE_CAMPAIGN, "Single campaign (100% composite)"),
            (HUGE_CAMPAIGN_LIST, "50 campaigns (large dataset)"),
        ]

        for payload, desc in edge_tests:
            status, body, ms = await post_webhook(session, payload)
            # Should return 200 (processed) or 422 (caught math error)
            passed = status in (200, 422)
            t = TestResult(
                f"Math Safety: {desc}", "math_safety",
                passed, f"Status: {status}", ms, body
            )
            results.append(t)
            icon = "PASS" if passed else "FAIL"
            print(f"    {icon} {desc}: status={status} ({ms:.0f}ms)")

        # ────────────────────────────────────────────────────
        # CATEGORY 4: Malformed Input
        # ────────────────────────────────────────────────────
        print(f"\n  [4/6] MALFORMED INPUT — Bad Data Types")

        malformed_tests = [
            ({"cmo_spend": "not_a_dict", "architect_risk": {}, "campaign_list": []},
             "cmo_spend as string"),
            ({"cmo_spend": {}, "architect_risk": {}, "campaign_list": "not_a_list"},
             "campaign_list as string"),
            ({"cmo_spend": {"total": "abc"}, "architect_risk": {}, "campaign_list": []},
             "Non-numeric total"),
        ]

        for payload, desc in malformed_tests:
            status, body, ms = await post_webhook(session, payload)
            # Should not return 500 (crash)
            passed = status != 500
            t = TestResult(
                f"Malformed: {desc}", "malformed_input",
                passed, f"Status: {status} (no 500 crash)", ms, body
            )
            results.append(t)
            icon = "PASS" if passed else "FAIL"
            print(f"    {icon} {desc}: status={status}")

        # ────────────────────────────────────────────────────
        # CATEGORY 5: Schema Validation
        # ────────────────────────────────────────────────────
        print(f"\n  [5/6] SCHEMA VALIDATION — Report Structure")

        # Re-use the valid payload response's report
        schema = report.get("schema", [])
        expected_schema = ["Dashboard", "Calculation Engine", "Input Data", "Campaign Analysis"]
        schema_match = schema == expected_schema
        t = TestResult(
            "Report schema has 4 tabs", "schema",
            schema_match, f"Expected {expected_schema}, got {schema}", 0
        )
        results.append(t)
        print(f"    {'PASS' if schema_match else 'FAIL'} Schema: {schema}")

        formula_map = report.get("formula_map", {})
        has_formulas = len(formula_map) >= 7
        t = TestResult(
            "Formula map has 7+ formulas", "schema",
            has_formulas, f"Got {len(formula_map)} formulas", 0
        )
        results.append(t)
        print(f"    {'PASS' if has_formulas else 'FAIL'} Formula count: {len(formula_map)}")

        # ────────────────────────────────────────────────────
        # CATEGORY 6: Stress Test — Concurrent Requests
        # ────────────────────────────────────────────────────
        print(f"\n  [6/6] STRESS TEST — 5 Concurrent Requests")

        async def fire_one():
            s, b, m = await post_webhook(session, VALID_PAYLOAD, timeout=30)
            return s

        tasks = [fire_one() for _ in range(5)]
        stress_start = time.time()
        stress_results = await asyncio.gather(*tasks)
        stress_elapsed = (time.time() - stress_start) * 1000

        success_count = sum(1 for s in stress_results if s == 200)
        passed = success_count == 5
        t = TestResult(
            f"5-concurrent webhook stress", "stress",
            passed,
            f"{success_count}/5 succeeded in {stress_elapsed:.0f}ms. Statuses: {stress_results}",
            stress_elapsed
        )
        results.append(t)
        icon = "PASS" if passed else "FAIL"
        print(f"    {icon} {success_count}/5 succeeded ({stress_elapsed:.0f}ms)")

    # ══════════════════════════════════════════════════════════
    #  FINAL VERDICT
    # ══════════════════════════════════════════════════════════

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    score = round(passed / total * 100) if total > 0 else 0
    elapsed = time.time() - start_time

    if score >= 80:
        verdict = "PASS"
    elif score >= 50:
        verdict = "WARN"
    else:
        verdict = "FAIL"

    print(f"\n{'='*70}")
    print(f"  PHANTOM QA ELITE — VERDICT: {verdict}")
    print(f"  Score: {score}/100 | Passed: {passed}/{total} | Failed: {failed}")
    print(f"  Duration: {elapsed:.1f}s")
    print(f"  Agent: {AGENT_NAME}")
    print(f"{'='*70}")

    if failed > 0:
        print(f"\n  Failed Tests:")
        for r in results:
            if not r.passed:
                print(f"    X {r.name}: {r.details}")

    # ── Atomizer-compatible report ────────────────────────
    report_data = {
        "agent": "Phantom_QA_Elite",
        "target": AGENT_NAME,
        "target_url": WEBHOOK_URL,
        "verdict": verdict,
        "score": score,
        "total_tests": total,
        "passed": passed,
        "failed": failed,
        "duration_seconds": round(elapsed, 1),
        "results": [r.to_dict() for r in results],
        "repair_payloads": [
            {
                "test_id": r.name.replace(" ", "_"),
                "agent": "Skeptic",
                "verdict": "FAIL",
                "target_url": WEBHOOK_URL,
                "issue": r.details,
                "repair_instruction": f"Fix: {r.name} — {r.details}",
            }
            for r in results if not r.passed
        ],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    # Save report
    report_path = f"reports/phantom_qa_cfo_fragility_{time.strftime('%Y%m%d_%H%M%S')}.json"
    import os
    os.makedirs("reports", exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2)
    print(f"\n  Report saved: {report_path}\n")

    return report_data


if __name__ == "__main__":
    asyncio.run(run_all_tests())
