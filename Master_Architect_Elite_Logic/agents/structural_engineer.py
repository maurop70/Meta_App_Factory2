"""
structural_engineer.py — Structural Engineer Agent
════════════════════════════════════════════════════
Master_Architect_Elite_Logic | Triad Agent 1/3

Analyzes DB schemas, API contracts, data models, migration paths,
and port conflicts for proposed architecture changes.
"""

import os
import json
import logging
import requests
from typing import Optional

logger = logging.getLogger("StructuralEngineer")

SYSTEM_PROMPT = """You are the Structural Engineer of the Master Architect Triad.
Your domain: database schemas, API contracts, data models, system structure, and migration paths.

You are reviewing a proposed change to a software factory ecosystem.

Analyze the proposed change and output ONLY a JSON object (no markdown, no backticks):
{
  "domain": "structural",
  "score": <0-100>,
  "schemas_reviewed": ["list of identified DB schemas or data models"],
  "api_contracts": ["list of API endpoints affected"],
  "migration_required": true/false,
  "migration_plan": "brief migration strategy if needed",
  "port_conflicts": ["any port assignment issues"],
  "concerns": ["max 3 architectural concerns"],
  "recommendations": ["max 3 actionable recommendations"]
}

Focus on:
- Data model integrity and normalization
- API endpoint consistency (naming, methods, auth)
- Breaking changes in contracts
- Port collision in the 5005-5104 range
- State management patterns (file-based → SQLite → Postgres paths)
- Input validation (Pydantic models on POST/PUT endpoints)

Be concise. Score 0-100 where 100 = flawless structure, 0 = fundamentally broken.
Use ONLY ASCII characters. Never output anything outside the JSON."""


class StructuralEngineer:
    """
    Triad Agent 1: Analyzes structural integrity of proposed changes.
    Uses Gemini for intelligent analysis with keyword fallback.
    """

    def __init__(self, api_key: str = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model

    def analyze(self, description: str, change_type: str = "feature",
                components: list = None, context: dict = None) -> dict:
        """
        Run structural analysis on a proposed change.
        Returns a verdict dict with score, concerns, and recommendations.
        """
        ai_result = self._ai_analyze(description, change_type, components, context)
        if ai_result:
            return ai_result
        return self._fallback_analyze(description, change_type, components)

    def _ai_analyze(self, description: str, change_type: str,
                    components: list, context: dict) -> Optional[dict]:
        """Use Gemini for intelligent structural analysis."""
        if not self.api_key:
            return None

        prompt = (
            f"CHANGE TYPE: {change_type}\n"
            f"AFFECTED COMPONENTS: {', '.join(components or ['unknown'])}\n"
            f"DESCRIPTION:\n{description[:3000]}\n"
        )
        if context:
            prompt += f"\nADDITIONAL CONTEXT:\n{json.dumps(context, indent=2)[:1000]}\n"
        prompt += "\nProvide your structural engineering review."

        try:
            import re
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n" + prompt}]}
                ],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
            }

            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"Gemini API error: {resp.status_code}")
                return None

            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

            # Extract JSON
            if "```" in text:
                match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
                if match:
                    text = match.group(1).strip()
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                text = text[start:end + 1]
            text = text.encode('ascii', 'replace').decode('ascii')

            result = json.loads(text)
            result["domain"] = "structural"
            result["source"] = "gemini"
            result.setdefault("score", 70)
            result.setdefault("concerns", [])
            result.setdefault("recommendations", [])
            return result

        except Exception as e:
            logger.warning(f"Structural AI analysis failed: {e}")
            return None

    def _fallback_analyze(self, description: str, change_type: str,
                          components: list) -> dict:
        """Keyword-based fallback analysis."""
        desc_lower = description.lower()
        score = 75  # Default

        concerns = []
        recommendations = []

        # Port conflict check
        if "port" in desc_lower:
            concerns.append("Port assignment detected — verify no collision with registry.json")
            score -= 5

        # Schema check
        if any(kw in desc_lower for kw in ["database", "schema", "table", "migration", "sql"]):
            recommendations.append("Include rollback migration for any schema changes")
            if "migration" not in desc_lower:
                concerns.append("Schema change detected without explicit migration plan")
                score -= 10

        # API contract check
        if any(kw in desc_lower for kw in ["endpoint", "api", "route", "rest"]):
            if "validation" not in desc_lower and "pydantic" not in desc_lower:
                concerns.append("API endpoint without explicit input validation")
                score -= 5
            recommendations.append("Ensure Pydantic model for all POST/PUT request bodies")

        # State management check
        if any(kw in desc_lower for kw in ["json file", "file-based", "local state"]):
            recommendations.append("Consider SQLite migration path for file-based state >10K records")

        if change_type == "new_app":
            recommendations.append("Register in registry.json with assigned port from 5005-5104 range")

        return {
            "domain": "structural",
            "source": "keyword_fallback",
            "score": max(0, min(100, score)),
            "schemas_reviewed": [],
            "api_contracts": [],
            "migration_required": "migration" in desc_lower or "schema" in desc_lower,
            "port_conflicts": [],
            "concerns": concerns[:3],
            "recommendations": recommendations[:3],
        }
