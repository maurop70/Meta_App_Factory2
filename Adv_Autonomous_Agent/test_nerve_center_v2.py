"""
Test Suite — Nerve Center v2.0 Self-Rectification Engine
==========================================================
Validates the full SCAN → ANALYZE → RECTIFY → ACT → LEARN → LOG pipeline
using simulated error payloads (no live n8n API calls).

Test Scenarios:
    1. Known errors are diagnosed correctly via seeded tree (backward compat)
    2. Unknown errors trigger rectification and grafting
    3. Learning pipeline promotes successful rectifications
    4. Learning pipeline demotes failed rectifications
    5. Reasoning tree persists and reloads correctly
    6. Full NerveCenterV2 pipeline end-to-end
"""

import os
import sys
import json
import shutil
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from self_rectification_engine import (
    SelfRectificationEngine,
    ReasoningTree,
    LearningPipeline,
    ReasoningNode,
    STATE_DIR as DEFAULT_STATE_DIR,
)
from nerve_center_v2 import NerveCenterV2

# ── Test Configuration ──────────────────────────────────────
TEST_STATE_DIR = os.path.join(SCRIPT_DIR, ".test_nerve_v2_state")

# Counters
_pass = 0
_fail = 0


def _assert(condition: bool, label: str, detail: str = ""):
    global _pass, _fail
    if condition:
        _pass += 1
        print(f"  ✅ PASS: {label}")
    else:
        _fail += 1
        msg = f"  ❌ FAIL: {label}"
        if detail:
            msg += f" — {detail}"
        print(msg)


def cleanup():
    """Remove test state directory."""
    if os.path.exists(TEST_STATE_DIR):
        shutil.rmtree(TEST_STATE_DIR, ignore_errors=True)


# ══════════════════════════════════════════════════════════════
#  TEST 1: Known Error Classification (Backward Compatibility)
# ══════════════════════════════════════════════════════════════

def test_known_error_classification():
    """Verify that v1.0 seed patterns are correctly classified."""
    print(f"\n{'─'*55}")
    print(f"  TEST 1: Known Error Classification")
    print(f"{'─'*55}")

    engine = SelfRectificationEngine(state_dir=TEST_STATE_DIR)

    # Test AUTH_EXPIRED
    diag = engine.diagnose(
        error_text="HTTP 401 Unauthorized: invalid token for API endpoint",
        execution_id="TEST_AUTH_001",
        workflow_name="Auth_Test_Workflow",
    )
    _assert(diag["id"] == "AUTH_EXPIRED", "AUTH_EXPIRED detected", f"Got: {diag['id']}")
    _assert(diag["action"] == "refresh_credentials", "Correct action: refresh_credentials")
    _assert(diag["source"] == "seeded", "Source is 'seeded'")

    # Test GATEWAY_TIMEOUT
    diag = engine.diagnose(
        error_text="504 Gateway Timeout: upstream server did not respond",
        execution_id="TEST_GW_001",
        workflow_name="Gateway_Test_Workflow",
    )
    _assert(diag["id"] == "GATEWAY_TIMEOUT", "GATEWAY_TIMEOUT detected", f"Got: {diag['id']}")
    _assert(diag["action"] == "retry_with_backoff", "Correct action: retry_with_backoff")

    # Test RATE_LIMITED
    diag = engine.diagnose(
        error_text="429 Too Many Requests: rate limit exceeded for this API key",
        execution_id="TEST_RL_001",
        workflow_name="RateLimit_Test_Workflow",
    )
    _assert(diag["id"] == "RATE_LIMITED", "RATE_LIMITED detected", f"Got: {diag['id']}")

    # Test CONNECTION_REFUSED
    diag = engine.diagnose(
        error_text="ECONNREFUSED: Connection refused at 127.0.0.1:8080",
        execution_id="TEST_CONN_001",
        workflow_name="Connection_Test_Workflow",
    )
    _assert(diag["id"] == "CONNECTION_REFUSED", "CONNECTION_REFUSED detected", f"Got: {diag['id']}")

    # Test CIRCUIT_OPEN
    diag = engine.diagnose(
        error_text="Circuit breaker OPEN: cascade failure detected in downstream services",
        execution_id="TEST_CB_001",
        workflow_name="CircuitBreaker_Test_Workflow",
    )
    _assert(diag["id"] == "CIRCUIT_OPEN", "CIRCUIT_OPEN detected", f"Got: {diag['id']}")

    # Test MALFORMED_JSON
    diag = engine.diagnose(
        error_text="400 Bad Request: JSON parse error, Unexpected token at position 42",
        execution_id="TEST_JSON_001",
        workflow_name="JSON_Test_Workflow",
    )
    _assert(diag["id"] == "MALFORMED_JSON", "MALFORMED_JSON detected", f"Got: {diag['id']}")

    cleanup()


