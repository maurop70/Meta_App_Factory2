"""
model_router.py — Intelligent per-task LLM routing for Meta App Factory
═════════════════════════════════════════════════════════════════════════
Routes between Gemini 2.5 Flash (fast/creative/multimodal) and Claude 3.7 Sonnet
(deep reasoning/math/structured analysis) based on task type.
"""

import os
import json
import logging
import requests

# Standalone invocations (loop_engine planner, CLI tests) need .env loaded;
# inside api.py this is a no-op since the environment is already populated.
try:
    from dotenv import load_dotenv
    from pathlib import Path as _Path
    load_dotenv(_Path(__file__).parent / ".env")
    load_dotenv(_Path(__file__).parent.parent / ".env")
except ImportError:
    pass

logger = logging.getLogger("ModelRouter")

# ── Model Definitions ────────────────────────────────────────────────
GEMINI_FLASH = "gemini-2.5-flash"
GEMINI_PRO = "gemini-2.5-pro"
# claude-3-7-sonnet-20250219 was retired (404 as of 2026-06-12); current
# Sonnet verified live on this key. Override without code change via env.
CLAUDE_SONNET = os.getenv("CLAUDE_ROUTER_MODEL", "claude-sonnet-4-6")

# ── Task → Model Mapping ────────────────────────────────────────────
# Gemini: fast inference, creative/generative, multimodal (images)
# Claude: deep analytical reasoning, structured math, cross-doc reconciliation
TASK_ROUTING = {
    # War Room Agents
    "CEO":          GEMINI_FLASH,     # Strategic vision, fast creative
    "CMO":          GEMINI_FLASH,     # Marketing narratives, creative
    "CFO":          CLAUDE_SONNET,    # Financial modeling, structured math
    "CRITIC":       CLAUDE_SONNET,    # Deep adversarial analysis
    "ARCHITECT":    GEMINI_FLASH,     # Technical design, fast iteration

    # Deliverable Generators
    "market_intel":      GEMINI_FLASH,     # Market research, creative synthesis
    "brand_identity":    GEMINI_FLASH,     # Brand DNA, creative/visual
    "legal_analysis":    CLAUDE_SONNET,    # Legal reasoning, structured
    "financial_model":   CLAUDE_SONNET,    # Spreadsheet math, projections
    "assumptions_extraction": GEMINI_PRO,  # NL request -> structured model-assumptions JSON (Gemini)
    "business_plan":     CLAUDE_SONNET,    # Cross-doc reconciliation
    "funding_strategy":  CLAUDE_SONNET,    # Financial gap analysis
    "pitch_deck":        GEMINI_FLASH,     # Presentation copy, creative

    # Sentinel / Overwatch (Adv_Autonomous_Agent)
    "sentinel_snap_back": GEMINI_FLASH,   # Fast injection
    "sentinel_diagnostic": GEMINI_PRO,     # Deep reasoning

    # Special Tasks
    "document_upload":   GEMINI_FLASH,     # Multimodal (image + text)
    "implementation_plan": CLAUDE_SONNET,  # Structured planning
    "code_generation":   CLAUDE_SONNET,    # Code writing
    "chat":              GEMINI_FLASH,     # General conversation

    # Visual Critic (ClaudeAY Auditor — layout/design screenshot review)
    "visual_critic":     GEMINI_PRO,       # Spatial reasoning on screenshots
}

# Vision model override (e.g. gemini-2.5-flash for faster/cheaper critiques)
VISION_MODEL_ENV = "GEMINI_VISION_MODEL"


def _get_gemini_key():
    """Retrieve Gemini API key from env."""
    key = os.getenv("GEMINI_API_KEY", "")
    return key.strip("'\"")


def _get_anthropic_key():
    """Retrieve Anthropic API key from env."""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if key:
        key = key.strip("'\"")
    if not key:
        logger.warning("[ModelRouter] WARNING: ANTHROPIC_API_KEY missing from .env. Forcing degraded Gemini fallback for Claude-designated nodes.")
    return key


def _call_gemini(prompt: str, system_prompt: str = "", api_key: str = "",
                 model_name: str = GEMINI_FLASH,
                 image_b64: str = None, image_mime: str = "image/png") -> str:
    """Call Gemini models via REST API. Optional inline image for vision tasks."""
    if not api_key:
        api_key = _get_gemini_key()
    if not api_key:
        # Loud, never silent (CLAUDE_RULES 0.3)
        logger.warning("[ModelRouter] GEMINI_API_KEY missing — Gemini call skipped")
        return ""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

    parts = []
    if system_prompt:
        parts.append({"text": f"[SYSTEM]: {system_prompt}\n\n{prompt}"})
    else:
        parts.append({"text": prompt})
    if image_b64:
        parts.append({"inlineData": {"mimeType": image_mime, "data": image_b64}})

    data = {"contents": [{"role": "user", "parts": parts}]}

    try:
        r = requests.post(url, json=data, headers=headers, timeout=60)
        candidates = r.json().get("candidates", [])
        if candidates:
            return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
    except Exception as e:
        logger.warning(f"[Gemini] Call failed: {e}")
    return ""


