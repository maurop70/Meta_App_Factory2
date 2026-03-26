"""
CMO Agent — Go-to-Market Planner Engine (Search-Grounded)
════════════════════════════════════════════════════════
Launch sequencing, channel strategy, pricing architecture,
and growth lever identification.

Layer 1: Gemini Search Grounding (real-time Google Search)
"""

import json
import os
from google import genai
from google.genai import types

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())

GTM_PROMPT = """You are an elite Go-to-Market strategist at a top venture studio. You specialize in SaaS, B2B, and B2C launch strategies.
You have access to real-time internet search. USE IT to find current CAC benchmarks, channel costs, and similar product launches.

Given the following product/company information, create a comprehensive Go-to-Market playbook.

INPUT:
{user_input}

ADDITIONAL CONTEXT:
{context}

Produce a JSON response with EXACTLY this structure:
{{
  "company_name": "string",
  "product_name": "string",
  "target_market": "string — primary market segment",
  "gtm_summary": "string — 2-3 sentence GTM strategy overview",
  "launch_phases": [
    {{
      "phase": "string — phase name (e.g. 'Pre-Launch', 'Soft Launch', 'Growth')",
      "timeline": "string — e.g. 'Month 1-2'",
      "objectives": ["string — 2-3 key objectives"],
      "tactics": ["string — 3-5 specific tactics"],
      "success_metrics": ["string — 2-3 measurable KPIs"],
      "budget_allocation": "string — percentage or range"
    }}
  ],
  "channel_strategy": [
    {{
      "channel": "string — channel name",
      "priority": "PRIMARY | SECONDARY | EXPERIMENTAL",
      "audience_fit": "string — why this channel reaches the target",
      "content_type": "string — what content works here",
      "estimated_cac": "string — estimated customer acquisition cost",
      "tactics": ["string — 2-3 specific tactics"]
    }}
  ],
  "pricing_architecture": {{
    "model": "string — e.g. 'Freemium + SaaS Tiers'",
    "rationale": "string — why this pricing model",
    "tiers": [
      {{
        "name": "string — tier name",
        "price": "string — monthly price",
        "features": ["string — 3-5 key features"],
        "target_segment": "string — who this tier is for"
      }}
    ],
    "conversion_strategy": "string — how free users become paid"
  }},
  "growth_levers": [
    {{
      "lever": "string — growth lever name",
      "type": "PRODUCT_LED | COMMUNITY_LED | PARTNER_LED | CONTENT_LED | SALES_LED",
      "description": "string — how this lever works",
      "expected_impact": "HIGH | MEDIUM | LOW",
      "timeline_to_impact": "string — e.g. '30-60 days'"
    }}
  ],
  "launch_risks": [
    {{
      "risk": "string",
      "probability": "HIGH | MEDIUM | LOW",
      "impact": "HIGH | MEDIUM | LOW",
      "mitigation": "string"
    }}
  ],
  "first_90_days_plan": "string — concise narrative of the first 90 days"
}}

IMPORTANT: Return ONLY valid JSON. No markdown, no code fences.
Provide actionable, specific tactics — not generic advice. Include realistic timelines and metrics."""


async def generate_gtm_plan(user_input: str, context: str = "") -> dict:
    """Generate a comprehensive go-to-market playbook."""
    client = get_client()
    
    prompt = GTM_PROMPT.format(
        user_input=user_input,
        context=context or "None provided"
    )
    
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[GROUNDING_TOOL],
            temperature=0.45,
            max_output_tokens=8192,
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
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "error": "Failed to parse GTM plan response",
            "raw_response": text[:2000]
        }
