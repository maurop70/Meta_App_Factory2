"""
logic_checker.py — Semantic Critic + Hallucination Gate
═════════════════════════════════════════════════════════
Two-layer evaluation:

  Layer 1 — Hallucination Gate (UDPP)
    Runs first if agent_provenance_block is supplied.
    Fails immediately if any agent provided uncited claims or mock data.

  Layer 2 — CEO Strategy Gate (Gemini semantic eval)
    Evaluates the CEO's synthesis narrative for strategic coherence.
    Model waterfall: gemini-2.5-pro → gemini-2.5-flash on 503/UNAVAILABLE.
"""

import os
import json
from google import genai
from ai_utils import generate_with_backoff_sync
from agent_base import run_hallucination_gate


def evaluate_logic(ceo_synthesis: str, agent_provenance_block: dict = None) -> dict:
    """
    Evaluates the War Room pipeline output for logic and data integrity.

    Args:
        ceo_synthesis:          The CEO's final strategy narrative text.
        agent_provenance_block: Optional dict of { "CMO": {...}, "CTO": {...} }
                                provenance sidecars from CMO/CTO agents.
                                If provided, the Hallucination Gate runs first.

    Returns:
        { "status": "PASS" | "FAIL", "errors": [...], "gate_triggered": str }
    """
    if not ceo_synthesis or "No response" in ceo_synthesis:
        return {
            "status": "FAIL",
            "errors": ["CEO Synthesis is missing or empty."],
            "gate_triggered": "pre_check",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # LAYER 1 — HALLUCINATION GATE (UDPP)
    # Runs before the Gemini semantic eval. If provenance is dirty, fail fast.
    # ─────────────────────────────────────────────────────────────────────────
    if agent_provenance_block:
        gate_status, gate_errors = run_hallucination_gate(agent_provenance_block)
        if gate_status == "FAIL":
            return {
                "status": "FAIL",
                "errors": gate_errors,
                "gate_triggered": "hallucination_gate",
            }

    # ─────────────────────────────────────────────────────────────────────────
    # LAYER 2 — CEO STRATEGY GATE (Gemini semantic evaluation)
    # ─────────────────────────────────────────────────────────────────────────
    prompt = f"""You are the Critic (QA Agent) for the Aether C-Suite War Room.
Your job is to read the CEO's Synthesis and determine if the strategic pipeline should PASS or FAIL.

CEO SYNTHESIS:
\"\"\"
{ceo_synthesis}
\"\"\"

EVALUATION RULES:
1. If the CEO explicitly HALTS, REJECTS, or places the pivot "on hold", you must FAIL.
2. If the CEO identifies a "total communications failure", "critical vulnerability", or major internal contradiction across the departments (CTO, CMO, CFO), you must FAIL.
3. If the CEO authorizes the deployment or indicates the strategy is successfully unified and ready, you must PASS.

Respond in strict JSON format:
{{
    "status": "PASS" or "FAIL",
    "errors": ["List of critical contradictions or reasons for failure, if any"]
}}
"""

    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return {
                "status": "FAIL",
                "errors": ["GEMINI_API_KEY is missing from environment."],
                "gate_triggered": "api_key_missing",
            }

        client = genai.Client(api_key=api_key)

        # Model waterfall: pro → flash on 503/UNAVAILABLE
        models_to_try = ["gemini-2.5-pro", "gemini-2.5-flash"]
        last_error = None

        for model_name in models_to_try:
            try:
                response = generate_with_backoff_sync(
                    client.models.generate_content,
                    model=model_name,
                    contents=prompt,
                )
                raw_text = response.text.replace("```json", "").replace("```", "").strip()
                data = json.loads(raw_text)
                return {
                    "status": data.get("status", "FAIL"),
                    "errors": data.get("errors", []),
                    "gate_triggered": "ceo_strategy_gate",
                    "model_used": model_name,
                }
            except Exception as model_err:
                err_str = str(model_err)
                if "503" in err_str or "UNAVAILABLE" in err_str or "demand" in err_str.lower():
                    last_error = f"[{model_name} exhausted all retries, trying fallback model]"
                    continue
                # Non-availability error — fail with details
                return {
                    "status": "FAIL",
                    "errors": [f"Critic AI evaluation failed: {err_str}"],
                    "gate_triggered": "ceo_strategy_gate",
                }

        return {
            "status": "FAIL",
            "errors": [f"All Critic models unavailable. Last error: {last_error}"],
            "gate_triggered": "ceo_strategy_gate",
        }

    except Exception as e:
        return {
            "status": "FAIL",
            "errors": [f"Critic AI evaluation failed: {str(e)}"],
            "gate_triggered": "ceo_strategy_gate",
        }