def _call_claude(prompt: str, system_prompt: str = "", api_key: str = "") -> str:
    """Call Claude 3.7 Sonnet via Anthropic Messages API."""
    if not api_key:
        api_key = _get_anthropic_key()
    if not api_key:
        return ""  # Will fallback to Gemini

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    data = {
        "model": CLAUDE_SONNET,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        data["system"] = system_prompt

    try:
        r = requests.post(url, json=data, headers=headers, timeout=90)
        result = r.json()
        content = result.get("content", [])
        if content:
            return content[0].get("text", "").strip()
    except Exception as e:
        logger.warning(f"[Claude] Call failed: {e}")
    return ""


def get_model_for_task(task_type: str) -> str:
    """Return the model name that best fits the given task type."""
    return TASK_ROUTING.get(task_type, GEMINI_FLASH)


def route_multimodal(task_type: str, prompt: str, image_b64: str,
                     image_mime: str = "image/png", system_prompt: str = "") -> str:
    """
    Route a vision task (prompt + inline image) to a Gemini vision model.
    Model: GEMINI_VISION_MODEL env override, else the task's TASK_ROUTING
    entry (visual_critic → gemini-2.5-pro for spatial reasoning).

    Returns the RAW model text ('' on failure) — no emoji prefixes and no
    truncation, because callers (auditor visual critic) parse a verdict
    out of the response. API key absence is logged loudly, never silent
    (CLAUDE_RULES 0.3).
    """
    if not _get_gemini_key():
        logger.warning("[ModelRouter] GEMINI_API_KEY missing — multimodal "
                       "route '%s' unavailable", task_type)
        return ""
    model = os.getenv(VISION_MODEL_ENV, "").strip() or get_model_for_task(task_type)
    logger.info(f"[ModelRouter] Multimodal task '{task_type}' → {model}")
    return _call_gemini(prompt, system_prompt, model_name=model,
                        image_b64=image_b64, image_mime=image_mime)


def route(task_type: str, prompt: str, system_prompt: str = "", high_availability: bool = False) -> str:
    """
    Route a prompt to the optimal LLM based on task type.
    Falls back: preferred model → alternative model → empty string.
    
    Resilience Matrix:
    - Heavy Tier (CLAUDE_SONNET) falls back strictly to Heavy Tier (GEMINI_PRO).
    - Heavy Tier (GEMINI_PRO) falls back strictly to Heavy Tier (CLAUDE_SONNET).
    - Speed Tier (GEMINI_FLASH) fails cleanly without fallback unless high_availability=True.
    """
    preferred = get_model_for_task(task_type)
    logger.info(f"[ModelRouter] Task '{task_type}' → {preferred} (high_availability={high_availability})")

    if preferred == CLAUDE_SONNET:
        # Heavy Tier: Claude Sonnet -> Fallback strictly to Gemini Pro
        response = _call_claude(prompt, system_prompt)
        if response:
            return f"🧠 [Claude] {response[:2000]}"
        logger.warning(f"[ModelRouter] Claude Sonnet unavailable for '{task_type}', falling back strictly to Gemini Pro")
        response = _call_gemini(prompt, system_prompt, model_name=GEMINI_PRO)
        if response:
            return f"🤖 [Gemini Pro] {response[:2000]}"
            
    elif preferred == GEMINI_PRO:
        # Heavy Tier: Gemini Pro -> Fallback strictly to Claude Sonnet
        response = _call_gemini(prompt, system_prompt, model_name=GEMINI_PRO)
        if response:
            return f"🤖 [Gemini Pro] {response[:2000]}"
        logger.warning(f"[ModelRouter] Gemini Pro unavailable for '{task_type}', falling back strictly to Claude Sonnet")
        response = _call_claude(prompt, system_prompt)
        if response:
            return f"🧠 [Claude] {response[:2000]}"
            
    elif preferred == GEMINI_FLASH:
        # Speed Tier: Gemini Flash -> Fails cleanly unless high_availability=True
        response = _call_gemini(prompt, system_prompt, model_name=GEMINI_FLASH)
        if response:
            return f"🤖 [Gemini Flash] {response[:2000]}"
        
        if high_availability:
            logger.warning(f"[ModelRouter] Gemini Flash failed. high_availability=True, falling back to Heavy tier (Gemini Pro)")
            response = _call_gemini(prompt, system_prompt, model_name=GEMINI_PRO)
            if response:
                return f"🤖 [Gemini Pro] {response[:2000]}"
            logger.warning(f"[ModelRouter] Gemini Pro also failed under high_availability, trying Claude Sonnet")
            response = _call_claude(prompt, system_prompt)
            if response:
                return f"🧠 [Claude] {response[:2000]}"
        else:
            logger.warning(f"[ModelRouter] Gemini Flash failed. high_availability=False, clean-failing to conserve tokens.")

    return ""


if __name__ == "__main__":
    print(f"CEO   → {get_model_for_task('CEO')}")
    print(f"CFO   → {get_model_for_task('CFO')}")
    print(f"CRITIC → {get_model_for_task('CRITIC')}")
    print(f"brand  → {get_model_for_task('brand_identity')}")
    print(f"legal  → {get_model_for_task('legal_analysis')}")
