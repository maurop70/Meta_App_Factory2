"""
CMO Agent — Competitive Matrix Engine (Search-Grounded)
═══════════════════════════════════════════════════════
SWOT analysis, differentiation mapping, moat assessment,
and competitive positioning matrix generation.

Layer 1: Gemini Search Grounding (real-time Google Search)
Layer 2: Deep Research Crawler (Wikipedia, Reddit, custom)
"""

import json
import os
import sys
from pathlib import Path
from google import genai
from google.genai import types

# Add shared modules to path
SHARED_MODULES = str(Path(__file__).parent.parent.parent.parent / "shared_modules")
if SHARED_MODULES not in sys.path:
    sys.path.insert(0, SHARED_MODULES)

try:
    from deep_research_crawler import deep_research
    HAS_CRAWLER = True
except ImportError:
    HAS_CRAWLER = False

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())


def _extract_citations(response) -> list:
    citations = []
    try:
        metadata = response.candidates[0].grounding_metadata
        if metadata and metadata.grounding_chunks:
            for chunk in metadata.grounding_chunks:
                if hasattr(chunk, 'web') and chunk.web:
                    citations.append({
                        "title": chunk.web.title if hasattr(chunk.web, 'title') else "",
                        "url": chunk.web.uri if hasattr(chunk.web, 'uri') else "",
                    })
    except Exception:
        pass
    return citations


def _clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    if text.startswith("json"):
        text = text[4:]
    return text.strip()


COMPETITIVE_PROMPT = """You are an elite competitive intelligence analyst and strategy consultant.
You have access to real-time internet search. USE IT to find current competitor data, funding rounds, pricing, market share, and news.

Given the following company/product information, produce a comprehensive competitive analysis.

INPUT:
{user_input}

ADDITIONAL CONTEXT:
{context}

REAL-TIME RESEARCH INTELLIGENCE (pre-fetched from the web):
{research_intel}

IMPORTANT INSTRUCTIONS:
- Search for REAL competitor companies, their actual pricing, real revenue data.
- Do NOT guess — use search to find actual market data.
- Cite specific sources when possible.

Produce a JSON response with EXACTLY this structure:
{{
  "company_name": "string",
  "industry": "string",
  "analysis_summary": "string — 2-3 sentence executive summary",
  "swot": {{
    "strengths": [
      {{
        "factor": "string — strength name",
        "description": "string — why this is a strength",
        "leverage_strategy": "string — how to maximize this"
      }}
    ],
    "weaknesses": [
      {{
        "factor": "string",
        "description": "string",
        "mitigation": "string — how to address this"
      }}
    ],
    "opportunities": [
      {{
        "factor": "string",
        "description": "string",
        "capture_strategy": "string — how to seize this"
      }}
    ],
    "threats": [
      {{
        "factor": "string",
        "description": "string",
        "defense_strategy": "string — how to defend against this"
      }}
    ]
  }},
  "competitive_matrix": [
    {{
      "competitor": "string — competitor name",
      "category": "DIRECT | INDIRECT | POTENTIAL",
      "market_share": "string — estimated market share or 'Unknown'",
      "pricing": "string — pricing info",
      "key_features": ["string — 3-4 key features"],
      "differentiator": "string — their main USP",
      "weakness_to_exploit": "string — where we can win against them",
      "threat_level": "HIGH | MEDIUM | LOW"
    }}
  ],
  "differentiation_map": {{
    "our_unique_value": "string — what ONLY we offer",
    "shared_features": ["string — features we share with competitors"],
    "competitor_advantages": ["string — where competitors are ahead"],
    "defensibility": "string — how hard it is to copy our advantages"
  }},
  "moat_analysis": {{
    "moat_type": "string — e.g. 'Network Effects', 'Data Moat', 'Switching Costs'",
    "moat_strength": "STRONG | MODERATE | WEAK | BUILDING",
    "description": "string — detailed moat assessment",
    "time_to_replicate": "string — how long it would take a competitor to copy",
    "moat_builders": ["string — 3-4 actions that strengthen the moat"],
    "moat_threats": ["string — 2-3 things that could erode the moat"]
  }},
  "positioning_recommendation": {{
    "current_position": "string — where we sit today",
    "desired_position": "string — where we should aim",
    "positioning_moves": ["string — 3-4 specific strategic moves"],
    "timeline": "string — realistic timeline"
  }},
  "sources_consulted": ["string — list of sources used"],
  "strategic_recommendations": [
    {{
      "priority": "number — 1 is highest",
      "recommendation": "string — specific action",
      "rationale": "string — why this matters",
      "expected_impact": "HIGH | MEDIUM | LOW",
      "effort": "HIGH | MEDIUM | LOW"
    }}
  ]
}}

IMPORTANT: Return ONLY valid JSON. No markdown, no code fences.
Provide 4-5 items for strengths, weaknesses, opportunities, threats each.
Include 3-5 competitors in the matrix. Be specific and data-informed."""


async def analyze_competitive_landscape(user_input: str, context: str = "") -> dict:
    """Run a comprehensive competitive analysis with internet access."""
    client = get_client()

    # ── Layer 2: Deep Research Crawler ────────────────────
    research_intel = "No pre-fetched research available."
    if HAS_CRAWLER:
        try:
            research = await deep_research(f"{user_input} competitors market share pricing")
            research_intel = research.get("intelligence_brief", "No findings.")
        except Exception as e:
            research_intel = f"Crawler error: {str(e)[:100]}"

    prompt = COMPETITIVE_PROMPT.format(
        user_input=user_input,
        context=context or "None provided",
        research_intel=research_intel,
    )

    # ── Layer 1: Gemini with Search Grounding ─────────────
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[GROUNDING_TOOL],
            temperature=0.4,
            max_output_tokens=8192,
        )
    )

    text = _clean_json_text(response.text)
    citations = _extract_citations(response)

    try:
        result = json.loads(text)
        if citations:
            result["_citations"] = citations
        result["_search_grounded"] = True
        result["_deep_research"] = HAS_CRAWLER
        return result
    except json.JSONDecodeError:
        return {
            "error": "Failed to parse competitive analysis response",
            "raw_response": text[:2000],
            "_citations": citations,
        }
