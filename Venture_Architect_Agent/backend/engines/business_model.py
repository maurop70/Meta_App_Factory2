import os
import json
from google import genai
from google.genai import types

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())

PROMPT = """You are an elite Venture Architect. Develop the Business Model Canvas.
Use real-time search to find analogous business models.

INPUT:
{user_input}

CONTEXT:
{context}

Produce a JSON response with EXACTLY this structure:
{{
  "customer_segments": ["string"],
  "value_propositions": ["string"],
  "channels": ["string"],
  "customer_relationships": ["string"],
  "revenue_streams": ["string — detailed pricing/revenue model"],
  "key_resources": ["string"],
  "key_activities": ["string"],
  "key_partnerships": ["string"],
  "cost_structure": ["string"]
}}
"""

async def generate_business_model(user_input: str, context: str = "") -> dict:
    client = get_client()
    prompt = PROMPT.format(user_input=user_input, context=context or "None")
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[GROUNDING_TOOL],
            temperature=0.5,
            response_mime_type="application/json"
        )
    )
    
    try:
        return json.loads(response.text)
    except Exception:
        return {"error": "Parsing failed", "raw": response.text}
