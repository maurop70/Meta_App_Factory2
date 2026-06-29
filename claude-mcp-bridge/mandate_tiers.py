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
    needs_human: bool = False   # refuse-to-classify signal (fail-high on the unknown)
    mislabeled: bool = False    # structured fields under-declared vs. concrete evidence

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


# ═════════════════════════════════════════════════════════════════════════════
# Phase 1 piece 2 — STRUCTURED-ACTION CLASSIFIER (two judges: declared ⊕ evidence)
# ═════════════════════════════════════════════════════════════════════════════
#
# LIMITATION — READ BEFORE TRUSTING THIS (stated plainly, like the call-stack
# boundary in executor_gate). The evidence judge is a regex/pattern scan: a SPEED
# BUMP, NOT A WALL. It catches the disguises enumerated in the adversarial matrix,
# NOT every possible one — that limit is inherent to pattern matching and cannot be
# regex'd away. It is acceptable ONLY because this detector is ONE LAYER among
# several: unrecognized mutations FAIL HIGH by design (the unknown is refused, not
# waved through), and the real defense against a cleverly disguised plan is the
# human approval gate and, later, the mixed-lineage panel. Do NOT treat this as a
# complete defense against disguise — it REDUCES that risk, it does not eliminate it.


def _known_prod_targets() -> set:
    """Known-prod targets come from the SINGLE named source the SSH wire already
    gates on (ssh_wire.APPROVED_HOSTS) — never a hardcoded IP list here, so a
    changed/added prod host stays recognized as prod. Lazy import keeps this
    module dependency-light."""
    try:
        from ssh_wire import APPROVED_HOSTS
        out = set()
        for ip, name in APPROVED_HOSTS.items():
            if ip:
                out.add(str(ip).lower())
            if name:
                out.add(str(name).lower())
        return out
    except Exception:
        return set()


# Evidence patterns run against the CONCRETE action payload, never free prose. They
# can only RAISE the tier. (Prod *hosts* are sourced above, not hardcoded here.)
_EVIDENCE_T3: list[tuple[str, str]] = [
    (r"\bdeploy(?:ing|ment)?\b|deploy_(?:erp|maf|edge)\.py", "deploy"),
    (r"\b(?:systemctl|service)\b.{0,30}\b(?:restart|stop|start|reload)\b|"
     r"\b(?:restart|reboot|bounce|kill)\b.{0,30}\b(?:service|daemon|unit|server|core-engine|erp-backend)\b",
     "service/prod restart"),
    (r"\b(?:prod|production|droplet|digitalocean|nyc\d?)\b", "production keyword"),
    (r"\b(?:delete|drop|truncate|wipe|purge)\b.{0,40}\b(?:table|database|db|records?|users?|schema)\b|"
     r"\bmigrat(?:e|ion)\b.{0,40}\b(?:prod|live|remote)\b", "destructive/live DB"),
    (r"\bmerge\b.{0,30}\b(?:into|to)\b.{0,10}\bmain\b|\bpush\b.{0,20}\b(?:origin/)?main\b", "merge/push to main"),
    (r"\b(?:billing|invoice|charge|payment|stripe|payout|refund|subscription|pricing|ledger)\b", "money/billing"),
    (r"\b(?:child[_\s-]?safety|coppa|age[_\s-]?gate|parental|minor|kids)\b", "child-safety (Module A)"),
    (r"\b(?:disable|bypass|skip|relax|grant|elevate)\b.{0,20}\bauth|"
     r"\b(?:auth[nz]?|rbac|acl|permission|role|oauth|session|firewall|cors|csp)\b.{0,25}"
     r"\b(?:boundary|policy|middleware|change|disable|bypass)\b", "auth/security boundary"),
    (r"\b(?:rm\s+-rf|format\s+[a-z]:|mkfs|del\s+/[sq])\b", "destructive OS command"),
    (r"deploy_(?:erp|maf|edge)\.py|executor_gate\.py|(?:^|[\\/])\.env\b", "writes a protected/guard file"),
]
_EVIDENCE_T2: list[tuple[str, str]] = [
    (r"\bgit\s+(?:add|commit|push)\b", "version control"),
]

