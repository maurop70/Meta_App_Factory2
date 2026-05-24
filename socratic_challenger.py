"""
socratic_challenger.py — Dialectical Challenge Protocol (Phase 3)
═══════════════════════════════════════════════════════════════════
Meta_App_Factory | Antigravity V3.0 | Venture Studio

Implements the "Socratic Persuasion" logic:
  1. Strategic Pause  — halts when Critic score < 9.5
  2. Persuasion Loop  — Critic presents 3 weaknesses, waits for user input
  3. Convince Logic   — analyzes user reasoning for logical soundness
  4. Hard Override    — logs risks, marks path as "Commander-Override"

Integrates with the War Room WebSocket for real-time boardroom challenge flow.
"""

import os
import sys
import json
import logging
import random
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger("socratic_challenger")

# ── Challenge Templates ──────────────────────────────────

WEAKNESS_CATEGORIES = [
    "Scalability",
    "Market Validation",
    "Technical Debt",
    "Competitive Moat",
    "Unit Economics",
    "User Retention",
    "Regulatory Risk",
    "Team Dependency",
    "Data Privacy",
    "Go-to-Market Timing",
]

WEAKNESS_TEMPLATES = {
    "Scalability": [
        "The current architecture shows no auto-scaling strategy. At 10x load, response times will breach SLA thresholds.",
        "Database write patterns suggest single-node bottleneck. No sharding or replication strategy is documented.",
        "WebSocket fan-out without message broker will cap at ~500 concurrent sessions.",
    ],
    "Market Validation": [
        "No A/B test data supports the proposed UX flow. Competitor analysis shows 3 alternatives with proven conversion funnels.",
        "Target persona assumptions are unvalidated. No user interviews or survey data reference in the plan.",
        "Market size estimate uses top-down TAM methodology without bottom-up validation.",
    ],
    "Technical Debt": [
        "14 TODO markers remain in production code. 3 are in critical authentication paths.",
        "Test coverage is below 40%. Any refactor risks silent regression in edge cases.",
        "Dependency tree includes 6 packages with known CVEs. No remediation timeline exists.",
    ],
    "Competitive Moat": [
        "The proposed feature set is table-stakes in the current market. No defensible IP or network effect is described.",
        "Switching costs for users are near-zero. What prevents churn when a well-funded competitor enters?",
        "The technology stack is commodity. Differentiation must come from execution speed, not architecture.",
    ],
    "Unit Economics": [
        "Customer acquisition cost projections assume organic growth without paid channels. Industry benchmarks suggest 3x higher CAC.",
        "Gross margin assumptions exclude infrastructure amortization and support staffing.",
        "Projected LTV/CAC ratio of 5:1 is optimistic given current churn data.",
    ],
    "User Retention": [
        "No re-engagement mechanism exists. Users who churn have no recovery path.",
        "Onboarding flow has 6 steps. Industry data shows each step loses 15-20% of users.",
        "No push notification or email drip campaign infrastructure is planned.",
    ],
    "Regulatory Risk": [
        "Data handling practices may not comply with GDPR Article 17 (right to erasure).",
        "Cross-border data transfer strategy is undefined. EU-US data flows require documented safeguards.",
        "Financial data processing may trigger SOC2 Type II requirements not budgeted in the plan.",
    ],
    "Team Dependency": [
        "Single point of failure: only one engineer understands the core orchestration layer.",
        "No documentation bus-factor analysis. Knowledge concentration creates existential risk.",
        "Hiring timeline for planned features is unrealistic given current market conditions.",
    ],
    "Data Privacy": [
        "PII flows through 3 services without encryption-at-rest. Breach liability is unquantified.",
        "Audit logging is insufficient for forensic reconstruction. No retention policy is defined.",
        "Third-party data sharing agreements lack sub-processor clauses required by modern privacy frameworks.",
    ],
    "Go-to-Market Timing": [
        "Market window analysis is absent. Seasonal patterns suggest Q1 launch disadvantage.",
        "Competitor release calendar shows 2 major launches within our planned launch window.",
        "Enterprise sales cycle of 6-9 months means revenue recognition won't happen until Q3 at earliest.",
    ],
}

