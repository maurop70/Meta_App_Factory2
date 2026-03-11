"""
skill_gap_analyzer.py -- GeoTalent Forward Scout: Skill Gap Analysis
=====================================================================
Meta App Factory | GeoTalent-Scout | Antigravity-AI

Scans MASTER_INDEX.md to identify which agents have the most
Level 4-5 errors and recommends new skills to address them.
Unaddressed gaps escalate to the Sunday Leitner Deep Review.
"""

import os
import sys
import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter, defaultdict

logger = logging.getLogger("geotalent.skillgap")

SCRIPT_DIR = Path(__file__).resolve().parent
FACTORY_DIR = SCRIPT_DIR.parent.parent  # Aether/GeoTalent-Scout -> Meta_App_Factory
sys.path.insert(0, str(FACTORY_DIR))
sys.path.insert(0, str(FACTORY_DIR / "Sentinel_Bridge"))

MASTER_INDEX_PATH = FACTORY_DIR / "MASTER_INDEX.md"
STATE_DIR = FACTORY_DIR / ".Gemini_state"
GAPS_STATE_PATH = STATE_DIR / "skill_gaps.json"

# Lazy imports
_pii = None


def _get_pii():
    global _pii
    if _pii is None:
        try:
            from pii_masker import PIIMasker
            _pii = PIIMasker()
        except ImportError:
            logger.warning("PIIMasker not available")
    return _pii


# ── Skill Recommendations Knowledge Base ─────────────────

SKILL_RECOMMENDATIONS = {
    "jsx_parse": {
        "trigger_patterns": ["jsx", "babel", "parse error", "react"],
        "skill": "JSX/React Syntax Validator",
        "description": "Add AST-level JSX validation before writing React files",
    },
    "null_handling": {
        "trigger_patterns": ["nonetype", "none", "null", "undefined", "missing"],
        "skill": "Null-Safety Guard",
        "description": "Implement defensive null checks across data pipelines",
    },
    "auth_management": {
        "trigger_patterns": ["401", "unauthorized", "token", "credential", "auth"],
        "skill": "Credential Lifecycle Manager",
        "description": "Auto-refresh expired tokens with vault integration",
    },
    "context_awareness": {
        "trigger_patterns": ["context", "missing data", "not connected", "disconnected"],
        "skill": "Cross-Module Context Injector",
        "description": "Ensure all UI tabs share context with AI chat components",
    },
    "api_stability": {
        "trigger_patterns": ["api", "endpoint", "crash", "500", "server error"],
        "skill": "API Resilience Layer",
        "description": "Add circuit breakers and graceful degradation to all endpoints",
    },
    "classification": {
        "trigger_patterns": ["unknown", "unrecognized", "classify", "pattern"],
        "skill": "Pattern Classification Expander",
        "description": "Expand NerveCenter REMEDY_LIBRARY with new failure signatures",
    },
    "tone_management": {
        "trigger_patterns": ["tone", "rejected", "notification", "style"],
        "skill": "Adaptive Tone Calibrator",
        "description": "Expand EQ Engine tone profiles based on feedback data",
    },
}


