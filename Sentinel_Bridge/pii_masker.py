"""
pii_masker.py — PII & Secrets Safety Filter
════════════════════════════════════════════
Sentinel Bridge | Aether Protocol | Antigravity-AI

Strips sensitive data from notification payloads before they
are sent to external messaging APIs (ntfy, WhatsApp, SMS).

Masks:
- Windows/Unix file paths
- API keys and tokens (hex/base64 strings > 20 chars)
- Email addresses (optionally)
- IP addresses
- Environment variable values
- Internal hostnames and ports
"""

# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

from auto_heal import healed_post, auto_heal, diagnose

def _v3_preflight():
    """V3: Ping Resonance_Watchdog_V3 before execution."""
    if not _V3_AVAILABLE:
        return True
    try:
        import json as _j
        _cfg_path = _os.path.join(_FACTORY_DIR, "resilience_config.json")
        if not _os.path.exists(_cfg_path):
            return True
        with open(_cfg_path) as _f:
            _cfg = _j.load(_f)
        _url = _cfg.get("cloud_health", {}).get("watchdog_url", "")
        if not _url:
            return True
        import requests as _rq
        _r = _rq.get(_url, timeout=5)
        return _r.status_code == 200
    except Exception:
        return False


import re
import logging
from typing import Optional

logger = logging.getLogger("sentinel.pii_masker")

# ── Regex Patterns ───────────────────────────────────────

PATTERNS = {
    # Windows paths: C:\Users\..., D:\Projects\...
    "windows_path": re.compile(
        r'[A-Za-z]:\\(?:[^\s\\:*?"<>|]+\\)*[^\s\\:*?"<>|]*',
    ),

    # Unix paths: /home/user/..., /var/log/...
    "unix_path": re.compile(
        r'(?<!\w)/(?:home|var|tmp|opt|usr|etc|srv|mnt|data|root)'
        r'(?:/[^\s:*?"<>|]+)+',
    ),

    # API keys / tokens: long hex or base64 strings
    "api_key": re.compile(
        r'\b(?:sk-|pk-|api[_-]?key|token|bearer|secret)[_:=\s]*'
        r'[A-Za-z0-9_\-]{20,}\b',
        re.IGNORECASE,
    ),

    # Standalone long hex strings (likely tokens/hashes)
    "hex_token": re.compile(
        r'\b[0-9a-fA-F]{32,}\b',
    ),

    # Long base64 strings (>40 chars, likely credentials)
    "base64_token": re.compile(
        r'\b[A-Za-z0-9+/]{40,}={0,2}\b',
    ),

    # Internal IP addresses (192.168.x.x, 10.x.x.x, 172.x.x.x)
    "internal_ip": re.compile(
        r'\b(?:192\.168\.\d{1,3}\.\d{1,3}'
        r'|10\.\d{1,3}\.\d{1,3}\.\d{1,3}'
        r'|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b',
    ),

    # localhost with port
    "localhost": re.compile(
        r'(?:http://)?localhost:\d{2,5}',
        re.IGNORECASE,
    ),

    # Google Drive paths (specific to this ecosystem)
    "gdrive_path": re.compile(
        r'My Drive\s*\([^)]+\)(?:\\[^\s]+)+',
    ),

    # .env file references
    "env_ref": re.compile(
        r'\.env(?:\.enc|\.local|\.production)?',
    ),
}

# Replacement strings
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
    """

    def __init__(self, mask_emails: bool = False):
        """
        Args:
            mask_emails: If True, also mask email addresses.
                         Default False (emails are often useful in notifications).
        """
        self.mask_emails = mask_emails
        self._patterns = dict(PATTERNS)
        self._masks = dict(MASKS)

        if mask_emails:
            self._patterns["email"] = re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            )
            self._masks["email"] = "[EMAIL_REDACTED]"

    def mask(self, text: str) -> str:
        """
        Apply all masking patterns to the input text.
        Returns sanitized text safe for external delivery.
        """
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
        """
        Recursively mask all string values in a dictionary.
        Returns a new dict with masked values (original is not modified).
        """
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

    def audit(self, text: str) -> list[dict]:
        """
        Return a list of all PII findings in the text.
        Useful for debugging and compliance reporting.
        """
        findings = []
        for name, pattern in self._patterns.items():
            matches = pattern.findall(text)
            if matches:
                findings.append({
                    "type": name,
                    "count": len(matches),
                    "samples": [m[:20] + "…" if len(m) > 20 else m
                                for m in matches[:3]],
                })
        return findings


if __name__ == "__main__":
    masker = PIIMasker()

    tests = [
        r"Error in C:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Meta_App_Factory\refine_engine.py",
        "API key: sk-abc123456789012345678901234567890",
        "Token: a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6",
        "Connect to 192.168.1.100:5009 or localhost:8000",
        "Config in .env.local and .env.production files",
        "Meeting with John at 3pm — safe text, no PII here.",
    ]

    for t in tests:
        masked = masker.mask(t)
        safe = masker.is_safe(t)
        status = "✅ SAFE" if safe else "🔒 MASKED"
        print(f"{status}: {masked}")
        print()
# V3 AUTO-HEAL ACTIVE
