import os
import json
from google import genai
from google.genai import types

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())

def _clean_json_text(text: str) -> str:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    return text

FINANCIAL_PROMPT = """You are an elite Venture Architect and CFO. 
You have access to real-time internet search to find benchmark SaaS metrics, cloud hosting costs, and typical salary data.

Given the business context, generate a 5-Year Financial Projection model.

INPUT:
{user_input}

CONTEXT:
{context}

Produce a JSON response with EXACTLY this structure:
{{
  "currency": "USD",
  "summary": "string — 2-3 sentence overview of the financial trajectory",
  "yearly_projections": [
    {{
      "year": 1,
      "revenue": "number",
      "cogs": "number — Cost of Goods Sold / Cloud Infrastructure",
      "gross_margin_percent": "number",
      "opex": "number — Operating Expenses (Payroll, Marketing, R&D)",
      "ebitda": "number",
      "cash_flow": "number",
      "headcount": "number"
    }}
  ] // generate for years 1 through 5
}}
"""

async def generate_financials(user_input: str, context: str = "") -> dict:
    client = get_client()
    prompt = FINANCIAL_PROMPT.format(user_input=user_input, context=context or "None")
    
    response = client.models.generate_content(
        model="gemini-2.5-pro",
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
