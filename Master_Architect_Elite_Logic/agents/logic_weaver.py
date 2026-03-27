"""
logic_weaver.py — Logic Weaver Agent
═════════════════════════════════════
Master_Architect_Elite_Logic | Triad Agent 2/3

Analyzes n8n workflow integration, Gemini Agent Bridge routing,
inter-agent communication, and fallback chain patterns.
"""

import os
import json
import logging
import requests
from typing import Optional

logger = logging.getLogger("LogicWeaver")

SYSTEM_PROMPT = """You are the Logic Weaver of the Master Architect Triad.
Your domain: n8n workflows, agent routing, inter-service communication, and fallback chains.

You are reviewing a proposed change to a software factory ecosystem that uses:
- n8n Cloud workflows for agent orchestration (webhooks, credential management)
- Gemini API for AI-powered agents
- FastAPI backends with SSE streaming
- Circuit breakers for n8n → Gemini → cached fallback chains
- C-Suite agent routing (CEO, CFO, CMO, CTO, HR, Critic)

Analyze the proposed change and output ONLY a JSON object (no markdown, no backticks):
{
  "domain": "logic",
  "score": <0-100>,
  "workflow_impacts": ["list of n8n workflows or webhook endpoints affected"],
  "agent_routing_changes": ["list of agent routing modifications"],
  "fallback_chain_valid": true/false,
  "circuit_breaker_status": "ok" or "warn" or "fail",
  "integration_points": ["services that need coordinated updates"],
  "concerns": ["max 3 architectural concerns"],
  "recommendations": ["max 3 actionable recommendations"]
}

Focus on:
- n8n webhook URL stability and credential references
- Agent dispatch path integrity (classifier → router → executor → reviewer)
- Circuit breaker configuration (failure threshold, cooldown)
- SSE/WebSocket connection lifecycle
- Race conditions in async agent orchestration
- Fallback chain completeness (n8n → Model Router → Gemini-only → cached)

Score 0-100 where 100 = flawless logic flow, 0 = broken routing.
Use ONLY ASCII characters."""


class LogicWeaver:
    """
    Triad Agent 2: Analyzes workflow integration and agent routing logic.
    Uses Gemini for intelligent analysis with keyword fallback.
    """

    def __init__(self, api_key: str = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model

    def analyze(self, description: str, change_type: str = "feature",
                components: list = None, context: dict = None) -> dict:
        ai_result = self._ai_analyze(description, change_type, components, context)
        if ai_result:
            return ai_result
        return self._fallback_analyze(description, change_type, components)

    def _ai_analyze(self, description: str, change_type: str,
                    components: list, context: dict) -> Optional[dict]:
        if not self.api_key:
            return None

        prompt = (
            f"CHANGE TYPE: {change_type}\n"
            f"AFFECTED COMPONENTS: {', '.join(components or ['unknown'])}\n"
            f"DESCRIPTION:\n{description[:3000]}\n"
        )
        if context:
            prompt += f"\nADDITIONAL CONTEXT:\n{json.dumps(context, indent=2)[:1000]}\n"
        prompt += "\nProvide your logic weaving review."

        try:
            import re
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n" + prompt}]}
                ],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
            }

            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code != 200:
                return None

            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

            if "```" in text:
                match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
                if match:
                    text = match.group(1).strip()
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                text = text[start:end + 1]
            text = text.encode('ascii', 'replace').decode('ascii')

            result = json.loads(text)
            result["domain"] = "logic"
            result["source"] = "gemini"
            result.setdefault("score", 70)
            result.setdefault("concerns", [])
            result.setdefault("recommendations", [])
            return result

        except Exception as e:
            logger.warning(f"Logic Weaver AI analysis failed: {e}")
            return None

    def _fallback_analyze(self, description: str, change_type: str,
                          components: list) -> dict:
        desc_lower = description.lower()
        score = 75
        concerns = []
        recommendations = []

        # n8n workflow check
        if any(kw in desc_lower for kw in ["n8n", "webhook", "workflow", "trigger"]):
            recommendations.append("Verify n8n webhook URLs are stable and credentials are valid")
            if "fallback" not in desc_lower:
                concerns.append("Workflow integration without explicit fallback chain")
                score -= 10

        # Agent routing check
        if any(kw in desc_lower for kw in ["agent", "route", "dispatch", "c-suite", "warroom"]):
            recommendations.append("Ensure agent dispatch follows classifier → router → executor → reviewer pipeline")
            if "circuit" not in desc_lower and "breaker" not in desc_lower:
                concerns.append("Agent routing change without circuit breaker consideration")
                score -= 5

        # SSE/WebSocket check
        if any(kw in desc_lower for kw in ["sse", "stream", "websocket", "real-time"]):
            recommendations.append("Implement connection keepalive and reconnection logic")
            if "timeout" not in desc_lower:
                concerns.append("Streaming endpoint without explicit timeout handling")
                score -= 5

        # Async check
        if any(kw in desc_lower for kw in ["async", "concurrent", "parallel", "thread"]):
            concerns.append("Review for race conditions in concurrent agent operations")
            score -= 5

        return {
            "domain": "logic",
            "source": "keyword_fallback",
            "score": max(0, min(100, score)),
            "workflow_impacts": [],
            "agent_routing_changes": [],
            "fallback_chain_valid": "fallback" in desc_lower,
            "circuit_breaker_status": "ok",
            "integration_points": components or [],
            "concerns": concerns[:3],
            "recommendations": recommendations[:3],
        }
