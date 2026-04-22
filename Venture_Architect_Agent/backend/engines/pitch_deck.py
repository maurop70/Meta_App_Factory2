import os
import json
from google import genai
from google.genai import types

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())

PROMPT = """You are an elite Venture Architect and Pitch Deck narrative expert.
Using all the provided project context (Market Research, Financials, Unit Economics),
synthesize a world-class 10-slide Investor Pitch Deck narrative.

INPUT:
{user_input}

CONTEXT:
{context}

Produce a JSON response with EXACTLY this structure:
{{
  "deck_title": "string",
  "one_liner": "string",
  "slides": [
    {{
      "slide_number": "number",
      "slide_title": "string (e.g. 'The Problem', 'The Solution', 'Traction')",
      "main_headline": "string — The 1 sentence takeaway for this slide",
      "talking_points": ["string — 3 bullet points to speak to"]
    }}
  ] // Generate exactly 10 slides following standard Sequoia structure
}}
"""

async def generate_pitch_deck(user_input: str, context: str = "") -> dict:
    client = get_client()
    prompt = PROMPT.format(user_input=user_input, context=context or "None")
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[GROUNDING_TOOL],
            temperature=0.6,
            response_mime_type="application/json"
        )
    )
    
    try:
        return json.loads(response.text)
    except Exception:
        return {"error": "Parsing failed", "raw": response.text}
