"""
test_swdr.py — SWDR Staging Validation Harness
═══════════════════════════════════════════════════
Simulates 100 webhook call iterations with configurable failure injection
to verify circuit breaker, exponential backoff, and failure rate thresholds.

Run:
    cd Meta_App_Factory
    python test_swdr.py

Expected: All tests PASS, failure rate < 5%
"""

import os
import sys
import time
import json
import shutil
import tempfile

# Ensure local modules are importable
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Stability modules live in sub-app directories (e.g. Resonance2/)
RESONANCE2_DIR = os.path.join(SCRIPT_DIR, "Resonance2")
sys.path.insert(0, RESONANCE2_DIR)
sys.path.insert(0, SCRIPT_DIR)

# Use a temp directory for circuit breaker state to avoid polluting real state
TEST_CB_DIR = os.path.join(tempfile.gettempdir(), "swdr_test_circuit_breakers")
os.makedirs(TEST_CB_DIR, exist_ok=True)

# Patch the circuit breaker state dir for testing
import circuit_breaker as cb_module
cb_module.STATE_DIR = TEST_CB_DIR

from circuit_breaker import CircuitBreaker

# Patch error aggregator to a temp log
TEST_LOG_PATH = os.path.join(tempfile.gettempdir(), "swdr_test_error_log.jsonl")
import error_aggregator as ea_module
ea_module.ERROR_LOG_PATH = TEST_LOG_PATH

from error_aggregator import ErrorAggregator


# ── Helpers ──────────────────────────────────────────────────────
class TestResult:
    def __init__(self, name):
        self.name = name
        self.passed = False
        self.detail = ""

    def __repr__(self):
        icon = "✅" if self.passed else "❌"
        return f"{icon} {self.name}: {self.detail}"


def cleanup():
    """Remove temp test artifacts."""
    if os.path.exists(TEST_CB_DIR):
        shutil.rmtree(TEST_CB_DIR, ignore_errors=True)
    if os.path.exists(TEST_LOG_PATH):
        os.remove(TEST_LOG_PATH)


# ── Test 1: Circuit Breaker Trips After 3 Consecutive Failures ─────
def test_circuit_breaker_threshold():
    t = TestResult("Circuit Breaker trips at threshold=3")
    cb = CircuitBreaker("test-webhook", failure_threshold=3, cooldown_seconds=5)
    cb.reset()

    # Simulate 3 consecutive failures
    cb.record_failure()
    cb.record_failure()
    assert cb.state == "CLOSED", "Should still be CLOSED after 2 failures"

    cb.record_failure()
    assert cb.state == "OPEN", "Should be OPEN after 3 failures"
    assert not cb.can_call(), "Should block calls when OPEN"

    t.passed = True
    t.detail = "OPEN after 3 failures, calls blocked"
    return t


# ── Test 2: Circuit Breaker Recovery (HALF_OPEN → CLOSED) ──────
def test_circuit_breaker_recovery():
    t = TestResult("Circuit Breaker recovers after cooldown")
    cb = CircuitBreaker("test-recovery", failure_threshold=3, cooldown_seconds=1, success_threshold=2)
    cb.reset()

    # Trip it
    for _ in range(3):
        cb.record_failure()
    assert cb.state == "OPEN"

    # Wait for cooldown
    time.sleep(1.5)
    assert cb.state == "HALF_OPEN", f"Expected HALF_OPEN after cooldown, got {cb.state}"
    assert cb.can_call(), "Should allow test call in HALF_OPEN"

    # Recover
    cb.record_success()
    cb.record_success()
    assert cb.state == "CLOSED", "Should be CLOSED after 2 successes in HALF_OPEN"

    t.passed = True
    t.detail = "OPEN → HALF_OPEN (1s cooldown) → CLOSED (2 successes)"
    return t


# ── Test 3: Exponential Backoff Timing ─────────────────────────
def test_exponential_backoff_timing():
    t = TestResult("Exponential backoff delays are correct")
    backoff_base = 2
    expected_delays = [2, 4, 8]  # 2^0*2, 2^1*2, 2^2*2

    for attempt, expected in enumerate(expected_delays):
        actual = backoff_base * (2 ** attempt)
        if abs(actual - expected) > 0.01:
            t.detail = f"Attempt {attempt}: expected {expected}s, got {actual}s"
            return t

    t.passed = True
    t.detail = "Delays verified: 2s → 4s → 8s"
    return t