class SkillGapAnalyzer:
    """
    Analyzes MASTER_INDEX.md to find skill gaps across the agent network.
    """

    def __init__(self):
        self._gaps: list = []
        self._state = self._load_state()
        self._pii = _get_pii()

    def _load_state(self) -> dict:
        if GAPS_STATE_PATH.exists():
            try:
                return json.loads(GAPS_STATE_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"gaps": [], "last_scan": None, "scan_count": 0}

    def _save_state(self) -> None:
        STATE_DIR.mkdir(exist_ok=True)
        try:
            GAPS_STATE_PATH.write_text(json.dumps(self._state, indent=2))
        except Exception as e:
            logger.error("Could not save skill gap state: %s", e)

    # ── Core: Scan MASTER_INDEX ──────────────────────────

    def scan_errors(self) -> list:
        """
        Parse MASTER_INDEX.md for ERROR_ENTRY items.
        Returns list of parsed error dicts.
        """
        if not MASTER_INDEX_PATH.exists():
            logger.warning("MASTER_INDEX.md not found")
            return []

        content = MASTER_INDEX_PATH.read_text(encoding="utf-8")

        # Parse ERROR_ENTRY blocks
        entries = []
        blocks = re.split(r'### ERROR_ENTRY', content)

        for block in blocks[1:]:  # Skip header
            entry = {}
            for field in ["Timestamp", "App", "Error_Complexity",
                          "Description", "Root_Cause", "Resolution",
                          "Status", "Last_Reviewed"]:
                match = re.search(
                    rf'\*\*{field}:\*\*\s*(.+?)(?:\n|$)', block
                )
                if match:
                    entry[field.lower()] = match.group(1).strip()

            # Parse complexity as int
            try:
                entry["complexity"] = int(entry.get("error_complexity", "1"))
            except ValueError:
                entry["complexity"] = 1

            if entry.get("app"):
                entries.append(entry)

        return entries

    # ── Core: Analyze Gaps ───────────────────────────────

    def analyze(self) -> dict:
        """
        Full skill gap analysis:
        1. Parse errors from MASTER_INDEX
        2. Filter Level 4-5
        3. Aggregate by app/agent
        4. Recommend skills
        5. Return report
        """
        errors = self.scan_errors()

        # Filter high-complexity
        critical_errors = [e for e in errors if e.get("complexity", 1) >= 4]
        open_errors = [e for e in critical_errors
                       if e.get("status", "").upper() not in ("RESOLVED",)]

        # Aggregate by app
        app_errors = defaultdict(list)
        for err in critical_errors:
            app_errors[err["app"]].append(err)

        # Identify skill gaps
        gaps = []
        for app, app_errs in app_errors.items():
            descriptions = " ".join(
                e.get("description", "") + " " + e.get("root_cause", "")
                for e in app_errs
            ).lower()

            matched_skills = []
            for skill_id, skill in SKILL_RECOMMENDATIONS.items():
                for pattern in skill["trigger_patterns"]:
                    if pattern in descriptions:
                        matched_skills.append({
                            "skill_id": skill_id,
                            "skill_name": skill["skill"],
                            "description": skill["description"],
                            "matched_pattern": pattern,
                        })
                        break

            if matched_skills:
                gaps.append({
                    "app": app,
                    "error_count": len(app_errs),
                    "open_count": len([e for e in app_errs
                                       if e.get("status", "").upper() != "RESOLVED"]),
                    "max_complexity": max(e.get("complexity", 1) for e in app_errs),
                    "recommended_skills": matched_skills,
                })

        # PII-mask the report
        if self._pii:
            for gap in gaps:
                gap["app"] = self._pii.mask(gap["app"])

        self._gaps = gaps

        # Update state
        self._state["gaps"] = gaps
        self._state["last_scan"] = datetime.now(timezone.utc).isoformat()
        self._state["scan_count"] = self._state.get("scan_count", 0) + 1
        self._save_state()

        report = {
            "total_errors": len(errors),
            "critical_errors": len(critical_errors),
            "open_critical": len(open_errors),
            "apps_with_gaps": len(gaps),
            "gaps": gaps,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }

        return report

    # ── Leitner Escalation ───────────────────────────────

    def escalate_unaddressed(self) -> int:
        """
        Escalate unaddressed skill gaps to MASTER_INDEX Level 5
        for the Sunday Deep Review.
        """
        escalated = 0
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        for gap in self._gaps:
            if gap.get("open_count", 0) > 0:
                skills = ", ".join(
                    s["skill_name"] for s in gap.get("recommended_skills", [])
                )
                entry = (
                    f"\n### ERROR_ENTRY\n"
                    f"- **Timestamp:** {timestamp}\n"
                    f"- **App:** GeoTalent_Scout\n"
                    f"- **Error_Complexity:** 5\n"
                    f"- **Description:** Skill gap unaddressed in {gap['app']}: {skills}\n"
                    f"- **Root_Cause:** {gap['open_count']} open Level 4-5 errors without required skills\n"
                    f"- **Resolution:** pending_deep_review\n"
                    f"- **Status:** OPEN\n"
                    f"- **Last_Reviewed:** {timestamp}\n"
                )

                try:
                    with open(MASTER_INDEX_PATH, "a", encoding="utf-8",
                              newline="\n") as f:
                        f.write(entry)
                    escalated += 1
                except Exception as e:
                    logger.error("Escalation failed: %s", e)

        return escalated

    def get_gaps(self) -> list:
        """Return current skill gaps."""
        return self._gaps or self._state.get("gaps", [])


# ── Entry Point ──────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(description="GeoTalent Skill Gap Analyzer")
    parser.add_argument("--test", action="store_true", help="Run analysis")
    args = parser.parse_args()

    analyzer = SkillGapAnalyzer()

    if args.test:
        print("GeoTalent Skill Gap Analyzer -- Scan")
        print("-" * 50)

        report = analyzer.analyze()
        print(f"Total errors in MASTER_INDEX: {report['total_errors']}")
        print(f"Critical (Level 4-5): {report['critical_errors']}")
        print(f"Open critical: {report['open_critical']}")
        print(f"Apps with skill gaps: {report['apps_with_gaps']}")

        for gap in report["gaps"]:
            print(f"\n  App: {gap['app']}")
            print(f"  Errors: {gap['error_count']} "
                  f"(open: {gap['open_count']})")
            for skill in gap["recommended_skills"]:
                print(f"    -> {skill['skill_name']}: {skill['description']}")

        print("\nDone!")
    else:
        print("Use --test to run skill gap analysis.")
