import os
import re
import httpx
import logging
import asyncio
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

logger = logging.getLogger(__name__)
venture_router = APIRouter(prefix="/api/v1/venture", tags=["Venture Architect Mode B"])

class ArtifactPayload(BaseModel):
    artifact_type: str
    content: str

# Lazy retrieval — this module is imported BEFORE api.py loads .env,
# so os.getenv at module scope would return None.
def _get_api_key() -> str | None:
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key.strip("'\"")
    return None

async def _async_agent_prompt(agent_role: str, artifact_payload: str) -> dict:
    """
    Natively asynchronous LLM network operation via httpx.
    Multiplexes Gemini inference without OS-level thread locks.
    """
    api_key = _get_api_key()
    if not api_key:
        logger.error("[SECURITY FATAL] GEMINI_API_KEY void detected in environment matrix.")
        raise HTTPException(status_code=500, detail="Cognitive engine disconnected. API key null.")


    logger.info(f"[{agent_role}] Initiating asynchronous cognitive inference...")

    # System instruction synthesis mapped to the agent persona
    system_prompt = (
        f"You are the {agent_role} of a high-growth technology startup. "
        "Analyze the following artifact strictly from your departmental perspective. "
        "Provide concise, brutal, and highly technical feedback. Do not use conversational filler."
    )

    if agent_role == "CRITIC":
        system_prompt += " You must strictly conclude your analysis with a persuasion score out of 10. Format exactly as: SCORE: X/10."

    prompt_text = f"{system_prompt}\n\nArtifact Payload:\n{artifact_payload}"

    # Utilizing gemini-2.5-flash for maximum C-Suite multiplexing velocity
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "temperature": 0.2  # Strict analytical constraint to prevent format hallucinations
        }
    }

    try:
        # The core I/O release. The ASGI worker thread is freed here.
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=45.0)
            response.raise_for_status()
            data = response.json()

            # CRITICAL FIX: candidates and parts are arrays, not objects.
            # The Gemini REST API returns: candidates[0].content.parts[0].text
            feedback_text = data["candidates"][0]["content"]["parts"][0]["text"]

            # Mathematical Extraction Matrix for the CRITIC
            score = None
            if agent_role == "CRITIC":
                match = re.search(r"SCORE:\s*(\d+)(?:\.\d+)?/10", feedback_text, re.IGNORECASE)
                if match:
                    score = int(match.group(1))
                else:
                    logger.warning("[CRITIC] Formatting hallucination detected. Regex extraction failed. Defaulting score to 0.")
                    score = 0

            logger.info(f"[{agent_role}] Inference complete.")
            return {
                "agent": agent_role,
                "feedback": feedback_text,
                "score": score
            }

    except httpx.HTTPStatusError as e:
        logger.error(f"[{agent_role}] Cognitive HTTP Error: {e.response.text}")
        return {"agent": agent_role, "feedback": f"COGNITIVE FRACTURE: HTTP {e.response.status_code}", "score": 0 if agent_role == "CRITIC" else None}
    except Exception as e:
        logger.error(f"[{agent_role}] Cognitive I/O Fracture: {str(e)}")
        return {"agent": agent_role, "feedback": "COGNITIVE FRACTURE: Network Timeout.", "score": 0 if agent_role == "CRITIC" else None}

# ── THE BOARD SECRETARY: AUTONOMOUS REVISION ENGINE ──────────────────

MAX_REVISION_STRIKES = 3  # Hard deadlock prevention limit

