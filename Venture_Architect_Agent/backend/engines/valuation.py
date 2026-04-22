import os
import json
from google import genai
from google.genai import types

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())

PROMPT = """You are an elite Venture Architect and Valuation Expert.
Using the provided business context, calculate an early-stage valuation and project exit scenarios.

INPUT:
{user_input}

CONTEXT:
{context}

Produce a JSON response with EXACTLY this structure:
{{
  "summary": "string — 2 sentence summary of valuation logic",
  "current_valuation": {{
    "pre_money": "number",
    "methodology_used": "string (e.g. 'Scorecard', 'Berkus', 'Revenue Multiple')",
    "rationale": "string"
  }},
  "exit_scenarios": [
    {{
      "scenario": "string (e.g. 'Base Case', 'Best Case')",
      "time_horizon_years": "number",
      "exit_valuation": "number",
      "roi_multiple": "number (e.g. 10x)",
      "likely_acquirers": ["string — 3 real companies"]
    }}
  ],
  "valuation_drivers": ["string — 3 things that will increase valuation"]
}}
"""

async def calculate_valuation(user_input: str, context: str = "") -> dict:
    client = get_client()
    prompt = PROMPT.format(user_input=user_input, context=context or "None")
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[GROUNDING_TOOL],
            temperature=0.3,
            response_mime_type="application/json"
        )
    )
    
    try:
        return json.loads(response.text)
    except Exception:
        return {"error": "Parsing failed", "raw": response.text}
