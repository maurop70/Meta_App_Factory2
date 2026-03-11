"""
leitner_architect.py — Leitner Error Prioritization Architect
══════════════════════════════════════════════════════════════
Meta App Factory | Aether Protocol | Antigravity-AI

Cross-references past high-complexity errors against current app
source code to detect architectural regression patterns. Uses the
Leitner spaced-repetition model: harder lessons are reviewed more
frequently (Level 4-5 every 72 hours).
"""

import os
import sys
import re
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("LeitnerArchitect")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_INDEX_PATH = os.path.join(SCRIPT_DIR, "MASTER_INDEX.md")
REGISTRY_PATH = os.path.join(SCRIPT_DIR, "registry.json")
STATE_DIR = os.path.join(SCRIPT_DIR, ".Gemini_state")
WARNINGS_PATH = os.path.join(STATE_DIR, "system_warnings.json")

# ── Complexity Rating Heuristics ─────────────────────────

# Keywords that suggest higher complexity
SEVERITY_KEYWORDS = {
    5: ["security", "credential", "auth", "injection", "xss", "data loss",
        "regression", "systemic", "production down", "corruption"],
    4: ["architectural", "design flaw", "race condition", "memory leak",
        "deadlock", "data integrity", "breaking change", "circular"],
    3: ["logic bug", "state", "async", "timing", "duplicate", "missing check",
        "edge case", "null", "undefined"],
    2: ["import", "missing", "typo", "css", "style", "layout", "format",
        "encoding", "path"],
    1: ["config", "whitespace", "comment", "naming", "docs", "readme"],
}

# Patterns that indicate architectural issues in source code
REGRESSION_PATTERNS = {
    "hardcoded_credentials": r"""(?:api_key|password|secret|token)\s*=\s*['\"][^'\"]{8,}""",
    "missing_error_handling": r"""(?:requests\.(?:get|post|put|delete)|fetch\(|httpx\.)(?:(?!try|except|catch|\.catch).)*$""",
    "no_dotenv": r"""os\.getenv\((?:(?!load_dotenv).)*$""",
    "strict_mode_sse": r"""StrictMode.*(?:getReader|EventSource|event-stream)""",
    "dangerouslySetInnerHTML": r"""dangerouslySetInnerHTML(?:(?!DOMPurify).)*$""",
    "unclosed_resources": r"""(?:open\(|connect\()(?:(?!with |\.close\(\)|finally).)*$""",
}


