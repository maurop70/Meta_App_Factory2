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

logger = logging.getLogger("ModelRouter")

# ── Model Definitions ────────────────────────────────────────────────
GEMINI_FLASH = "gemini-2.5-flash"
GEMINI_PRO = "gemini-2.5-pro"
CLAUDE_SONNET = "claude-3-7-sonnet-20250219"

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
}


def _get_gemini_key():
    """Retrieve Gemini API key from vault or env."""
    try:
        from vault import get_secret
        key = get_secret("GEMINI_API_KEY")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY", "")


def _get_anthropic_key():
    """Retrieve Anthropic API key from vault or env."""
    try:
        from vault import get_secret
        key = get_secret("ANTHROPIC_API_KEY")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("ANTHROPIC_API_KEY", "")


def _call_gemini(prompt: str, system_prompt: str = "", api_key: str = "", model_name: str = GEMINI_FLASH) -> str:
    """Call Gemini models via REST API."""
    if not api_key:
        api_key = _get_gemini_key()
    if not api_key:
        return ""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

    parts = []
    if system_prompt:
        parts.append({"text": f"[SYSTEM]: {system_prompt}\n\n{prompt}"})
    else:
        parts.append({"text": prompt})

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


def route(task_type: str, prompt: str, system_prompt: str = "") -> str:
    """
    Route a prompt to the optimal LLM based on task type.
    Falls back: preferred model → alternative model → empty string.
    """
    preferred = get_model_for_task(task_type)
    logger.info(f"[ModelRouter] Task '{task_type}' → {preferred}")

    if preferred == CLAUDE_SONNET:
        # Try Claude first, fallback to Gemini
        response = _call_claude(prompt, system_prompt)
        if response:
            return f"🧠 [Claude] {response[:2000]}"
        logger.info(f"[ModelRouter] Claude unavailable for '{task_type}', falling back to Gemini")
        response = _call_gemini(prompt, system_prompt, model_name=GEMINI_FLASH)
        if response:
            return f"🤖 [Gemini] {response[:2000]}"
    else:
        # Try Gemini (Pro or Flash) first, fallback to Claude
        response = _call_gemini(prompt, system_prompt, model_name=preferred)
        if response:
            return f"🤖 [Gemini] {response[:2000]}"
        logger.info(f"[ModelRouter] Gemini unavailable for '{task_type}', falling back to Claude")
        response = _call_claude(prompt, system_prompt)
        if response:
            return f"🧠 [Claude] {response[:2000]}"

    return ""


if __name__ == "__main__":
    print(f"CEO   → {get_model_for_task('CEO')}")
    print(f"CFO   → {get_model_for_task('CFO')}")
    print(f"CRITIC → {get_model_for_task('CRITIC')}")
    print(f"brand  → {get_model_for_task('brand_identity')}")
    print(f"legal  → {get_model_for_task('legal_analysis')}")
