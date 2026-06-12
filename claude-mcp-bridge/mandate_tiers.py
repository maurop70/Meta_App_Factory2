"""
Risk-Tier Classifier — CLAUDE_RULES.md Section 15
--------------------------------------------------
Classifies a mandate INSTRUCTION (never the full rule-injected prompt —
the rules text always contains gate words like "deploy" and would
permanently false-positive) into autonomy tiers:

  TIER 0 — read-only diagnosis           → full autonomy
  TIER 1 — local workspace mutation      → autonomy + Auditor check
  TIER 2 — version control (add/commit/push) → autonomy + ledger verification
  TIER 3 — irreversible / outward-facing → operator approval required

Replaces the legacy keyword scan of loop_engine.requires_user_input(),
which scanned the entire mandate (including injected CLAUDE_RULES.md)
and therefore tripped on every iteration.

The classifier is deliberately conservative: the HIGHEST tier matched
wins, and unrecognized instructions default to Tier 1 (mutation assumed).
"""

import re
from dataclasses import dataclass, field

# Patterns are matched case-insensitively with word boundaries where
# meaningful. Order within a tier does not matter — highest tier wins.

_TIER3_PATTERNS: list[tuple[str, str]] = [
    (r"\bdeploy(?:ing|ment)?\b.{0,40}\b(?:prod|production|digitalocean|droplet|live)\b",
     "production deployment"),
    (r"\b(?:run|execute|launch)\b.{0,30}\bdeploy_(?:erp|maf)\.py\b", "deploy script execution"),
    (r"\bdeploy_(?:erp|maf)\.py\b", "deploy script referenced as action target"),
    (r"\bdeploy\b(?!\w)", "deployment requested"),
    (r"\b(?:migrate|migration)\b.{0,40}\b(?:prod|production|live|remote)\b",
     "live schema migration"),
    (r"\bmerge\b.{0,30}\b(?:into|to)\b.{0,10}\bmain\b", "merge to main"),
    (r"\b(?:delete|drop|truncate|wipe|purge|overwrite)\b.{0,50}\b(?:table|database|db|data|records?|users?)\b",
     "data deletion/overwrite"),
    (r"\bnew\b.{0,20}\bchild\s+app\b", "new child app"),
    (r"\b(?:update|change|modify|append)\b.{0,30}\b(?:claude_rules|permanent rules|rulebook)\b",
     "rule change"),
    (r"\b(?:rm\s+-rf|format\s+[a-z]:|mkfs)\b", "destructive OS command"),
]

_TIER2_PATTERNS: list[tuple[str, str]] = [
    (r"\bgit\s+(?:add|commit|push)\b", "git mutation"),
    (r"\b(?:commit|push)\b.{0,30}\b(?:branch|repo|github|origin|dev|main)\b", "version control"),
    (r"\bseal\b.{0,30}\b(?:version control|git)\b", "git seal"),
]

_TIER1_PATTERNS: list[tuple[str, str]] = [
    (r"\b(?:fix|repair|patch|implement|build|create|write|edit|modify|refactor|add|remove|rename|update)\b",
     "local mutation verb"),
    (r"\b(?:install|npm|pip)\b", "dependency change"),
    (r"\brestart\b.{0,40}\b(?:local|localhost|127\.0\.0\.1|dev server|api\.py|backend)\b",
     "local service restart"),
    (r"\brun\b.{0,30}\b(?:tests?|suites?|build)\b", "test/build run"),
]

_TIER0_PATTERNS: list[tuple[str, str]] = [
    (r"\b(?:read|inspect|check|verify|diagnose|analyze|analyse|status|list|show|probe|poll|monitor|summari[sz]e|report|audit)\b",
     "read-only verb"),
]

_TIERS: list[tuple[int, list[tuple[str, str]]]] = [
    (3, _TIER3_PATTERNS),
    (2, _TIER2_PATTERNS),
    (1, _TIER1_PATTERNS),
    (0, _TIER0_PATTERNS),
]


@dataclass
class TierResult:
    tier: int
    reasons: list[str] = field(default_factory=list)

    @property
    def requires_human(self) -> bool:
        return self.tier >= 3


def classify_tier(instruction: str) -> TierResult:
    """
    Classify an instruction's risk tier. Highest matched tier wins.
    No match at all defaults to Tier 1 (assume mutation, get audited)
    rather than Tier 0 — fail toward more verification, not less.
    """
    text = (instruction or "").lower()
    if not text.strip():
        return TierResult(tier=0, reasons=["empty instruction"])

    for tier, patterns in _TIERS:
        reasons = [desc for pat, desc in patterns if re.search(pat, text)]
        if reasons:
            return TierResult(tier=tier, reasons=reasons)

    return TierResult(tier=1, reasons=["no pattern matched — mutation assumed"])


if __name__ == "__main__":
    CASES = [
        ("Check the health endpoint status on localhost", 0),
        ("Read api.py and summarize the routing table", 0),
        ("Fix the ImportError in loop_engine.py and run the tests", 1),
        ("Implement the new SKU search endpoint", 1),
        ("git add the two changed files, commit and push to dev", 2),
        ("Deploy the ERP to production", 3),
        ("Run deploy_erp.py", 3),
        ("Delete all records from the suppliers table", 3),
        ("Merge dev into main", 3),
        ("Update CLAUDE_RULES with a new section", 3),
    ]
    passed = 0
    for instruction, expected in CASES:
        r = classify_tier(instruction)
        ok = r.tier == expected
        print(f"  [{'PASS' if ok else 'FAIL'}] tier={r.tier} (want {expected}) — {instruction[:55]}")
        passed += ok
    print(f"\n{passed}/{len(CASES)} passed")