# ══════════════════════════════════════════════════════════════
#  TEST 2: Unknown Error → Rectification + Grafting
# ══════════════════════════════════════════════════════════════

def test_unknown_error_rectification():
    """Verify that unknown errors trigger rectification mode."""
    print(f"\n{'─'*55}")
    print(f"  TEST 2: Unknown Error Rectification")
    print(f"{'─'*55}")

    engine = SelfRectificationEngine(state_dir=TEST_STATE_DIR)

    # This error doesn't match any seeded pattern
    novel_error = (
        "KAFKA_CONSUMER_LAG: Consumer group 'analytics-pipeline' has accumulated "
        "15,000 unprocessed messages on partition 3 of topic 'user-events'. "
        "Broker at kafka-node-7.internal:9092 reports disk I/O saturation."
    )

    diag = engine.diagnose(
        error_text=novel_error,
        execution_id="TEST_NOVEL_001",
        workflow_name="Analytics_Pipeline",
    )

    _assert(diag["source"] == "rectified", "Source is 'rectified' (not seeded)")
    _assert(diag["id"].startswith("LEARNED_"), "Node ID starts with LEARNED_", f"Got: {diag['id']}")
    _assert(diag["confidence"] == 0.4, "Initial confidence is 0.4 (provisional)")
    _assert(len(diag.get("candidate_patterns", [])) > 0, "Candidate patterns generated")
    _assert(diag["action"] in [
        "retry_with_backoff", "retry_execution", "refresh_credentials", "log_for_review"
    ], "Valid action inferred")

    # Verify the node was grafted onto the tree
    tree_stats = engine.tree.get_stats()
    _assert(tree_stats["learned_nodes"] == 1, "One learned node in tree", f"Got: {tree_stats['learned_nodes']}")
    _assert(tree_stats["total_nodes"] == 11, "Total nodes = 10 seeded + ROOT + 1 learned", f"Got: {tree_stats['total_nodes']}")

    # Verify the node is findable in the tree
    learned_node = engine.tree.find_node(diag["id"])
    _assert(learned_node is not None, f"Learned node '{diag['id']}' found in tree")
    _assert(learned_node.learned is True, "Node is marked as learned")

    cleanup()


# ══════════════════════════════════════════════════════════════
#  TEST 3: Learning Pipeline — Promotion
# ══════════════════════════════════════════════════════════════

def test_learning_promotion():
    """Verify that successful rectifications boost confidence."""
    print(f"\n{'─'*55}")
    print(f"  TEST 3: Learning Pipeline — Promotion")
    print(f"{'─'*55}")

    engine = SelfRectificationEngine(state_dir=TEST_STATE_DIR)

    # Diagnose a genuinely novel error that won't match any seeded pattern
    # (No HTTP codes, no auth/timeout/rate keywords)
    diag = engine.diagnose(
        error_text="WASM_MEMORY_OOM: WebAssembly module 'analytics-core' exceeded linear memory ceiling at 4GB boundary during bulk aggregation of 2M row dataset",
        execution_id="TEST_PROMO_001",
        workflow_name="WASM_Analytics_Engine",
    )
    node_id = diag["id"]
    initial_confidence = diag["confidence"]
    _assert(diag["source"] == "rectified", "Source is 'rectified' (novel error)")
    _assert(initial_confidence == 0.4, "Initial confidence is 0.4")

    # Simulate successful outcome → PROMOTE
    result = engine.learn("TEST_PROMO_001", success=True)
    _assert(result is not None, "Learning result returned")
    _assert(result["action"] == "PROMOTED", "Learning action is PROMOTED")

    # Check that confidence was boosted
    node = engine.tree.find_node(node_id)
    _assert(node.confidence == 0.55, "Confidence boosted to 0.55 (0.4 + 0.15)", f"Got: {node.confidence}")
    _assert(node.success_count == 1, "Success count incremented to 1")
    _assert(node.match_count == 1, "Match count incremented to 1")

    # Verify learning ledger has an entry
    _assert(len(engine.pipeline.ledger) == 1, "Learning ledger has one entry")
    _assert(engine.pipeline.ledger[0]["success"] is True, "Ledger entry records success")

    cleanup()


