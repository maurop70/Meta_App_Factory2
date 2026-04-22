import os
import json
from google import genai
from google.genai import types

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())

PROMPT = """You are an elite Venture Architect and GTM Budgeting Specialist.
Map out the capital deployment timeline and translate the CMO's marketing strategy into month-over-month cash burn.

INPUT:
{user_input}

CONTEXT:
{context}

Produce a JSON response with EXACTLY this structure:
{{
  "summary": "string — 2 sentence summary of the GTM budget",
  "total_gtm_budget": "number",
  "monthly_burn_rate": "number",
  "allocation_breakdown": [
    {{
      "category": "string (e.g. 'Paid Ads', 'Sales Hiring', 'Content')",
      "budget": "number",
      "percentage": "number"
    }}
  ],
  "hiring_timeline": [
    {{
      "role": "string",
      "month_to_hire": "number",
      "annual_salary": "number"
    }}
  ],
  "cash_out_date": "string — e.g. 'Month 18'"
}}
"""

async def generate_gtm_budget(user_input: str, context: str = "") -> dict:
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
