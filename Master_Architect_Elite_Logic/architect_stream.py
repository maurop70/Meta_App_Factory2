"""
architect_stream.py — SSE Streaming Bridge
════════════════════════════════════════════
Master_Architect_Elite_Logic | Meta App Factory

Provides SSE (Server-Sent Events) streaming for real-time
Triad reviews via the Gemini API. Used by /api/review/stream.
"""

import json
import logging

logger = logging.getLogger("ArchitectStream")


def stream_triad_review(triad_engine, description: str,
                        change_type: str = "feature",
                        components: list = None,
                        context: dict = None):
    """
    Generator that yields SSE-formatted events as the Triad review
    progresses. Each event is a JSON dict:

      {"step": "TRIAD_START|AGENT_*|TRIAD_VERDICT|GATE_*", "text": "...", ...}

    Usage:
        from architect_stream import stream_triad_review

        def generate():
            for event in stream_triad_review(engine, desc):
                yield f"data: {json.dumps(event)}\\n\\n"
        return StreamingResponse(generate(), media_type="text/event-stream")
    """
    from adversarial_gate import AdversarialGate

    # Phase 1: Triad Review (streaming)
    verdict_dict = None
    for event in triad_engine.review_streaming(
        description, change_type, components or [], context or {}
    ):
        if event.get("step") == "TRIAD_VERDICT":
            verdict_dict = event.get("verdict", {})
        yield event

    if not verdict_dict:
        yield {
            "step": "ERROR",
            "text": "Triad review produced no verdict.",
        }
        return

    # Phase 2: Adversarial Gate
    yield {
        "step": "GATE_START",
        "text": "🏛️ Adversarial Gate: Evaluating architecture...",
    }

    gate = AdversarialGate()
    gate_result = gate.evaluate(verdict_dict)
    gate_status = gate_result.get("gate_result", "UNKNOWN")

    if gate_status == "AUTO_APPROVE":
        # Store as approved pattern
        try:
            triad_engine.memory.store_pattern({
                "domain": "composite",
                "category": _classify_category(description),
                "pattern": description[:100],
                "rationale": f"Auto-approved with score {verdict_dict.get('composite_score')}",
                "technologies": components or [],
                "triad_score": verdict_dict.get("composite_score", 0),
            }, gate_status="approved")
        except Exception as e:
            logger.warning(f"Pattern storage failed: {e}")

        yield {
            "step": "GATE_RESULT",
            "text": f"✅ Auto-Approved (Score: {verdict_dict.get('composite_score', 0)}/100)",
            "gate": gate_result,
        }

    elif gate_status == "CHALLENGED":
        yield {
            "step": "GATE_CHALLENGE",
            "text": (
                f"⚠️ Architecture Challenged — Score {verdict_dict.get('composite_score', 0)}/100 "
                f"(threshold: {gate.AUTO_APPROVE_THRESHOLD})"
            ),
            "gate": gate_result,
            "challenge_id": gate_result.get("challenge_id"),
            "weaknesses": gate_result.get("weaknesses", []),
        }

    else:  # REJECTED
        yield {
            "step": "GATE_REJECTED",
            "text": f"❌ Architecture Rejected (Score: {verdict_dict.get('composite_score', 0)}/100)",
            "gate": gate_result,
        }

    yield {
        "step": "COMPLETE",
        "text": "Review complete.",
        "final_verdict": verdict_dict,
        "gate_status": gate_status,
    }


def _classify_category(description: str) -> str:
    """Simple keyword-based category classification."""
    desc_lower = description.lower()
    categories = {
        "api": ["api", "endpoint", "rest", "route", "fastapi"],
        "dashboard": ["dashboard", "ui", "frontend", "page", "component"],
        "pipeline": ["pipeline", "workflow", "n8n", "automation"],
        "agent": ["agent", "ai", "gemini", "model", "llm"],
        "database": ["database", "schema", "table", "migration", "sql"],
        "security": ["security", "auth", "credential", "vault", "pii"],
        "infrastructure": ["deploy", "docker", "port", "server", "launch"],
    }
    for cat, keywords in categories.items():
        if any(kw in desc_lower for kw in keywords):
            return cat
    return "general"
