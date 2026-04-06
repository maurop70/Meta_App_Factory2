"""
cpo_agent.py — Phase 9: Chief Product Officer (Tri-Node Architecture)
═════════════════════════════════════════════════════════════════════
Executes the Empathy Engine, Commercial Strategist, and MVP Butcher
in a single Chain-of-Thought (CoT) LLM call mapped to the CPOHandoff
Pydantic schema to eliminate latency and save tokens.
"""

import os
import json
import logging
import requests
from typing import Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'), override=True)
except ImportError:
    pass

from warroom_protocol import CPOHandoff
from factory_stream import get_secret
from auto_heal import healed_post

logger = logging.getLogger("CPO_Agent")


def _execute_empathy_engine() -> str:
    """Node 1: User Empathy Engine Context Builder"""
    return (
        "## NODE 1: User Empathy Engine\n"
        "You must aggressively hunt for friction points in the proposed architecture.\n"
        "- Enforce a strict 'Zero-Friction' UI mandate for the user.\n"
        "- Identify any steps that cause cognitive load or delay.\n"
        "- Output your findings into the `friction_elimination_notes` schema field first.\n"
    )

def _execute_commercial_strategist() -> str:
    """Node 2: Commercial Strategist Context Builder"""
    return (
        "## NODE 2: Commercial Strategist\n"
        "You must demand a clear Value Capture mechanism to ensure survival against well-funded competitors.\n"
        "- How does this product make money while remaining competitive?\n"
        "- What is the immediate commercial moat?\n"
        "- Output your monetization strategy into the `value_capture_mechanism` schema field second.\n"
        "- Provide a `commercial_viability_score` (1-10).\n"
    )

def _execute_mvp_butcher() -> str:
    """Node 3: MVP Butcher Context Builder"""
    return (
        "## NODE 3: The MVP Butcher\n"
        "Synthesize the UX demands (Node 1) and Commercial needs (Node 2) against the CTO's technical constraints.\n"
        "- Produce a ruthless MoSCoW matrix.\n"
        "- You must cut ANY feature that jeopardizes the launch timeline.\n"
        "- Output your final cut into `cut_features`.\n"
        "- Output critical launch features into `moscow_must_haves`.\n"
        "- Output competitive differentiators into `moscow_should_haves`.\n"
    )

def run_cpo(prompt: str) -> str:
    """
    Executes the CPO evaluation using a forced Chain-of-Thought approach.
    Takes the prompt state from the War Room orchestrator.
    Returns a strict JSON string matching CPOHandoff.
    """
    logger.info("[CPO] Executing Tri-Node Multi-Agent Cluster constraints.")
    
    # 1. Build the massive system instruction
    system_instruction = (
        "You are the acting Chief Product Officer (CPO) for the War Room. "
        "You will evaluate the current state using a Tri-Node execution model:\n\n"
        f"{_execute_empathy_engine()}\n"
        f"{_execute_commercial_strategist()}\n"
        f"{_execute_mvp_butcher()}\n\n"
        "CRITICAL INSTRUCTION: You MUST output YOUR ENTIRE RESPONSE as a single VALID JSON object. "
        "Do NOT include markdown fences (```json or ```). "
        "Your chronological JSON output MUST strictly match the following schema:\n"
        f"{json.dumps(CPOHandoff.model_json_schema(), indent=2)}\n\n"
        "Wait for the user's TOPIC prompt, then begin your chronological JSON evaluation."
    )
    
    import google.generativeai as genai
    
    # strict native execution priority
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        api_key = get_secret("GEMINI_API_KEY")

    if not api_key:
        logger.error("[CPO] GEMINI_API_KEY not found.")
        return json.dumps({"error": "GEMINI_API_KEY missing from vault/env."})
        
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_instruction
        )
        
        response = model.generate_content(
            f"TOPIC/STATE: {prompt}",
            generation_config=genai.GenerationConfig(
                temperature=0.4,
                response_mime_type="application/json"
            )
        )
        
        content_text = response.text
        # Validate Pydantic Handoff strictly before returning
        validated_handoff = CPOHandoff.model_validate_json(content_text)
        return validated_handoff.model_dump_json(indent=2)
        
    except Exception as e:
        logger.error(f"[CPO] Tri-Node execution failed (SDK): {str(e)}")
        # Construct fallback safely
        fallback = CPOHandoff(
            friction_elimination_notes=[f"Execution fault: {str(e)}"],
            value_capture_mechanism="HALTED DUE TO ERROR",
            commercial_viability_score=1.0,
            cut_features=["ALL"],
            moscow_must_haves=[],
            moscow_should_haves=[]
        )
        return fallback.model_dump_json(indent=2)

if __name__ == "__main__":
    # Test harness
    print("Testing Tri-Node CPO Execution...")
    try:
        out = run_cpo("We are building a new cross-chain swap protocol against a $10M funded competitor. Active-active Redis proposed.")
        print(out)
    except Exception as ex:
        print(f"Error: {ex}")
