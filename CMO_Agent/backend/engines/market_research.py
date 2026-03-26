"""
CMO Agent — Market Research Engine (Search-Grounded)
═════════════════════════════════════════════════════
TAM/SAM/SOM calculations, competitive intelligence,
trend identification, and market sizing analysis.

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

# Search grounding tool — gives Gemini live Google Search access
GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())


def _extract_citations(response) -> list:
    """Extract source citations from Gemini grounding metadata."""
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
    """Strip markdown fences and extract JSON from response."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    if text.startswith("json"):
        text = text[4:]
    return text.strip()


MARKET_RESEARCH_PROMPT = """You are the CMO of a top-tier AI venture studio. You are an elite market research analyst.
You have access to real-time internet search. USE IT to find current market data, recent reports, funding rounds, and news.

Given the following company/product/industry information, produce a comprehensive market research report.

INPUT:
{user_input}

ADDITIONAL CONTEXT (if any):
{context}

REAL-TIME RESEARCH INTELLIGENCE (pre-fetched from the web):
{research_intel}

IMPORTANT INSTRUCTIONS:
- Use the real-time research data above to ground your analysis in FACTS, not assumptions.
- Search for current market sizes, growth rates, and competitor data.
- Cite specific sources when possible.
- Do NOT guess revenue figures — search for them.

Produce a JSON response with EXACTLY this structure:
{{
  "company_name": "string — the company or product name being analyzed",
  "industry": "string — the primary industry/sector",
  "executive_summary": "string — 2-3 sentence executive summary of findings",
  "market_sizing": {{
    "tam": {{
      "value": "string — e.g. '$35.3B'",
      "description": "string — what the TAM represents",
      "source": "string — data source or methodology"
    }},
    "sam": {{
      "value": "string",
      "description": "string",
      "source": "string"
    }},
    "som": {{
      "value": "string",
      "description": "string — realistic Year 1 capture",
      "source": "string"
    }}
  }},
  "market_trends": [
    {{
      "trend": "string — trend name",
      "impact": "HIGH | MEDIUM | LOW",
      "description": "string — 1-2 sentences",
      "opportunity": "string — how to capitalize"
    }}
  ],
  "competitive_landscape": [
    {{
      "competitor": "string — company name",
      "market_position": "Leader | Challenger | Niche",
      "strengths": ["string"],
      "weaknesses": ["string"],
      "estimated_revenue": "string — if estimable"
    }}
  ],
  "market_gaps": [
    {{
      "gap": "string — unmet need",
      "severity": "CRITICAL | SIGNIFICANT | MODERATE",
      "opportunity_size": "string",
      "entry_strategy": "string"
    }}
  ],
  "entry_barriers": [
    {{
      "barrier": "string",
      "severity": "HIGH | MEDIUM | LOW",
      "mitigation": "string"
    }}
  ],
  "sources_consulted": ["string — list of sources used in this analysis"],
  "recommendation": "string — 3-4 sentence strategic recommendation"
}}

IMPORTANT: Return ONLY valid JSON. No markdown, no code fences, no commentary.
Provide realistic, data-informed numbers. If exact data is unavailable, provide reasonable estimates with clear methodology notes.
Generate 3-5 items for trends, competitors, gaps, and barriers each."""


async def analyze_market(user_input: str, context: str = "") -> dict:
    """Run a comprehensive market research analysis with internet access."""
    client = get_client()

    # ── Layer 2: Deep Research Crawler ────────────────────
    research_intel = "No pre-fetched research available."
    if HAS_CRAWLER:
        try:
            research = await deep_research(user_input)
            research_intel = research.get("intelligence_brief", "No findings.")
        except Exception as e:
            research_intel = f"Crawler error: {str(e)[:100]}"

    prompt = MARKET_RESEARCH_PROMPT.format(
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
            "error": "Failed to parse market research response",
            "raw_response": text[:2000],
            "company_name": "Unknown",
            "executive_summary": "Analysis could not be parsed. Please retry.",
            "_citations": citations,
        }


async def stream_market_analysis(user_input: str, context: str = ""):
    """Stream market research analysis chunks via SSE."""
    client = get_client()

    research_intel = "No pre-fetched research available."
    if HAS_CRAWLER:
        try:
            research = await deep_research(user_input)
            research_intel = research.get("intelligence_brief", "No findings.")
        except Exception:
            pass

    prompt = MARKET_RESEARCH_PROMPT.format(
        user_input=user_input,
        context=context or "None provided",
        research_intel=research_intel,
    )

    response = client.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[GROUNDING_TOOL],
            temperature=0.4,
            max_output_tokens=8192,
        )
    )

    for chunk in response:
        if chunk.text:
            yield chunk.text
