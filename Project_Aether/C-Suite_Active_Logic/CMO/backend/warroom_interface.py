"""
CMO Agent — War Room Interface (Search-Grounded)
══════════════════════════════════════════════════
Standardized API contract for the War Room integration.
Returns structured CMO perspectives that the Commander app
can parse and display alongside other agents.

Layer 1: Gemini Search Grounding (real-time Google Search)
"""

import json
import os
from google import genai
from google.genai import types

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())

WARROOM_PROMPT = """You are CMO_Elite — the Chief Marketing Officer of Antigravity-AI, seated at the War Room boardroom table.

The Commander has brought a topic for deliberation. Other agents (CEO, CFO, CTO, Critic) may also be present.
Your role is to provide the definitive MARKETING perspective on this topic.

TOPIC:
{topic}

CONTEXT:
{context}

OTHER AGENTS PRESENT: {agents_present}

Respond as CMO_Elite. Be decisive, data-driven, and specific. Draw from:
- Market research and competitive intelligence
- Brand strategy and positioning
- Audience psychology and psychographic insights
- Go-to-market tactics and channel strategy
- Growth metrics and KPIs

Produce a JSON response with EXACTLY this structure:
{{
  "agent": "CMO_Elite",
  "status": "decisive",
  "perspective": "string — your 2-3 sentence strategic marketing perspective on this topic",
  "data_points": ["string — 3-5 specific data points, metrics, or market facts supporting your perspective"],
  "recommendations": ["string — 3-4 specific, actionable marketing recommendations"],
  "confidence_score": 0.0,
  "risk_flags": ["string — any marketing risks or blind spots to flag (0-2 items)"],
  "collaboration_needs": ["string — what you need from other agents to refine your recommendation (0-2 items)"]
}}

The confidence_score should be a float between 0.0 and 1.0 reflecting how confident you are in your analysis.
Higher confidence when the topic is clearly within marketing domain. Lower when it requires data you don't have.

IMPORTANT: Return ONLY valid JSON. No markdown, no code fences.
Be specific and decisive — the Commander values clarity over hedging."""


async def warroom_respond(topic: str, context: str = "", agents_present: list = None) -> dict:
    """
    Generate the CMO's perspective for a War Room deliberation.
    
    This is the standard API contract that the War Room app will call
    to get the CMO's "seat at the table" input on any topic.
    
    Args:
        topic: The topic or question being deliberated
        context: Additional context (previous agent responses, documents, etc.)
        agents_present: List of other agents at the table
        
    Returns:
        Standardized War Room response dict
    """
    client = get_client()
    
    agents_str = ", ".join(agents_present) if agents_present else "CEO, CFO, CTO, Critic"
    
    prompt = WARROOM_PROMPT.format(
        topic=topic,
        context=context or "No additional context provided.",
        agents_present=agents_str
    )
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[GROUNDING_TOOL],
            temperature=0.45,
            max_output_tokens=4096,
        )
    )
    
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    if text.startswith("json"):
        text = text[4:]
    text = text.strip()
    
    try:
        result = json.loads(text)
        # Enforce schema compliance
        result["agent"] = "CMO_Elite"
        if "confidence_score" in result:
            result["confidence_score"] = round(float(result["confidence_score"]), 2)
        return result
    except (json.JSONDecodeError, ValueError):
        return {
            "agent": "CMO_Elite",
            "status": "error",
            "perspective": "CMO analysis could not be completed. Retrying with fallback.",
            "data_points": [],
            "recommendations": ["Retry the analysis with more specific context."],
            "confidence_score": 0.1,
            "risk_flags": ["Analysis parsing failed — raw response may contain useful insights"],
            "collaboration_needs": [],
            "_raw_fallback": text[:1500]
        }