# ══════════════════════════════════════════════════════════════
#  TEST 4: Learning Pipeline — Demotion
# ══════════════════════════════════════════════════════════════

def test_learning_demotion():
    """Verify that failed rectifications reduce confidence."""
    print(f"\n{'─'*55}")
    print(f"  TEST 4: Learning Pipeline — Demotion")
    print(f"{'─'*55}")

    engine = SelfRectificationEngine(state_dir=TEST_STATE_DIR)

    # Diagnose an unknown error
    diag = engine.diagnose(
        error_text="ZOOKEEPER_SESSION_EXPIRED: ZK session 0x1234abcd expired, ephemeral nodes deleted",
        execution_id="TEST_DEMO_001",
        workflow_name="Coordination_Service",
    )
    node_id = diag["id"]

    # Simulate failed outcome → DEMOTE
    result = engine.learn("TEST_DEMO_001", success=False)
    _assert(result is not None, "Learning result returned")
    _assert(result["action"] == "DEMOTED", "Learning action is DEMOTED")

    # Check that confidence was reduced
    node = engine.tree.find_node(node_id)
    _assert(node.confidence == 0.2, "Confidence reduced to 0.2 (0.4 - 0.2)", f"Got: {node.confidence}")

    # Demote again → should hit LOW_CONFIDENCE_REVIEW threshold
    diag2 = engine.diagnose(
        error_text="ZOOKEEPER_SESSION_EXPIRED: ZK session 0x5678efab expired again",
        execution_id="TEST_DEMO_002",
        workflow_name="Coordination_Service",
    )
    result2 = engine.learn("TEST_DEMO_002", success=False)
    if result2:
        _assert(
            result2.get("flag") == "LOW_CONFIDENCE_REVIEW",
            "Low confidence flag triggered",
            f"Flag: {result2.get('flag')}"
        )

    cleanup()


# ══════════════════════════════════════════════════════════════
#  TEST 5: Tree Persistence (Save → Load → Verify)
# ══════════════════════════════════════════════════════════════

def test_tree_persistence():
    """Verify that the reasoning tree and ledger persist correctly."""
    print(f"\n{'─'*55}")
    print(f"  TEST 5: Tree Persistence")
    print(f"{'─'*55}")

    # Create engine and learn a pattern
    engine1 = SelfRectificationEngine(state_dir=TEST_STATE_DIR)
    diag = engine1.diagnose(
        error_text="S3_BUCKET_ACCESS_DENIED: IAM role arn:aws:iam::123:role/data-reader lacks s3:GetObject permission",
        execution_id="TEST_PERSIST_001",
        workflow_name="Data_Lake_Ingestion",
    )
    engine1.learn("TEST_PERSIST_001", success=True)
    node_id = diag["id"]

    # Verify files were created
    tree_file = os.path.join(TEST_STATE_DIR, "reasoning_tree.json")
    ledger_file = os.path.join(TEST_STATE_DIR, "learning_ledger.json")
    _assert(os.path.exists(tree_file), "reasoning_tree.json exists on disk")
    _assert(os.path.exists(ledger_file), "learning_ledger.json exists on disk")

    # Create a NEW engine instance (should load from disk)
    engine2 = SelfRectificationEngine(state_dir=TEST_STATE_DIR)

    # Verify the learned node survived the reload
    reloaded_node = engine2.tree.find_node(node_id)
    _assert(reloaded_node is not None, "Learned node found after reload")
    _assert(reloaded_node.learned is True, "Node still marked as learned")
    _assert(reloaded_node.confidence == 0.55, "Confidence preserved (0.55)", f"Got: {reloaded_node.confidence}")
    _assert(reloaded_node.success_count == 1, "Success count preserved")

    # Verify ledger survived
    _assert(len(engine2.pipeline.ledger) == 1, "Learning ledger preserved")

    # Verify tree stats
    stats = engine2.tree.get_stats()
    _assert(stats["learned_nodes"] == 1, "Learned node count preserved")

    cleanup()


