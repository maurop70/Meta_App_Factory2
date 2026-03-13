"""
pii_masker.py — PII & Secrets Safety Filter (Global Core)
═══════════════════════════════════════════════════════════
.system_core | Antigravity V3.0 | Venture Studio Inheritance Engine

Canonical implementation — all child projects link here via symlink.
Originally built for Sentinel_Bridge, now promoted to Global Skills.

Strips sensitive data from payloads before external transmission:
- Windows/Unix file paths
- API keys and tokens (hex/base64 > 20 chars)
- Email addresses (optional)
- IP addresses
- Environment variable values
- Internal hostnames and ports
"""

import re
import os
import sys
import logging
from typing import Optional

# ── V3.0 Resilience ──────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, FACTORY_DIR)

logger = logging.getLogger("system_core.pii_masker")

# ── Regex Patterns ───────────────────────────────────────
PATTERNS = {
    "windows_path": re.compile(
        r'[A-Za-z]:\\(?:[^\s\\:*?"<>|]+\\)*[^\s\\:*?"<>|]*',
    ),
    "unix_path": re.compile(
        r'(?<!\w)/(?:home|var|tmp|opt|usr|etc|srv|mnt|data|root)'
        r'(?:/[^\s:*?"<>|]+)+',
    ),
    "api_key": re.compile(
        r'\b(?:sk-|pk-|api[_-]?key|token|bearer|secret)[_:=\s]*'
        r'[A-Za-z0-9_\-]{20,}\b',
        re.IGNORECASE,
    ),
    "hex_token": re.compile(r'\b[0-9a-fA-F]{32,}\b'),
    "base64_token": re.compile(r'\b[A-Za-z0-9+/]{40,}={0,2}\b'),
    "internal_ip": re.compile(
        r'\b(?:192\.168\.\d{1,3}\.\d{1,3}'
        r'|10\.\d{1,3}\.\d{1,3}\.\d{1,3}'
        r'|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b',
    ),
    "localhost": re.compile(r'(?:http://)?localhost:\d{2,5}', re.IGNORECASE),
    "gdrive_path": re.compile(r'My Drive\s*\([^)]+\)(?:\\[^\s]+)+'),
    "env_ref": re.compile(r'\.env(?:\.enc|\.local|\.production)?'),
}

MASKS = {
    "windows_path": "[PATH_REDACTED]",
    "unix_path": "[PATH_REDACTED]",
    "api_key": "[KEY_REDACTED]",
    "hex_token": "[TOKEN_REDACTED]",
    "base64_token": "[TOKEN_REDACTED]",
    "internal_ip": "[IP_REDACTED]",
    "localhost": "[LOCAL_ENDPOINT]",
    "gdrive_path": "[DRIVE_PATH_REDACTED]",
    "env_ref": "[ENV_FILE]",
}


class PIIMasker:
    """
    Safety filter that strips sensitive data from text before
    it reaches external messaging APIs.

    Usage:
        from system_core import PIIMasker
        masker = PIIMasker()
        clean = masker.mask("Token: sk-abc123...")
    """

    def __init__(self, mask_emails: bool = False):
        self.mask_emails = mask_emails
        self._patterns = dict(PATTERNS)
        self._masks = dict(MASKS)

        if mask_emails:
            self._patterns["email"] = re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            )
            self._masks["email"] = "[EMAIL_REDACTED]"

    def mask(self, text: str) -> str:
        """Apply all masking patterns. Returns sanitized text."""
        if not text:
            return text
        masked = text
        redactions = 0
        for name, pattern in self._patterns.items():
            replacement = self._masks.get(name, "[REDACTED]")
            new_text = pattern.sub(replacement, masked)
            if new_text != masked:
                count = masked.count(replacement) if replacement in masked else 0
                new_count = new_text.count(replacement)
                redactions += new_count - count
                masked = new_text
        if redactions > 0:
            logger.info("PII Masker: %d redaction(s) applied", redactions)
        return masked

    def mask_dict(self, data: dict) -> dict:
        """Recursively mask all string values in a dictionary."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.mask(value)
            elif isinstance(value, dict):
                result[key] = self.mask_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self.mask(item) if isinstance(item, str)
                    else self.mask_dict(item) if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def is_safe(self, text: str) -> bool:
        """Check if text contains any PII/sensitive data."""
        for pattern in self._patterns.values():
            if pattern.search(text):
                return False
        return True

    def audit(self, text: str) -> list:
        """Return a list of all PII findings for compliance."""
        findings = []
        for name, pattern in self._patterns.items():
            matches = pattern.findall(text)
            if matches:
                findings.append({
                    "type": name,
                    "count": len(matches),
                    "samples": [m[:20] + "…" if len(m) > 20 else m for m in matches[:3]],
                })
        return findings


if __name__ == "__main__":
    masker = PIIMasker()
    tests = [
        r"Error in C:\Users\mpetr\Agents\factory.py",
        "API key: sk-abc123456789012345678901234567890",
        "Connect to 192.168.1.100:5009 or localhost:8000",
        "Safe text — no PII here.",
    ]
    for t in tests:
        masked = masker.mask(t)
        safe = masker.is_safe(t)
        status = "✅ SAFE" if safe else "🔒 MASKED"
        print(f"{status}: {masked}")