async def _execute_artifact_revision(artifact_type: str, original_content: str, feedback_results: list) -> str:
    """
    The Mode B Auto-Iterative Engine.
    Synthesizes a revised artifact based strictly on the multiplexed C-Suite feedback.
    """
    api_key = _get_api_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="Cognitive engine disconnected.")

    logger.info(f"[BOARD SECRETARY] Initiating autonomous revision for {artifact_type}...")

    # Consolidate the multiplexed feedback into a single injection payload
    feedback_payload = "\n\n".join([
        f"--- {res['agent']} FEEDBACK ---\n{res['feedback']}"
        for res in feedback_results
    ])

    system_prompt = (
        "You are the Board Secretary and Lead Synthesizer. "
        f"Your task is to rewrite the original {artifact_type} artifact to satisfy the C-Suite's demands. "
        "You must directly address the CRITIC's flaws and incorporate the CFO/CMO/CEO strategic pivots. "
        "Output ONLY the revised artifact. No conversational filler."
    )

    prompt_text = (
        f"{system_prompt}\n\n"
        f"--- ORIGINAL ARTIFACT ---\n{original_content}\n\n"
        f"--- C-SUITE DIRECTIVES ---\n{feedback_payload}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    req_payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
        "generationConfig": {"temperature": 0.4}  # Slight increase for creative restructuring
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=req_payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            # CRITICAL: candidates and parts are arrays
            revised = data["candidates"][0]["content"]["parts"][0]["text"]
            logger.info(f"[BOARD SECRETARY] Revision synthesized ({len(revised)} chars).")
            return revised

    except Exception as e:
        logger.error(f"[BOARD SECRETARY] Revision Fracture: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to synthesize artifact revision.")


# ── THE MODE B LIVE-DEBATE ENDPOINT WITH AUTO-ITERATIVE LOOP ─────────

@venture_router.post("/live-debate")
async def execute_live_debate(payload: ArtifactPayload = Body(...)):
    """
    The Mode B Asynchronous Matrix with Autonomous Socratic Revision Loop.
    Executes C-Suite deliberation via single-thread event loop multiplexing.
    If CRITIC consensus is not reached, the Board Secretary autonomously
    revises the artifact and re-submits (up to MAX_REVISION_STRIKES).
    """
    agents = ["CEO", "CFO", "CMO", "CRITIC"]
    current_content = payload.content
    iteration_log = []

    for revision_count in range(MAX_REVISION_STRIKES + 1):  # 0 = initial, 1-3 = revisions
        iteration_label = "INITIAL" if revision_count == 0 else f"REVISION_{revision_count}"
        logger.info(f"[MODE B] [{iteration_label}] Igniting async live debate (strike {revision_count}/{MAX_REVISION_STRIKES})...")

        # 🚨 THE STRUCTURAL MUTATION 🚨
        # ThreadPoolExecutor is eradicated. We map the async coroutines.
        tasks = [_async_agent_prompt(role, current_content) for role in agents]

        # asyncio.gather fires all network requests concurrently on a single thread.
        debate_results = await asyncio.gather(*tasks)

        # Extract CRITIC consensus for the auto-iterative Socratic loop
        critic_result = next((res for res in debate_results if res["agent"] == "CRITIC"), None)

        if not critic_result or critic_result["score"] is None:
            raise HTTPException(status_code=500, detail="CRITIC agent failed to yield a consensus score.")

        consensus_achieved = critic_result["score"] >= 7

        # Log this iteration
        iteration_log.append({
            "iteration": iteration_label,
            "critic_score": critic_result["score"],
            "results": list(debate_results),
        })

        if consensus_achieved:
            logger.info(f"[MODE B] CONSENSUS REACHED on {iteration_label} with score {critic_result['score']}/10.")
            return {
                "status": "CONSENSUS_REACHED",
                "critic_score": critic_result["score"],
                "results": debate_results,
                "revision_count": revision_count,
                "iteration_log": iteration_log,
                "final_artifact": current_content,
            }

        # ── DEADLOCK CHECK: Have we exhausted all revision strikes? ──
        if revision_count >= MAX_REVISION_STRIKES:
            logger.warning(f"[MODE B] DEADLOCK: {MAX_REVISION_STRIKES} revision strikes exhausted. Final score: {critic_result['score']}/10.")
            break

        # ── AUTO-ITERATIVE REVISION: Board Secretary synthesizes V{n+1} ──
        logger.info(f"[MODE B] Score {critic_result['score']}/10 — ITERATION_REQUIRED. Firing Board Secretary revision {revision_count + 1}...")
        current_content = await _execute_artifact_revision(
            artifact_type=payload.artifact_type,
            original_content=current_content,
            feedback_results=list(debate_results),
        )

    # Exhausted all strikes without consensus
    return {
        "status": "DEADLOCK_EXHAUSTED",
        "critic_score": critic_result["score"],
        "results": debate_results,
        "revision_count": MAX_REVISION_STRIKES,
        "iteration_log": iteration_log,
        "final_artifact": current_content,
    }