# ── Reasoning Analysis Keywords ──────────────────────────

STRONG_REASONING_SIGNALS = [
    "data shows", "evidence", "metrics", "measured", "tested",
    "validated", "benchmark", "analysis", "research", "study",
    "proven", "ROI", "experiment", "A/B test", "user feedback",
    "survey", "interview", "pilot", "prototype", "mvp results",
    "conversion rate", "retention", "growth rate", "margin",
]

WEAK_REASONING_SIGNALS = [
    "i think", "i believe", "i feel", "probably", "maybe",
    "could work", "should be fine", "trust me", "just do it",
    "gut feeling", "instinct", "hope", "assume",
]

OVERRIDE_RISK_LEVELS = {
    "low": "Proceeding without full Critic approval. Minor gaps in validation.",
    "medium": "Substantive objections remain unaddressed. Recommend monitoring closely.",
    "high": "Critical weaknesses bypassed by Commander authority. Requires post-launch review.",
    "critical": "Multiple structural risks were flagged but overridden. Full audit required within 30 days.",
}


class SocraticChallenger:
    """
    Dialectical challenge engine for the Boardroom War Room.

    Controls the flow:
      evaluate() → if score < 9.5 → challenge() → wait for user →
      analyze_response() → either "User-Validated" or recommend retry →
      force_proceed() → log risks and release lock

    Usage:
        challenger = SocraticChallenger()
        result = challenger.evaluate(proposal, critic_score=7.2)
        # result.status == "PAUSED" → challenge issued
        # User provides reasoning...
        verdict = challenger.analyze_response(challenge_id, user_reasoning)
    """

    PAUSE_THRESHOLD = 9.5  # Score below which we pause

    def __init__(self, log_dir=None):
        self.log_dir = log_dir or os.path.join(SCRIPT_DIR, "socratic_logs")
        os.makedirs(self.log_dir, exist_ok=True)
        self._challenge_counter = 0

    def _load_challenges(self):
        """Load active challenges from disk ledger."""
        path = os.path.join(self.log_dir, "active_challenges.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load active challenges: {e}")
        return {}

    def _save_challenges(self, challenges):
        """Save active challenges to disk ledger."""
        path = os.path.join(self.log_dir, "active_challenges.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(challenges, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save active challenges: {e}")

    # ── 1. Strategic Pause ───────────────────────────────

    def evaluate(self, proposal: str, critic_score: float, context: dict = None):
        """
        Evaluate a proposal against the Critic's score.
        If score < 9.5, issues a Strategic Pause with 3 challenges.
        """
        if critic_score >= self.PAUSE_THRESHOLD:
            return {
                "status": "APPROVED",
                "score": critic_score,
                "message": f"Critic score {critic_score}/10 meets threshold ({self.PAUSE_THRESHOLD}). Proceeding.",
                "validation": "Auto-Approved",
            }

        # Issue Strategic Pause
        challenges = self._load_challenges()
        counter = len(challenges) + 1
        challenge_id = f"CHG-{counter:04d}"
        while challenge_id in challenges:
            counter += 1
            challenge_id = f"CHG-{counter:04d}"

        weaknesses = self._generate_weaknesses(proposal, critic_score)

        challenge = {
            "challenge_id": challenge_id,
            "status": "PAUSED",
            "score": critic_score,
            "threshold": self.PAUSE_THRESHOLD,
            "gap": round(self.PAUSE_THRESHOLD - critic_score, 1),
            "proposal_preview": proposal[:200],
            "weaknesses": weaknesses,
            "requires": "user_reasoning",
            "options": ["convince", "force_proceed"],
            "created_at": datetime.now().isoformat(),
            "resolved_at": None,
            "resolution": None,
        }

        challenges[challenge_id] = challenge
        self._save_challenges(challenges)
        self._log_event("challenge_issued", challenge)

        return challenge

    # ── 2. Persuasion Loop — Generate Weaknesses ─────────

    def _generate_weaknesses(self, proposal: str, score: float):
        """
        Generate 3 state-of-the-art weaknesses based on the proposal context.
        Selects categories intelligently based on proposal keywords.
        """
        # Score-based severity
        if score < 4:
            severity = "CRITICAL"
            num_weaknesses = 3
        elif score < 7:
            severity = "SIGNIFICANT"
            num_weaknesses = 3
        else:
            severity = "MODERATE"
            num_weaknesses = 3

        # Select relevant categories based on proposal content
        proposal_lower = proposal.lower()
        relevant = []
        for cat in WEAKNESS_CATEGORIES:
            cat_lower = cat.lower().replace(" ", "")
            if any(kw in proposal_lower for kw in cat_lower.split()):
                relevant.append(cat)

        # Fill with random if not enough matches
        if len(relevant) < num_weaknesses:
            remaining = [c for c in WEAKNESS_CATEGORIES if c not in relevant]
            random.shuffle(remaining)
            relevant.extend(remaining[:num_weaknesses - len(relevant)])

        relevant = relevant[:num_weaknesses]

        # Build weakness objects
        weaknesses = []
        for i, category in enumerate(relevant):
            templates = WEAKNESS_TEMPLATES.get(category, ["No detailed weakness template available."])
            weaknesses.append({
                "id": i + 1,
                "category": category,
                "severity": severity,
                "challenge": random.choice(templates),
                "required_evidence": f"Provide data or reasoning addressing {category.lower()}.",
            })

        return weaknesses

    # ── 3. Convince Logic — Analyze User Reasoning ───────

    def analyze_response(self, challenge_id: str, user_reasoning: str):
        """
        Analyze user's reasoning against the issued challenge.
        Returns a verdict with updated score and validation status.
        """
        challenges = self._load_challenges()
        if challenge_id not in challenges:
            return {"error": f"Challenge {challenge_id} not found or already resolved."}

        challenge = challenges[challenge_id]
        if challenge.get("resolved_at"):
            return {"error": f"Challenge {challenge_id} is already resolved."}

        # Reasoning quality analysis
        reasoning_lower = user_reasoning.lower()
        strong_count = sum(1 for s in STRONG_REASONING_SIGNALS if s in reasoning_lower)
        weak_count = sum(1 for s in WEAK_REASONING_SIGNALS if s in reasoning_lower)
        word_count = len(user_reasoning.split())

        # Scoring rubric
        reasoning_score = 0

        # Length bonus (substantive responses score higher)
        if word_count >= 100:
            reasoning_score += 3
        elif word_count >= 50:
            reasoning_score += 2
        elif word_count >= 20:
            reasoning_score += 1

        # Evidence signals
        reasoning_score += min(strong_count * 1.5, 5)

        # Penalty for weak reasoning
        reasoning_score -= weak_count * 0.5

        # Address each weakness? (check for category keywords)
        addressed = 0
        for w in challenge["weaknesses"]:
            cat_words = w["category"].lower().split()
            if any(cw in reasoning_lower for cw in cat_words):
                addressed += 1
        coverage_bonus = (addressed / len(challenge["weaknesses"])) * 2
        reasoning_score += coverage_bonus

        # Final score (0-10)
        reasoning_score = max(0, min(10, reasoning_score))

        # Determine verdict
        combined_score = (challenge["score"] + reasoning_score) / 2
        is_convinced = combined_score >= 7.0

        if is_convinced:
            verdict = "CONVINCED"
            validation = "User-Validated"
            new_persuasion = min(10, int(combined_score) + 1)
            message = (
                f"The Critic acknowledges the strength of the Commander's reasoning. "
                f"Analysis score: {reasoning_score:.1f}/10. "
                f"Combined: {combined_score:.1f}/10. Path marked as User-Validated."
            )
        else:
            verdict = "UNCONVINCED"
            validation = "Pending"
            new_persuasion = max(1, int(combined_score))
            message = (
                f"The Critic remains unconvinced. Reasoning score: {reasoning_score:.1f}/10. "
                f"Combined: {combined_score:.1f}/10. Consider addressing: "
                + ", ".join(w["category"] for w in challenge["weaknesses"] if
                           not any(cw in reasoning_lower for cw in w["category"].lower().split()))
                + ". You may try again or use Hard Override."
            )

        result = {
            "challenge_id": challenge_id,
            "verdict": verdict,
            "validation": validation,
            "reasoning_score": round(reasoning_score, 1),
            "combined_score": round(combined_score, 1),
            "original_critic_score": challenge["score"],
            "new_persuasion": new_persuasion,
            "message": message,
            "analysis": {
                "word_count": word_count,
                "strong_signals": strong_count,
                "weak_signals": weak_count,
                "weaknesses_addressed": f"{addressed}/{len(challenge['weaknesses'])}",
                "coverage_score": round(coverage_bonus, 1),
            },
        }

        if is_convinced:
            challenge["resolved_at"] = datetime.now().isoformat()
            challenge["resolution"] = "User-Validated"
            challenges[challenge_id] = challenge
            self._save_challenges(challenges)

        self._log_event("reasoning_analyzed", result)
        return result

    # ── 4. Hard Override ─────────────────────────────────

    def force_proceed(self, challenge_id: str, commander_note: str = ""):
        """
        Commander Hard Override — logs all risks and releases the lock.
        The Critic must document the risks but allow the Architect to proceed.
        """
        challenges = self._load_challenges()
        if challenge_id not in challenges:
            return {"error": f"Challenge {challenge_id} not found."}

        challenge = challenges[challenge_id]

        # Determine risk level from gap
        gap = challenge["gap"]
        if gap <= 1:
            risk_level = "low"
        elif gap <= 3:
            risk_level = "medium"
        elif gap <= 5:
            risk_level = "high"
        else:
            risk_level = "critical"

        risk_description = OVERRIDE_RISK_LEVELS[risk_level]

        override_log = {
            "challenge_id": challenge_id,
            "status": "OVERRIDE",
            "risk_level": risk_level,
            "risk_description": risk_description,
            "original_score": challenge["score"],
            "gap_from_threshold": challenge["gap"],
            "weaknesses_unaddressed": [w["challenge"] for w in challenge["weaknesses"]],
            "commander_note": commander_note,
            "override_at": datetime.now().isoformat(),
            "audit_required": risk_level in ("high", "critical"),
            "audit_deadline": "30 days" if risk_level in ("high", "critical") else "N/A",
        }

        # Mark challenge as resolved
        challenge["resolved_at"] = datetime.now().isoformat()
        challenge["resolution"] = f"Commander-Override ({risk_level})"

        challenges[challenge_id] = challenge
        self._save_challenges(challenges)

        self._log_event("hard_override", override_log)

        return override_log

    # ── Helpers ───────────────────────────────────────────

    def get_active_challenges(self):
        """Return list of unresolved challenges."""
        challenges = self._load_challenges()
        return {
            cid: c
            for cid, c in challenges.items()
            if c.get("resolved_at") is None
        }

    def _log_event(self, event_type, data):
        """Log Socratic events to file for audit trail."""
        try:
            log_file = os.path.join(self.log_dir, "socratic_audit.json")
            existing = []
            if os.path.exists(log_file):
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    existing = []

            existing.append({
                "event": event_type,
                "timestamp": datetime.now().isoformat(),
                "data": data,
            })

            # Keep last 500 events
            if len(existing) > 500:
                existing = existing[-500:]

            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, default=str)
        except Exception as e:
            logger.error("Failed to log Socratic event: %s", e)


