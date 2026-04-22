"""
CMO Agent ?" Independent Legacy Verification Engine
????????????????????????????????????????????????????
Audits user-provided legacy documents against pristine
CMO Elite findings. Highlights flawed assumptions and
verifies valid context.
"""

import json
import os
from google import genai
from google.genai import types

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

async def run_legacy_audit(legacy_text: str, cmo_findings_summary: str) -> dict:
    """
    Compares the user's legacy documents against the CMO's findings.
    DO NOT assume the user's legacy documents are correct.
    """
    client = get_client()

    prompt = f"""
You are the CMO Elite. You have generated pristine, world-class strategic findings for a project.
The client has now provided legacy documentation that they were working on before using you.

CRITICAL DIRECTIVE (INDEPENDENT VERIFICATION PROTOCOL):
Do NOT assume the client's legacy documentation is correct. You must verify their information against your pristine findings. 
Identify gaps, flawed assumptions in the legacy docs, and areas where the legacy docs provide valid historical context. 
Your goal is to reconcile the truth, favoring your world-class strategy while absorbing any valuable context the client provided.

CMO ELITE PRISTINE FINDINGS:
{cmo_findings_summary}

CLIENT'S LEGACY DOCUMENTATION (TO BE AUDITED):
{legacy_text}

Analyze the documentation and return a JSON object with the exact following schema:

{{
  "audit_summary": "A 2-3 sentence executive summary of the reconciliation.",
  "flawed_assumptions": [
    {{
      "client_assumption": "What the client assumed in their doc",
      "cmo_correction": "Why it's wrong based on CMO findings, and the strategic correction",
      "severity": "HIGH | MEDIUM | LOW"
    }}
  ],
  "validated_context": [
    "A list of strings noting valuable historical context or data points from the legacy doc that have been validated and adopted into the strategy."
  ],
  "strategic_reconciliation": "A paragraph explaining the final, unified path forward now that the legacy data has been audited against the master strategy."
}}

Respond ONLY with valid, raw JSON. No markdown formatting.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.4,
            response_mime_type="application/json"
        )
    )

    try:
        raw = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        return data
    except Exception as e:
        print(f"Error parsing legacy audit: {e}")
        return {
            "audit_summary": "Failed to parse audit results.",
            "flawed_assumptions": [],
            "validated_context": [],
            "strategic_reconciliation": "Reconciliation failed due to processing error."
        }
