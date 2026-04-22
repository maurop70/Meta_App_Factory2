"""
CMO Agent — Campaign Planner Engine (Search-Grounded)
══════════════════════════════════════════════════════
Multi-channel campaign brief generation, content calendars,
messaging frameworks, and campaign strategy.

Layer 1: Gemini Search Grounding (real-time Google Search)
"""

import json
import os
from google import genai
from google.genai import types

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())


CAMPAIGN_PROMPT = """You are an elite campaign strategist and creative director at a top marketing agency.
You have access to real-time internet search. USE IT to find current ad platform costs, trending formats, and benchmark conversion rates.

Given the following product/company/campaign brief, create a comprehensive marketing campaign plan.

INPUT:
{user_input}

ADDITIONAL CONTEXT:
{context}

Produce a JSON response with EXACTLY this structure:
{{
  "campaign_name": "string — a catchy, memorable campaign name",
  "company_name": "string",
  "campaign_type": "string — e.g. 'Product Launch', 'Brand Awareness', 'Lead Generation'",
  "duration": "string — e.g. '8 weeks'",
  "budget_range": "string — estimated budget range",
  "campaign_summary": "string — 2-3 sentence overview of the campaign concept",
  "objectives": [
    {{
      "objective": "string — specific, measurable objective",
      "metric": "string — how success is measured",
      "target": "string — specific target number/percentage"
    }}
  ],
  "target_audience": {{
    "primary": "string — primary audience description",
    "secondary": "string — secondary audience",
    "exclusions": "string — who to exclude from targeting"
  }},
  "messaging_framework": {{
    "core_message": "string — the one thing we want the audience to remember",
    "supporting_messages": ["string — 3-4 supporting proof points"],
    "tone": "string — campaign voice/tone",
    "cta_primary": "string — primary call-to-action",
    "cta_secondary": "string — secondary/soft CTA"
  }},
  "channel_plan": [
    {{
      "channel": "string — channel name",
      "role": "string — what this channel does in the campaign",
      "content_types": ["string — types of content for this channel"],
      "frequency": "string — posting/ad frequency",
      "budget_share": "string — percentage of total budget",
      "key_metrics": ["string — 2-3 metrics to track"]
    }}
  ],
  "content_calendar": [
    {{
      "week": "string — e.g. 'Week 1-2'",
      "theme": "string — weekly theme",
      "deliverables": [
        {{
          "type": "string — content type",
          "channel": "string — destination channel",
          "description": "string — brief description",
          "cta": "string"
        }}
      ]
    }}
  ],
  "creative_brief": {{
    "concept": "string — the big creative idea",
    "visual_direction": "string — art direction guidance",
    "copy_direction": "string — copywriting style guidance",
    "hero_assets": ["string — 3-4 key creative assets needed"],
    "do_not_do": ["string — 3 creative guardrails"]
  }},
  "measurement_plan": {{
    "awareness_kpis": ["string — 2-3 awareness metrics"],
    "engagement_kpis": ["string — 2-3 engagement metrics"],
    "conversion_kpis": ["string — 2-3 conversion metrics"],
    "reporting_cadence": "string — how often to report"
  }},
  "risk_mitigation": [
    {{
      "risk": "string",
      "contingency": "string"
    }}
  ]
}}

IMPORTANT: Return ONLY valid JSON. No markdown, no code fences.
Be creative and specific — not generic. Campaign names should be catchy. Tactics should be actionable.
Create a 4-6 week content calendar with concrete deliverables."""


async def generate_campaign(user_input: str, context: str = "") -> dict:
    """Generate a comprehensive campaign plan."""
    client = get_client()
    
    prompt = CAMPAIGN_PROMPT.format(
        user_input=user_input,
        context=context or "None provided"
    )
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[GROUNDING_TOOL],
            temperature=0.55,
            max_output_tokens=8192,
        )
    )
    
    text = response.text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end+1]
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "error": "Failed to parse campaign plan response",
            "raw_response": text[:2000]
        }
