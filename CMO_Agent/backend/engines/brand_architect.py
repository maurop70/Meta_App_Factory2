"""
CMO Agent — Brand Architect Engine (Search-Grounded)
═══════════════════════════════════════════════════════
AI-powered brand identity generation: name ideation,
color palettes, typography, tone of voice, visual style.

Layer 1: Gemini Search Grounding (real-time Google Search)
"""

import json
import os
from google import genai
from google.genai import types

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())

BRAND_IDENTITY_PROMPT = """You are an elite brand strategist and creative director at a world-class agency.
You have access to real-time internet search. USE IT to research competitor brands, current design trends, and naming conventions.

Given the following company/product brief, create a complete, premium brand identity.

INPUT:
{user_input}

ADDITIONAL CONTEXT:
{context}

Produce a JSON response with EXACTLY this structure:
{{
  "company_name": "string — the company or product name",
  "tagline": "string — a memorable, concise tagline (6-10 words max)",
  "mission_statement": "string — compelling mission statement (1-2 sentences)",
  "vision_statement": "string — aspirational vision (1-2 sentences)",
  "value_proposition": "string — clear value prop for the target customer",
  "brand_personality": {{
    "archetype": "string — e.g. 'The Innovator', 'The Guardian', 'The Explorer'",
    "traits": ["string — 5 personality traits"],
    "voice_characteristics": ["string — 4-5 voice descriptors like 'bold', 'precise', 'warm'"]
  }},
  "visual_identity": {{
    "color_palette": {{
      "primary": "string — hex code",
      "secondary": "string — hex code",
      "accent": "string — hex code",
      "background": "string — hex code",
      "surface": "string — hex code",
      "text_primary": "string — hex code",
      "text_secondary": "string — hex code"
    }},
    "color_rationale": "string — why these colors work for this brand",
    "typography": {{
      "heading_font": "string — Google Font name",
      "body_font": "string — Google Font name",
      "mono_font": "string — Google Font name for data/code",
      "rationale": "string — why these fonts"
    }},
    "visual_style": "string — description of the visual direction (e.g. 'dark-mode-first, glassmorphic, minimal')",
    "icon_style": "string — icon direction (e.g. 'geometric, duotone, rounded')",
    "imagery_direction": "string — photography/illustration style"
  }},
  "tone_of_voice": {{
    "summary": "string — 1 sentence tone summary",
    "dos": ["string — 5 things the brand voice should do"],
    "donts": ["string — 5 things the brand voice should NOT do"],
    "example_headlines": ["string — 3 example marketing headlines in this tone"]
  }},
  "positioning_statement": "string — formal positioning statement: For [target], [brand] is the [category] that [key benefit] because [reason to believe]",
  "competitive_differentiation": "string — 2-3 sentences on what makes this brand unique vs competitors",
  "brand_story": "string — A compelling 3-4 sentence narrative about the brand's origin and promise"
}}

IMPORTANT: Return ONLY valid JSON. No markdown, no code fences.
Make the identity feel premium, distinctive, and memorable. Colors should be harmonious and purposeful."""


async def generate_brand_identity(user_input: str, context: str = "") -> dict:
    """Generate a complete brand identity."""
    client = get_client()
    
    prompt = BRAND_IDENTITY_PROMPT.format(
        user_input=user_input,
        context=context or "None provided"
    )
    
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[GROUNDING_TOOL],
            temperature=0.6,
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
            "error": "Failed to parse brand identity response",
            "raw_response": text[:2000],
            "company_name": "Unknown"
        }


async def stream_brand_identity(user_input: str, context: str = ""):
    """Stream brand identity generation via SSE."""
    client = get_client()
    
    prompt = BRAND_IDENTITY_PROMPT.format(
        user_input=user_input,
        context=context or "None provided"
    )
    
    response = client.models.generate_content_stream(
        model="gemini-2.5-pro",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[GROUNDING_TOOL],
            temperature=0.6,
            max_output_tokens=8192,
        )
    )
    
    for chunk in response:
        if chunk.text:
            yield chunk.text
