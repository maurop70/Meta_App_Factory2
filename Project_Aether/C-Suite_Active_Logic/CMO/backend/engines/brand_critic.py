"""
CMO Agent — Brand Critic Engine (Marcus Vane)
═══════════════════════════════════════════════════
Senior Creative Director persona that evaluates brand
identities and provides professional critique with
scoring, strengths/weaknesses, and actionable feedback.

Layer 1: Gemini Search Grounding (compares to real brands)
"""

import json
import os
import base64
from pathlib import Path
from google import genai
from google.genai import types

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


CRITIC_PROMPT = """You are Marcus Vane — a Senior Creative Director with 20 years of experience at
Pentagram, Collins, and IDEO. You are known for your brutally honest but constructive critiques.
You have deep expertise in brand strategy, visual identity, typography, color theory, and
consumer psychology.

You have access to real-time internet search. USE IT to compare this brand identity against
real competitor brands in the same industry.

BRAND IDENTITY TO REVIEW:
{identity_json}

{image_context}

ADDITIONAL CONTEXT:
{context}

PREVIOUS FEEDBACK FROM USER:
{user_feedback}

Produce a thorough brand critique as JSON with EXACTLY this structure:
{{
  "critic_name": "Marcus Vane",
  "critic_title": "Senior Creative Director",
  "overall_score": 0,
  "verdict": "EXCEPTIONAL | STRONG | SOLID | NEEDS_WORK | WEAK",
  "one_liner": "string — your single-sentence gut reaction",
  "strengths": [
    {{
      "point": "string — what works well",
      "detail": "string — why this is effective",
      "industry_reference": "string — a real brand that does this well for comparison"
    }}
  ],
  "weaknesses": [
    {{
      "point": "string — what doesn't work or could be better",
      "detail": "string — why this is a problem",
      "fix": "string — specific actionable improvement"
    }}
  ],
  "suggestions": [
    {{
      "priority": 1,
      "suggestion": "string — specific design or strategy recommendation",
      "rationale": "string — why this matters",
      "effort": "QUICK_WIN | MODERATE | SIGNIFICANT"
    }}
  ],
  "competitor_comparison": {{
    "industry": "string — the industry this brand is in",
    "top_competitors": ["string — 2-3 real competitor brand names"],
    "positioning_gap": "string — how this brand differentiates (or fails to)",
    "market_fit_score": 0.0
  }},
  "typography_review": {{
    "score": 0,
    "comment": "string — specific typography feedback"
  }},
  "color_review": {{
    "score": 0,
    "comment": "string — specific color palette feedback"
  }},
  "naming_review": {{
    "score": 0,
    "comment": "string — feedback on the brand name and tagline"
  }},
  "overall_recommendation": "string — 2-3 sentence final recommendation"
}}

IMPORTANT RULES:
- overall_score is 0-100. Be honest — most first-pass brands score 55-75.
- Reference REAL competitor brands by name (search for them).
- Be specific and actionable — don't say "make it better," say "use a tighter kerning on the logotype."
- The one_liner should be memorable and quotable.
- Return ONLY valid JSON. No markdown, no code fences.
"""


async def critique_brand(
    identity: dict,
    image_path: str = None,
    context: str = "",
    user_feedback: str = "",
) -> dict:
    """
    Run Marcus Vane's brand critique on an identity.

    Args:
        identity: Brand identity JSON
        image_path: Optional path to generated brand image for visual critique
        context: Additional context (market research, etc.)
        user_feedback: Previous user feedback if iterating

    Returns:
        Structured critique JSON
    """
    client = get_client()

    # Build image context
    image_context = "No brand visual was provided for review."
    contents = []

    if image_path:
        full_path = Path(__file__).parent.parent / "frontend" / image_path.lstrip("/")
        if full_path.exists():
            image_context = "A brand visual mockup has been provided. Review the visual design, color usage, typography rendering, and overall aesthetic quality in your critique."
            # Read image and include it
            with open(full_path, "rb") as f:
                img_bytes = f.read()
            img_b64 = base64.b64encode(img_bytes).decode()

    # Build the text prompt
    identity_str = json.dumps(identity, indent=2)[:3000]
    prompt_text = CRITIC_PROMPT.format(
        identity_json=identity_str,
        image_context=image_context,
        context=context or "None provided",
        user_feedback=user_feedback or "No previous feedback — this is the first review.",
    )

    # Build content parts
    if image_path and full_path.exists():
        contents = [
            types.Part.from_text(text=prompt_text),
            types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
        ]
    else:
        contents = prompt_text

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[GROUNDING_TOOL],
            temperature=0.5,
            max_output_tokens=6144,
        ),
    )

    text = response.text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end+1]

    try:
        result = json.loads(text)
        result["_search_grounded"] = True
        return result
    except json.JSONDecodeError:
        return {
            "critic_name": "Marcus Vane",
            "critic_title": "Senior Creative Director",
            "overall_score": 60,
            "verdict": "NEEDS_WORK",
            "one_liner": "The critique engine encountered a parsing issue.",
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
            "overall_recommendation": text[:500],
            "error": "Failed to parse structured critique",
        }
