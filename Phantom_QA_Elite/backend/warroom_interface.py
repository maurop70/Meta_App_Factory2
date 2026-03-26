"""
warroom_interface.py — War Room Protocol for Phantom QA Elite
==============================================================
Standardized /api/warroom/respond endpoint matching the
Antigravity War Room communication protocol.
"""

import os
import json
import logging
from google import genai
from google.genai import types

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())

logger = logging.getLogger("Phantom.WarRoom")


def get_client():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        return genai.Client(api_key=api_key)
    return None


async def warroom_respond(question: str, context: dict = None) -> dict:
    """
    Respond to a War Room question from the Commander's perspective
    as the Chief Quality Assurance Officer.
    """
    from memory_store import get_dashboard_stats

    stats = get_dashboard_stats()
    context_str = json.dumps(context) if context else "No additional context"

    prompt = f"""You are Phantom QA Elite — the Chief Quality Assurance Officer in the Antigravity War Room.

Your role: You ensure every app, feature, and deployment meets production-quality standards.
You speak with authority on testing, quality metrics, system stability, and risk assessment.

CURRENT QA INTELLIGENCE:
- Total Test Runs: {stats.get('total_runs', 0)}
- Overall Pass Rate: {stats.get('pass_rate', 0)}%
- Average Score: {stats.get('avg_score', 0)}/100
- Apps Tested: {stats.get('total_apps', 0)}
- Individual Tests Executed: {stats.get('total_tests', 0)}
- Tests Passed: {stats.get('tests_passed', 0)}

RECENT RUNS:
{json.dumps(stats.get('recent_runs', []), indent=2)}

ADDITIONAL CONTEXT:
{context_str}

The Commander asks: {question}

Respond with a JSON object:
{{
    "perspective": "Your analysis as CQO (2-3 sentences, direct and authoritative)",
    "key_points": ["Point 1", "Point 2", "Point 3"],
    "recommendations": ["Action 1", "Action 2"],
    "risk_assessment": "LOW|MEDIUM|HIGH|CRITICAL",
    "confidence": 0.0-1.0,
    "data_sources": ["source1", "source2"]
}}

Return ONLY valid JSON."""

    client = get_client()
    if not client:
        return {
            "agent": "Phantom_QA_Elite",
            "role": "Chief Quality Assurance Officer",
            "error": "Gemini API not configured",
        }

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[GROUNDING_TOOL],
                temperature=0.4,
                max_output_tokens=1024,
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
        data = json.loads(text)
        data["agent"] = "Phantom_QA_Elite"
        data["role"] = "Chief Quality Assurance Officer"
        return data

    except Exception as e:
        logger.error(f"War Room response failed: {e}")
        return {
            "agent": "Phantom_QA_Elite",
            "role": "Chief Quality Assurance Officer",
            "perspective": f"QA systems operational. Pass rate: {stats.get('pass_rate', 0)}%. "
                           f"Error generating detailed response: {str(e)[:100]}",
            "key_points": [f"Total runs: {stats.get('total_runs', 0)}",
                           f"Average score: {stats.get('avg_score', 0)}/100"],
            "recommendations": ["Re-run Phantom QA on critical apps"],
            "risk_assessment": "MEDIUM",
            "confidence": 0.5,
            "data_sources": ["phantom_memory.db"],
        }