# ── Module-level singleton ───────────────────────────────
_challenger = SocraticChallenger()


def get_challenger() -> SocraticChallenger:
    """Get the module-level SocraticChallenger instance."""
    return _challenger


import ast
from typing import List

class DoctrineEnforcer(ast.NodeVisitor):
    def __init__(self):
        self.violations: List[str] = []
        self.current_function = None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.current_function = node.name
        self._audit_route_decorator(node)
        self._audit_cpu_isolation(node)
        self._audit_pagination_boundary(node)
        self._audit_runtime_imports(node)
        self.generic_visit(node)
        self.current_function = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.current_function = node.name
        self._audit_route_decorator(node)
        self._audit_runtime_imports(node)
        self.generic_visit(node)
        self.current_function = None

    def _audit_runtime_imports(self, node):
        """Rule 4: Eradicate Inline Runtime Imports"""
        for stmt in node.body:
            for child in ast.walk(stmt):
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    self.violations.append(
                        f"[FATAL] Line {child.lineno}: Inline import '{child.names[0].name}' detected inside '{self.current_function}'. All dependencies must be resolved at the global module level."
                    )

    def _audit_route_decorator(self, node):
        """Rule 3: Eradicate Catch-All Fallback Routes"""
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr in ['get', 'post', 'put', 'delete']:
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        route_path = decorator.args[0].value
                        if "{full_path:path}" in str(route_path):
                            self.violations.append(
                                f"[FATAL] Line {node.lineno}: Catch-all fallback route '{route_path}' detected in '{self.current_function}'. Static HTML mounting is permanently forbidden."
                            )
            # Check StaticFiles in decorators or body
        for stmt in node.body:
            for child in ast.walk(stmt):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                    if child.func.id == 'StaticFiles':
                        self.violations.append(f"[FATAL] Line {child.lineno}: StaticFiles invocation detected in '{self.current_function}'. Static mounting forbidden.")

    def _audit_cpu_isolation(self, node):
        """Rule 2: CPU-Bound Thread Isolation"""
        for stmt in node.body:
            for child in ast.walk(stmt):
                if isinstance(child, ast.Call) and getattr(child.func, 'id', None) in ['FPDF', 'generate_pdf', 'csv_writer']:
                    self.violations.append(
                        f"[FATAL] Line {node.lineno}: CPU-bound I/O operation '{child.func.id}' detected on primary async thread in '{self.current_function}'. Must decouple via background worker."
                    )
                # Also check attribute calls like fpdf2 maneuvers
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                    if child.func.attr in ['output', 'write'] and 'pdf' in str(getattr(child.func.value, 'id', '')).lower():
                        self.violations.append(
                            f"[FATAL] Line {node.lineno}: CPU-bound fpdf2 maneuver detected in '{self.current_function}'. Must decouple via background worker."
                        )

    def _audit_pagination_boundary(self, node):
        """Rule 1: Pagination Boundary Enforcement"""
        is_get_route = False
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr == 'get':
                    is_get_route = True
                    break
        
        if not is_get_route:
            return

        arg_names = [arg.arg for arg in node.args.args] + [arg.arg for arg in node.args.kwonlyargs]
        has_pagination_args = ('limit' in arg_names and 'offset' in arg_names)
        
        for stmt in node.body:
            for child in ast.walk(stmt):
                if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                    keys = [k.value for k in child.value.keys if isinstance(k, ast.Constant)]
                    if 'items' in keys:
                        if not has_pagination_args:
                            self.violations.append(f"[FATAL] Line {node.lineno}: @router.get route '{self.current_function}' returns a collection ('items') but lacks 'limit' and 'offset' arguments.")
                        
                        required_keys = {'items', 'total', 'limit', 'offset'}
                        
                        # ── STRICT MATCH SET DIFFERENCE ──
                        unauthorized_keys = set(keys) - required_keys
                        for illegal_key in unauthorized_keys:
                            self.violations.append(f"[FATAL] Unauthorized key '{illegal_key}' detected in I/O serialization envelope. Strict match required.")
                            
                        missing = required_keys - set(keys)
                        if missing:
                            self.violations.append(f"[FATAL] Line {child.lineno}: Return statement in '{self.current_function}' violates Pagination Boundary. Missing keys: {missing}")

