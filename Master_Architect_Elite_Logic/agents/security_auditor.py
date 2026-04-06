"""
security_auditor.py — Security Auditor Agent
══════════════════════════════════════════════
Master_Architect_Elite_Logic | Triad Agent 3/3

Analyzes Deploy Shield compliance, credential management,
PII exposure, CORS/auth patterns, and dependency CVEs.
"""

import os
import json
import logging
import requests
from typing import Optional

logger = logging.getLogger("SecurityAuditor")

SYSTEM_PROMPT = """You are the Security Auditor of the Master Architect Triad.
Your domain: security compliance, credential management, PII protection, and deploy safety.

You are reviewing a proposed change to a software factory ecosystem that uses:
- Fernet vault for encrypted secret storage (vault.enc)
- .env files for development-only secrets
- CORS whitelist for frontend origins
- PII masking for logs and responses
- Phantom QA Gate for pre-deployment compliance

Analyze the proposed change and output ONLY a JSON object (no markdown, no backticks):
{
  "domain": "security",
  "score": <0-100>,
  "credential_exposure": ["any hardcoded secrets or insecure key handling"],
  "pii_risks": ["personal data exposure vectors"],
  "cors_valid": true/false,
  "auth_coverage": "full" or "partial" or "none",
  "deploy_shield_status": "PASS" or "WARN" or "FAIL",
  "dependency_risks": ["known CVE or outdated package concerns"],
  "concerns": ["max 3 security concerns"],
  "recommendations": ["max 3 actionable security recommendations"]
}

Focus on:
- Hardcoded secrets, API keys, or tokens in source code
- Secrets accessed via os.getenv() without vault_client fallback
- PII in logs, responses, or error messages
- CORS origin whitelist (must be explicit, not *)
- Authentication on mutation endpoints (POST/PUT/DELETE)
- Input sanitization and SQL injection prevention
- Dependency versions with known vulnerabilities

Score 0-100 where 100 = fortress security, 0 = critically exposed.
Use ONLY ASCII characters."""


class SecurityAuditor:
    """
    Triad Agent 3: Analyzes security posture of proposed changes.
    Uses Gemini for intelligent analysis with keyword fallback.
    """

    def __init__(self, api_key: str = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model

    def analyze(self, description: str, change_type: str = "feature",
                components: list = None, context: dict = None) -> dict:
        ai_result = self._ai_analyze(description, change_type, components, context)
        if ai_result:
            return ai_result
        return self._fallback_analyze(description, change_type, components)

    def _ai_analyze(self, description: str, change_type: str,
                    components: list, context: dict) -> Optional[dict]:
        if not self.api_key:
            return None

        prompt = (
            f"CHANGE TYPE: {change_type}\n"
            f"AFFECTED COMPONENTS: {', '.join(components or ['unknown'])}\n"
            f"DESCRIPTION:\n{description[:3000]}\n"
        )
        if context:
            prompt += f"\nADDITIONAL CONTEXT:\n{json.dumps(context, indent=2)[:1000]}\n"
        prompt += "\nProvide your security audit review."

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
                return None

            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

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
            result["domain"] = "security"
            result["source"] = "gemini"
            result.setdefault("score", 70)
            result.setdefault("concerns", [])
            result.setdefault("recommendations", [])
            return result

        except Exception as e:
            logger.warning(f"Security Auditor AI analysis failed: {e}")
            return None

    def _fallback_analyze(self, description: str, change_type: str,
                          components: list) -> dict:
        desc_lower = description.lower()
        score = 80
        concerns = []
        recommendations = []

        # Credential check
        if any(kw in desc_lower for kw in ["key", "secret", "token", "password", "credential"]):
            recommendations.append("Use vault_client.get_secret() instead of direct os.getenv()")
            if any(kw in desc_lower for kw in ["hardcode", "plain", "string"]):
                concerns.append("Possible hardcoded credential detected")
                score -= 25

        # PII check
        if any(kw in desc_lower for kw in ["email", "name", "phone", "address", "personal", "user data"]):
            concerns.append("PII handling detected — ensure masking in logs and error responses")
            recommendations.append("Apply PII regex masking before any logging or external transmission")
            score -= 5

        # CORS check
        if any(kw in desc_lower for kw in ["cors", "origin", "cross-origin"]):
            if "*" in desc_lower:
                concerns.append("Wildcard CORS origin detected — restrict to explicit localhost ports")
                score -= 15
            else:
                recommendations.append("Verify CORS origins include only necessary localhost ports")

        # Auth check
        if any(kw in desc_lower for kw in ["post", "put", "delete", "mutation", "write"]):
            if "auth" not in desc_lower and "token" not in desc_lower:
                concerns.append("Mutation endpoint without explicit authentication check")
                score -= 10

        # Dependency check
        if any(kw in desc_lower for kw in ["install", "pip", "npm", "dependency", "package"]):
            recommendations.append("Audit new dependencies for known CVEs before deployment")

        return {
            "domain": "security",
            "source": "keyword_fallback",
            "score": max(0, min(100, score)),
            "credential_exposure": [],
            "pii_risks": [],
            "cors_valid": "*" not in desc_lower,
            "auth_coverage": "partial",
            "deploy_shield_status": "PASS" if score >= 70 else "WARN" if score >= 50 else "FAIL",
            "dependency_risks": [],
            "concerns": concerns[:3],
            "recommendations": recommendations[:3],
        }