# ══════════════════════════════════════════════════════════════
#  TEST 6: Full NerveCenterV2 End-to-End Pipeline
# ══════════════════════════════════════════════════════════════

def test_full_pipeline():
    """Validate the complete 6-phase pipeline with mixed errors."""
    print(f"\n{'─'*55}")
    print(f"  TEST 6: Full NerveCenterV2 Pipeline (E2E)")
    print(f"{'─'*55}")

    # Temporarily override STATE_DIR for test isolation
    import self_rectification_engine as sre
    import nerve_center_v2 as ncv2
    original_state_dir = sre.STATE_DIR
    sre.STATE_DIR = TEST_STATE_DIR
    ncv2.STATE_DIR = TEST_STATE_DIR
    ncv2.STATE_FILE = os.path.join(TEST_STATE_DIR, "nerve_state_v2.json")

    nc = NerveCenterV2()
    nc.engine = SelfRectificationEngine(state_dir=TEST_STATE_DIR)

    # Inject a mix of known and unknown failures
    test_failures = [
        # Known: AUTH_EXPIRED
        {
            "id": "E2E_001",
            "status": "error",
            "workflowData": {"name": "User_Auth_Flow", "id": "wf_001"},
            "data": {
                "resultData": {
                    "error": {
                        "message": "401 Unauthorized: Token expired",
                        "description": "The auth token has expired."
                    },
                    "lastNodeExecuted": "Auth Check"
                }
            },
        },
        # Known: GATEWAY_TIMEOUT
        {
            "id": "E2E_002",
            "status": "error",
            "workflowData": {"name": "Payment_Processing", "id": "wf_002"},
            "data": {
                "resultData": {
                    "error": {
                        "message": "504 Gateway Timeout on payment gateway",
                        "description": "Upstream timeout."
                    },
                    "lastNodeExecuted": "Stripe Call"
                }
            },
        },
        # UNKNOWN: Should trigger rectification
        {
            "id": "E2E_003",
            "status": "error",
            "workflowData": {"name": "ML_Feature_Store", "id": "wf_003"},
            "data": {
                "resultData": {
                    "error": {
                        "message": "EMBEDDING_DIMENSION_MISMATCH: Vector dimensions 768 vs expected 1536 in collection 'product-embeddings'",
                        "description": "ChromaDB rejected the batch insert due to dimension mismatch."
                    },
                    "lastNodeExecuted": "Vector Upsert"
                }
            },
        },
    ]

    report = nc.scan_and_heal(injected_failures=test_failures)

    _assert(report["failures_found"] == 3, "3 failures processed")
    _assert(report["actions_taken"] == 3, "3 actions taken")
    _assert(report["healed"] >= 2, "At least 2 healed (known errors)", f"Got: {report['healed']}")
    _assert(report["rectified"] >= 1, "At least 1 rectified (unknown error)", f"Got: {report['rectified']}")

    # Check engine stats show the learned node
    stats = report.get("engine_stats", {})
    tree_stats = stats.get("tree", {})
    _assert(tree_stats.get("learned_nodes", 0) >= 1, "At least 1 learned node in tree stats")

    # Restore
    sre.STATE_DIR = original_state_dir
    ncv2.STATE_DIR = original_state_dir
    cleanup()


# ══════════════════════════════════════════════════════════════
#  TEST RUNNER
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n{'═'*60}")
    print(f"  🧪 NERVE CENTER v2.0 — Test Suite")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*60}")

    # Clean up before starting
    cleanup()

    try:
        test_known_error_classification()
        test_unknown_error_rectification()
        test_learning_promotion()
        test_learning_demotion()
        test_tree_persistence()
        test_full_pipeline()
    finally:
        cleanup()

    print(f"\n{'═'*60}")
    print(f"  🏁 TEST RESULTS: {_pass} passed, {_fail} failed")
    if _fail == 0:
        print(f"  ✅ ALL TESTS PASSED")
    else:
        print(f"  ❌ {_fail} TEST(S) FAILED")
    print(f"{'═'*60}\n")

    sys.exit(0 if _fail == 0 else 1)