# A shell command is benign ONLY if it is a SINGLE recognized command with NO tail.
# Any shell-chaining or substitution metacharacter disqualifies it — closing the
# benign-prefix-dangerous-tail bypass (e.g. "echo ok && rm -rf /prod").
_SHELL_METACHARS = re.compile(r"[&;|`\n<>]|\$\(")
_BENIGN_SHELL = re.compile(
    r"^\s*(?:echo|ls|dir|pwd|cat|type|head|tail|grep|find|whoami|date|"
    r"git\s+(?:status|log|diff|show)|pytest|python\s+-m\s+pytest|npm\s+(?:test|run\s+test))\b")


def _is_benign_shell(cmd: str) -> bool:
    if _SHELL_METACHARS.search(cmd):
        return False                       # any chaining/substitution => NOT benign
    return bool(_BENIGN_SHELL.match(cmd.strip().lower()))


def _evidence_tier(hay: str) -> tuple:
    for t in _known_prod_targets():
        if t and t in hay:
            return 3, [f"evidence: production target ({t})"]
    for pat, desc in _EVIDENCE_T3:
        if re.search(pat, hay):
            return 3, [f"evidence: {desc}"]
    for pat, desc in _EVIDENCE_T2:
        if re.search(pat, hay):
            return 2, [f"evidence: {desc}"]
    return 0, []


def _declared_tier(action: dict) -> tuple:
    touches = {str(x).lower() for x in (action.get("touches") or [])}
    tier, reasons = 0, []
    if action.get("deploys") or "production" in touches:
        tier = max(tier, 3); reasons.append("declared: production/deploy")
    if {"billing", "money", "payments"} & touches:
        tier = max(tier, 3); reasons.append("declared: billing")
    if {"child_safety", "module_a"} & touches:
        tier = max(tier, 3); reasons.append("declared: child-safety")
    if {"auth_boundary", "security_boundary", "authz"} & touches:
        tier = max(tier, 3); reasons.append("declared: auth boundary")
    if action.get("merges_main"):
        tier = max(tier, 3); reasons.append("declared: merge-main")
    if action.get("db_op") in ("delete", "drop", "truncate", "migrate"):
        tier = max(tier, 3); reasons.append(f"declared: db {action.get('db_op')}")
    return tier, reasons


def classify_action(action: dict) -> TierResult:
    """Classify ONE structured action. Structured fields are primary; an independent
    evidence scan of the concrete payload can only RAISE the tier (never lower it).
    Unrecognized mutation => fail-high (Tier 3, needs_human). Never defaults to safe.
    See the LIMITATION note above — this is one layer, not a complete defense."""
    a_type  = str(action.get("type", "")).lower()
    target  = str(action.get("target") or action.get("command") or action.get("path") or "")
    touches = [str(x).lower() for x in (action.get("touches") or [])]

    declared, dr = _declared_tier(action)
    evidence, er = _evidence_tier(f"{a_type} {target} {' '.join(touches)}".lower())

    tier = max(declared, evidence)
    mislabeled = evidence > declared and (action.get("touches") is not None or declared > 0)
    reasons = dr + er + (["MISLABEL: evidence exceeds declared fields"] if mislabeled else [])

    if tier == 0:    # nothing flagged — benign allowlist, else FAIL HIGH
        if a_type in ("read", "list", "exists", "status", "diagnose"):
            return TierResult(0, ["read-only"])
        if a_type == "shell" and _is_benign_shell(target):
            return TierResult(1, ["recognized-benign shell (single command, no tail)"])
        if a_type == "file_write":
            return TierResult(1, ["local file mutation"])
        if a_type == "git":
            return TierResult(2, ["git op"])
        return TierResult(3, ["unclassified mutation — fail-high"], needs_human=True)
    return TierResult(tier, reasons, mislabeled=mislabeled)


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
