import os
import json
from google import genai
from google.genai import types

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())

PROMPT = """You are an elite Venture Architect specializing in Unit Economics.
Using the provided project context (including CMO's GTM data and CAC estimates if available), 
calculate the core unit economics for this business model.

INPUT:
{user_input}

CONTEXT:
{context}

Produce a JSON response with EXACTLY this structure:
{{
  "summary": "string — 2 sentence summary of unit economics health",
  "arpu": "number — Average Revenue Per User (monthly or annual)",
  "cac": "number — Blended Customer Acquisition Cost",
  "ltv": "number — Lifetime Value of a customer",
  "ltv_cac_ratio": "number — LTV to CAC ratio (e.g. 3.5)",
  "payback_period_months": "number",
  "monthly_churn_percent": "number",
  "gross_margin_percent": "number",
  "key_drivers": ["string — 3 factors that will improve these metrics"],
  "risk_factors": ["string — 2 metrics most likely to fail"]
}}
"""

async def calculate_unit_economics(user_input: str, context: str = "") -> dict:
    client = get_client()
    prompt = PROMPT.format(user_input=user_input, context=context or "None")
    
    response = client.models.generate_content(
        model="gemini-2.5-pro",
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