def audit_staging_payload(filepath: str) -> List[str]:
    """Ingests the STAGING file and returns physical doctrine violations."""
    if not os.path.exists(filepath):
        return [f"[SYSTEM ERROR] Staging payload not found at {filepath}"]
        
    with open(filepath, 'r', encoding='utf-8') as file:
        source_code = file.read()
        
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        return [f"[FATAL SYNTAX ERROR] Cannot parse AST: {e.msg} at line {e.lineno}"]
        
    enforcer = DoctrineEnforcer()
    enforcer.visit(tree)
    return enforcer.violations

from typing import Dict, Any

def evaluate_payload(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """
    The Central Adversarial Gatekeeper.
    Physically routes payloads based on strict structural verification, overriding upstream intent.
    """
    payload_type = envelope.get("payload_type", "STRATEGIC_DOCUMENT")
    content_format = envelope.get("content_format", "markdown").lower()
    metadata = envelope.get("metadata", {})
    filename = metadata.get("filename", "").lower()
    staging_filepath = envelope.get("staging_filepath", "")
    
    # ── 1. ZERO-TRUST EXTENSION OVERRIDE ──
    # Mathematical enforcement: check metadata, format, AND the physical target path
    if (filename.endswith(".py") or 
        content_format == "python" or 
        staging_filepath.lower().endswith(".py")):
        payload_type = "EXECUTABLE_CODE"
        
    # ── 2. AST / MATHEMATICAL ROUTE ──
    if payload_type == "EXECUTABLE_CODE":
        staging_filepath = envelope.get("staging_filepath")
        
        if not staging_filepath or not os.path.exists(staging_filepath):
            return {
                "status": "FATAL_ERROR",
                "verdict": "REJECTED",
                "message": f"[FATAL] EXECUTABLE_CODE payload requires a physical path."
            }
            
        # ── LANGUAGE BIFURCATION ──
        if staging_filepath.lower().endswith(".py"):
            # Execute strict Python doctrine enforcement
            violations = audit_staging_payload(staging_filepath)
            if violations:
                return {
                    "status": "AST_VIOLATION",
                    "verdict": "REJECTED",
                    "message": "Physical doctrine violations detected. Atomic swap blocked.",
                    "violations": violations
                }
        elif staging_filepath.lower().endswith((".jsx", ".js", ".tsx", ".ts")):
            # Bypass Python AST; delegate to Playwright Diagnostic Node
            pass 
        else:
            return {
                "status": "UNSUPPORTED_LANGUAGE",
                "verdict": "REJECTED",
                "message": f"Unsupported executable format for AST parsing: {staging_filepath}"
            }

        return {
            "status": "APPROVED",
            "verdict": "VERIFIED",
            "message": "Payload passed structural pre-flight. Proceed to Diagnostic Node."
        }
            
    # ── 4. STRATEGIC ROUTING (MODE B) ──
    else:
        # Safe to use raw string content for lexical analysis
        content = envelope.get("content", "")
        critic_score = metadata.get("critic_score", 5.0)
        
        # Instantiate the lexical SocraticChallenger engine
        challenger = get_challenger()
        result = challenger.evaluate(proposal=content, critic_score=critic_score)
        
        # Result contains PAUSED status, weaknesses, allowing the Persuasion Loop
        return result

# ── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Socratic Challenger — Dialectical Challenge Engine")
    parser.add_argument("--score", type=float, default=7.0, help="Critic score (0-10)")
    parser.add_argument("--proposal", default="Build an AI-powered SaaS dashboard", help="Proposal text")
    args = parser.parse_args()

    challenger = SocraticChallenger()

    print(f"\n{'='*60}")
    print(f"  🏛️ Socratic Challenger — Dialectical Engine")
    print(f"{'='*60}\n")

    result = challenger.evaluate(args.proposal, args.score)
    print(f"  Status: {result['status']}")
    print(f"  Score: {result.get('score', 'N/A')}/{challenger.PAUSE_THRESHOLD}")

    if result["status"] == "PAUSED":
        print(f"  Gap: {result['gap']} points below threshold")
        print(f"\n  Weaknesses Identified:")
        for w in result["weaknesses"]:
            print(f"    {w['id']}. [{w['severity']}] {w['category']}")
            print(f"       {w['challenge']}")
            print(f"       → {w['required_evidence']}")

        # Simulate user response
        print(f"\n  Simulating Commander response...")
        test_reasoning = (
            "Our A/B test data from the Q4 pilot shows 23% conversion rate improvement. "
            "Market research from McKinsey validates the $4.2B TAM estimate. "
            "User retention metrics from the MVP show 72% Day-30 retention. "
            "Technical scalability has been benchmarked to handle 50K concurrent users."
        )
        verdict = challenger.analyze_response(result["challenge_id"], test_reasoning)
        print(f"\n  Verdict: {verdict['verdict']}")
        print(f"  Reasoning Score: {verdict['reasoning_score']}/10")
        print(f"  Combined Score: {verdict['combined_score']}/10")
        print(f"  Validation: {verdict['validation']}")
        print(f"  Message: {verdict['message']}")

    print(f"\n{'='*60}\n")