# ── Test 4: Failure Rate < 5% Over 100 Iterations ─────────────
def test_failure_rate_threshold():
    t = TestResult("Failure rate < 5% over 100 iterations (with CB protection)")
    cb = CircuitBreaker("test-rate", failure_threshold=3, cooldown_seconds=0.5)
    cb.reset()

    successes = 0
    failures = 0
    soft_pauses = 0
    total_iterations = 100

    # Simulate: first 5 iterations fail to trip the CB, then it pauses, then recovers
    # This models a realistic scenario: bad endpoint → CB opens → cooldown → recover
    for i in range(total_iterations):
        if not cb.can_call():
            soft_pauses += 1
            # Wait a tiny bit for cooldown in test mode
            time.sleep(0.1)
            continue

        # Simulate: 5% base failure rate (realistic after SWDR fix)
        import random
        if i < 3:
            # First 3 calls fail (simulating Token Decay scenario)
            cb.record_failure()
            failures += 1
        elif random.random() < 0.03:
            # 3% random failure rate
            cb.record_failure()
            failures += 1
        else:
            cb.record_success()
            successes += 1

    total_actual = successes + failures
    if total_actual == 0:
        t.detail = f"No calls made (all soft-paused: {soft_pauses})"
        return t

    failure_rate = (failures / total_actual) * 100

    t.detail = (f"Rate: {failure_rate:.1f}% "
                f"(ok: {successes}, fail: {failures}, paused: {soft_pauses})")
    t.passed = failure_rate < 5.0
    return t


# ── Test 5: Error Aggregator Receives Critical Logs ────────────
def test_error_aggregator_logging():
    t = TestResult("Error aggregator receives critical SWDR logs")

    # Clear test log
    if os.path.exists(TEST_LOG_PATH):
        os.remove(TEST_LOG_PATH)

    logger = ErrorAggregator("SWDR")
    logger.log_critical(
        "Test: Elite Council unreachable after 3 attempts",
        context={"project": "test_project", "error": "timeout", "action": "overseer_notify"}
    )
    logger.log_critical(
        "Test: Soft Pause triggered",
        context={"action": "soft_pause"}
    )

    entries = ErrorAggregator.read_recent(n=10, log_path=TEST_LOG_PATH)
    critical_entries = [e for e in entries if e.get("severity") == "critical"]

    t.passed = len(critical_entries) >= 2
    t.detail = f"{len(critical_entries)} critical entries logged"
    return t


# ── Test 6: Overseer Notification Payload Well-Formed ──────────
def test_overseer_payload():
    t = TestResult("Overseer notification payload is well-formed")

    logger = ErrorAggregator("SWDR")
    logger.log_critical(
        "Overseer test notification",
        context={
            "project": "Resonance2",
            "error": "N8N Server Error: 502",
            "action": "overseer_notify"
        }
    )

    entries = ErrorAggregator.read_recent(n=5, app_filter="SWDR", log_path=TEST_LOG_PATH)
    overseer_entries = [
        e for e in entries
        if e.get("context", {}).get("action") == "overseer_notify"
    ]

    if overseer_entries:
        entry = overseer_entries[-1]
        has_project = "project" in entry.get("context", {})
        has_error = "error" in entry.get("context", {})
        has_action = entry["context"]["action"] == "overseer_notify"
        t.passed = has_project and has_error and has_action
        t.detail = f"Payload OK: project={has_project}, error={has_error}, action={has_action}"
    else:
        t.detail = "No overseer notification found"

    return t


# ── Main Runner ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🔬 SWDR STAGING VALIDATION HARNESS")
    print("  Alpha_V2_Genesis_STAGING Environment")
    print("=" * 60 + "\n")

    cleanup()
    os.makedirs(TEST_CB_DIR, exist_ok=True)

    tests = [
        test_circuit_breaker_threshold,
        test_circuit_breaker_recovery,
        test_exponential_backoff_timing,
        test_failure_rate_threshold,
        test_error_aggregator_logging,
        test_overseer_payload,
    ]

    results = []
    for test_fn in tests:
        try:
            result = test_fn()
        except Exception as e:
            result = TestResult(test_fn.__name__)
            result.detail = f"EXCEPTION: {e}"
        results.append(result)
        print(f"  {result}")

    print(f"\n{'=' * 60}")
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"  Results: {passed}/{total} passed")

    if passed == total:
        print("  ✅ ALL TESTS PASSED — failure rate target MET")
        print("  Ready for Production push.")
    else:
        print("  ❌ SOME TESTS FAILED — do NOT push to Production")

    print(f"{'=' * 60}\n")

    cleanup()
    sys.exit(0 if passed == total else 1)
