import os
import json
from google import genai
from google.genai import types

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())

PROMPT = """You are an elite Venture Architect specializing in Scenario Modeling and Sensitivity Analysis.
Generate Base, Best, and Worst-case financial trajectories based on different assumptions.

INPUT:
{user_input}

CONTEXT:
{context}

Produce a JSON response with EXACTLY this structure:
{{
  "summary": "string — 2 sentence summary of the risk profile",
  "scenarios": [
    {{
      "scenario": "string (Base, Best, Worst)",
      "assumption_changes": ["string — what changed from baseline"],
      "year_3_revenue": "number",
      "year_3_ebitda": "number",
      "survival_probability_percent": "number"
    }}
  ],
  "sensitivity_variables": [
    {{
      "variable": "string (e.g. 'CAC', 'Churn Rate')",
      "impact_if_worse": "HIGH | MEDIUM | LOW",
      "mitigation_strategy": "string"
    }}
  ]
}}
"""

async def build_scenarios(user_input: str, context: str = "") -> dict:
    client = get_client()
    prompt = PROMPT.format(user_input=user_input, context=context or "None")
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[GROUNDING_TOOL],
            temperature=0.4,
            response_mime_type="application/json"
        )
    )
    
    try:
        return json.loads(response.text)
    except Exception:
        return {"error": "Parsing failed", "raw": response.text}