class LeitnerArchitect:
    """
    The Specialist — Architect module for Leitner Error Prioritization.
    Cross-references current builds against historical high-complexity
    failures to prevent architectural regression.
    """

    def __init__(self):
        self._ensure_state_dir()

    def _ensure_state_dir(self):
        os.makedirs(STATE_DIR, exist_ok=True)

    # ── Error Registry Parser ────────────────────────────

    def load_error_registry(self) -> List[dict]:
        """Parse the ERROR_REGISTRY section from MASTER_INDEX.md."""
        if not os.path.isfile(MASTER_INDEX_PATH):
            return []

        try:
            with open(MASTER_INDEX_PATH, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Could not read MASTER_INDEX: {e}")
            return []

        # Find the ERROR_REGISTRY section
        registry_match = re.search(
            r"## ERROR_REGISTRY\s*\n(.*?)(?=\n## (?!ERROR_ENTRY)|$)",
            content,
            re.DOTALL,
        )
        if not registry_match:
            return []

        registry_text = registry_match.group(1)
        entries = []

        # Parse individual ERROR_ENTRY blocks
        entry_blocks = re.findall(
            r"### ERROR_ENTRY\s*\n(.*?)(?=\n### ERROR_ENTRY|\n## |$)",
            registry_text,
            re.DOTALL,
        )

        for block in entry_blocks:
            entry = {}
            for line in block.strip().split("\n"):
                line = line.strip()
                if line.startswith("- **") and ":**" in line:
                    key_match = re.match(r"- \*\*(.+?):\*\*\s*(.*)", line)
                    if key_match:
                        key = key_match.group(1).strip().lower().replace(" ", "_")
                        value = key_match.group(2).strip()
                        entry[key] = value
            if entry:
                # Parse complexity as int
                try:
                    entry["error_complexity"] = int(entry.get("error_complexity", "2"))
                except ValueError:
                    entry["error_complexity"] = 2
                entries.append(entry)

        return entries

    def get_high_complexity_errors(self, min_level: int = 4) -> List[dict]:
        """Return only errors at or above the specified complexity level."""
        return [e for e in self.load_error_registry()
                if e.get("error_complexity", 0) >= min_level]

    # ── Complexity Rating ────────────────────────────────

    @staticmethod
    def rate_complexity(description: str, context: str = "") -> int:
        """
        Auto-assign 1-5 complexity based on heuristic keyword matching.
        Higher severity keywords win if multiple match.
        """
        combined = f"{description} {context}".lower()
        for level in sorted(SEVERITY_KEYWORDS.keys(), reverse=True):
            for keyword in SEVERITY_KEYWORDS[level]:
                if keyword in combined:
                    return level
        return 2  # Default: minor

    # ── Cross-Reference Engine ───────────────────────────

    def cross_reference(
        self, error_entry: dict, app_source_files: Dict[str, str]
    ) -> Optional[dict]:
        """
        Scan current source code for patterns that match a past
        high-complexity failure. Returns a warning dict or None.

        Strategy:
        1. Extract keywords from the error description/root_cause
        2. Check for matching REGRESSION_PATTERNS in source
        3. Check for direct keyword matches in source code
        """
        description = error_entry.get("description", "")
        root_cause = error_entry.get("root_cause", "")
        error_text = f"{description} {root_cause}".lower()

        matches = []

        # Strategy 1: Check regression patterns
        for pattern_name, pattern in REGRESSION_PATTERNS.items():
            # Only check patterns relevant to this error
            relevance = self._pattern_relevant_to_error(pattern_name, error_text)
            if not relevance:
                continue

            for rel_path, content in app_source_files.items():
                try:
                    found = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
                    if found:
                        matches.append({
                            "type": "regression_pattern",
                            "pattern": pattern_name,
                            "file": rel_path,
                            "occurrences": len(found),
                            "sample": found[0][:100] if found else "",
                        })
                except re.error:
                    continue

        # Strategy 2: Direct keyword matching from error context
        error_keywords = self._extract_error_keywords(error_text)
        for rel_path, content in app_source_files.items():
            content_lower = content.lower()
            for keyword in error_keywords:
                if keyword in content_lower:
                    # Find the line number
                    for i, line in enumerate(content.split("\n"), 1):
                        if keyword in line.lower():
                            matches.append({
                                "type": "keyword_match",
                                "keyword": keyword,
                                "file": rel_path,
                                "line": i,
                                "context": line.strip()[:120],
                            })
                            break  # One match per keyword per file

        if matches:
            return {
                "error_id": error_entry.get("timestamp", "unknown"),
                "error_description": description,
                "error_complexity": error_entry.get("error_complexity", 0),
                "app": error_entry.get("app", "unknown"),
                "matches": matches[:10],  # Cap at 10 matches
                "severity": "HIGH" if error_entry.get("error_complexity", 0) >= 4 else "MEDIUM",
                "recommendation": (
                    f"Architectural regression detected: current code contains patterns "
                    f"similar to past Level {error_entry.get('error_complexity', '?')} error. "
                    f"Review {len(matches)} match(es) before deploying."
                ),
            }
        return None

    def _pattern_relevant_to_error(self, pattern_name: str, error_text: str) -> bool:
        """Check if a regression pattern is relevant to the error description."""
        relevance_map = {
            "hardcoded_credentials": ["credential", "secret", "key", "auth", "token"],
            "missing_error_handling": ["error", "exception", "crash", "unhandled"],
            "no_dotenv": ["env", "environment", "config", "dotenv", "getenv"],
            "strict_mode_sse": ["strict", "sse", "streaming", "duplicate", "double"],
            "dangerouslySetInnerHTML": ["xss", "injection", "html", "sanitiz"],
            "unclosed_resources": ["resource", "leak", "file", "connection", "close"],
        }
        keywords = relevance_map.get(pattern_name, [])
        return any(k in error_text for k in keywords)

    def _extract_error_keywords(self, error_text: str) -> List[str]:
        """Extract meaningful keywords from error text for code searching."""
        # Remove common stop words
        stop_words = {
            "the", "a", "an", "is", "was", "are", "were", "in", "on", "at",
            "to", "for", "of", "with", "and", "or", "not", "this", "that",
            "it", "be", "has", "had", "have", "from", "by", "but", "error",
            "bug", "issue", "problem", "fix", "fixed",
        }
        words = re.findall(r"[a-z_]{4,}", error_text)
        keywords = [w for w in words if w not in stop_words]
        # Return unique keywords, max 8
        seen = set()
        unique = []
        for k in keywords:
            if k not in seen:
                seen.add(k)
                unique.append(k)
        return unique[:8]

    # ── System Warning Management ────────────────────────

    def issue_warning(self, warning: dict) -> None:
        """Write a System Warning to .Gemini_state/system_warnings.json."""
        self._ensure_state_dir()
        warnings = self._load_warnings()
        warning["timestamp"] = datetime.now(timezone.utc).isoformat()
        warning["status"] = "ACTIVE"
        warnings.append(warning)

        try:
            with open(WARNINGS_PATH, "w", encoding="utf-8", newline="\n") as f:
                json.dump(warnings, f, indent=2)
            logger.info(f"System Warning issued: {warning.get('recommendation', '')[:80]}")
        except Exception as e:
            logger.error(f"Could not write system warning: {e}")

    def _load_warnings(self) -> List[dict]:
        """Load existing system warnings."""
        if not os.path.isfile(WARNINGS_PATH):
            return []
        try:
            with open(WARNINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return []

    def get_active_warnings(self) -> List[dict]:
        """Return only active warnings."""
        return [w for w in self._load_warnings() if w.get("status") == "ACTIVE"]

    def dismiss_warning(self, timestamp: str) -> bool:
        """Mark a warning as dismissed by its timestamp."""
        warnings = self._load_warnings()
        found = False
        for w in warnings:
            if w.get("timestamp") == timestamp:
                w["status"] = "DISMISSED"
                w["dismissed_at"] = datetime.now(timezone.utc).isoformat()
                found = True
                break
        if found:
            try:
                with open(WARNINGS_PATH, "w", encoding="utf-8", newline="\n") as f:
                    json.dump(warnings, f, indent=2)
            except Exception:
                pass
        return found

    # ── Full Review Cycle ────────────────────────────────

    def run_deep_review(self, min_level: int = 4) -> List[dict]:
        """
        Execute a full deep review cycle:
        1. Load Level 4-5 errors from MASTER_INDEX
        2. Load all active apps from registry
        3. Cross-reference each error against each app's source
        4. Issue System Warnings for any matches
        Returns list of warnings issued.
        """
        high_errors = self.get_high_complexity_errors(min_level)
        if not high_errors:
            logger.info("Deep Review: No high-complexity errors found.")
            return []

        # Load active apps from registry
        apps = self._load_active_apps()
        if not apps:
            logger.info("Deep Review: No active apps found in registry.")
            return []

        warnings_issued = []

        for error in high_errors:
            for app_name, app_dir in apps.items():
                try:
                    # Import discover_app_files from refine_engine
                    sys.path.insert(0, SCRIPT_DIR)
                    from refine_engine import discover_app_files
                    source_files = discover_app_files(app_dir)
                    if not source_files:
                        continue

                    warning = self.cross_reference(error, source_files)
                    if warning:
                        warning["reviewed_app"] = app_name
                        warning["review_type"] = "deep_review_72h"
                        self.issue_warning(warning)
                        warnings_issued.append(warning)
                except Exception as e:
                    logger.warning(f"Deep review error for {app_name}: {e}")

        return warnings_issued

    def _load_active_apps(self) -> Dict[str, str]:
        """Load active app directories from registry.json."""
        if not os.path.isfile(REGISTRY_PATH):
            return {}
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            apps = {}
            for name, info in data.get("apps", {}).items():
                if info.get("status") != "active":
                    continue
                # Resolve app directory
                app_path = info.get("path", "")
                if app_path:
                    full = os.path.join(os.path.dirname(SCRIPT_DIR), app_path)
                else:
                    full = os.path.join(SCRIPT_DIR, name)
                if os.path.isdir(full):
                    apps[name] = full
            return apps
        except Exception as e:
            logger.warning(f"Could not load registry: {e}")
            return {}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    architect = LeitnerArchitect()

    # Quick test: load error registry
    errors = architect.load_error_registry()
    print(f"Loaded {len(errors)} error entries from MASTER_INDEX")

    high = architect.get_high_complexity_errors(4)
    print(f"High-complexity (L4+): {len(high)} entries")

    # Test complexity rating
    print(f"Rate 'security credential leak': {architect.rate_complexity('security credential leak')}")
    print(f"Rate 'missing import css': {architect.rate_complexity('missing import css')}")
    print(f"Rate 'race condition in async': {architect.rate_complexity('race condition in async')}")
