import os
import json
from google import genai
from google.genai import types

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())

PROMPT = """You are an elite Venture Architect and Cap Table Modeler.
Using the provided business context, generate a realistic Cap Table (Capitalization Table) and equity distribution simulator.

INPUT:
{user_input}

CONTEXT:
{context}

Produce a JSON response with EXACTLY this structure:
{{
  "summary": "string — 2 sentence summary of equity strategy",
  "founder_split": [
    {{
      "founder": "string",
      "equity_percent": "number"
    }}
  ],
  "esop_pool_percent": "number — Employee Stock Option Pool",
  "funding_rounds": [
    {{
      "round_name": "string (e.g. 'Pre-Seed', 'Seed', 'Series A')",
      "capital_raised": "number",
      "post_money_valuation": "number",
      "dilution_percent": "number",
      "investor_equity_percent": "number"
    }}
  ],
  "final_equity_distribution": [
    {{
      "stakeholder": "string",
      "final_equity_percent": "number"
    }}
  ],
  "recommendations": ["string — 3 strategic equity recommendations"]
}}
"""

async def generate_cap_table(user_input: str, context: str = "") -> dict:
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
