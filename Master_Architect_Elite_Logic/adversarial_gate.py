"""
adversarial_gate.py — Socratic Bridge Protocol for Architecture
════════════════════════════════════════════════════════════════
Master_Architect_Elite_Logic | Meta App Factory

Adapts the Boardroom SocraticChallenger into an architecture-specific
stress-test gate. Every Triad verdict passes through here before
patterns are stored in memory.

Flow:
  composite >= 85  → AUTO_APPROVE  → store pattern
  composite 60-84  → CHALLENGE     → 3 weakness probes → await reasoning
  composite < 60   → REJECT        → detailed report, no storage
"""

import os
import json
import random
import logging
from datetime import datetime

logger = logging.getLogger("AdversarialGate")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Architecture-Specific Weakness Categories ────────────

WEAKNESS_CATEGORIES = [
    "Single Point of Failure",
    "Horizontal Scaling Barrier",
    "State Coupling",
    "Schema Migration Risk",
    "Credential Surface Area",
    "Observability Gap",
    "Fallback Chain Completeness",
    "Data Consistency Under Failure",
]

WEAKNESS_TEMPLATES = {
    "Single Point of Failure": [
        "No redundancy in the proposed data path. A single node failure will cause total service outage.",
        "Critical service has no standby or failover mechanism. Mean time to recovery is undefined.",
        "The architecture relies on a single database instance with no read replicas or backup.",
    ],
    "Horizontal Scaling Barrier": [
        "Shared mutable state between request handlers prevents adding more instances.",
        "File-based locking mechanisms will break under multi-process deployment.",
        "WebSocket session affinity is not addressed — load balancer will break connections.",
    ],
    "State Coupling": [
        "Two services share a JSON file for state synchronization. This creates tight coupling and race conditions.",
        "In-memory state is shared across request boundaries without proper isolation.",
        "Global variables are used for cross-request state — will not survive process restart.",
    ],
    "Schema Migration Risk": [
        "Column rename without backward compatibility will break all existing queries.",
        "No rollback migration provided. If deploy fails, data recovery is manual.",
        "Foreign key constraint added to table with existing orphaned records will fail.",
    ],
    "Credential Surface Area": [
        "Three separate services each directly access the Gemini API key. Consolidate via vault.",
        "API keys are loaded via os.getenv() without vault_client fallback — insecure on shared systems.",
        "New service introduces a credential that is not covered by the rotation schedule.",
    ],
    "Observability Gap": [
        "No structured logging or telemetry for the new service. Failure reconstruction will be impossible.",
        "Error responses return generic messages — no correlation IDs for debugging.",
        "No health check endpoint defined. The watchdog cannot monitor this service.",
    ],
    "Fallback Chain Completeness": [
        "Primary AI provider failure has no fallback. Service will return errors during outage.",
        "Circuit breaker is configured but has no half-open probe — will never auto-recover.",
        "SSE stream has no heartbeat/keepalive. Silent connection drops will go undetected.",
    ],
    "Data Consistency Under Failure": [
        "Multi-step write operation is not wrapped in a transaction. Partial failure will leave inconsistent state.",
        "Cache invalidation is not synchronized with the database write. Stale reads are possible.",
        "Event sourcing has no idempotency guard. Replayed events will create duplicates.",
    ],
}

# ── Reasoning Analysis ──────────────────────────────────

STRONG_SIGNALS = [
    "data shows", "evidence", "metrics", "measured", "tested",
    "validated", "benchmark", "analysis", "research", "proven",
    "roi", "experiment", "a/b test", "user feedback", "pilot",
    "load test", "failover test", "migration test", "rollback",
]

WEAK_SIGNALS = [
    "i think", "i believe", "i feel", "probably", "maybe",
    "could work", "should be fine", "trust me", "gut feeling",
    "instinct", "hope", "assume",
]


class AdversarialGate:
    """
    Socratic Bridge stress-test for architecture reviews.
    Integrates with TriadEngine and ArchitectMemory.
    """

    AUTO_APPROVE_THRESHOLD = 85
    CHALLENGE_THRESHOLD = 60
    MAX_ROUNDS = 3

    def __init__(self, config: dict = None):
        if config:
            gate_cfg = config.get("adversarial_gate", {})
            self.AUTO_APPROVE_THRESHOLD = gate_cfg.get("auto_approve_threshold", 85)
            self.CHALLENGE_THRESHOLD = gate_cfg.get("challenge_threshold", 60)
            self.MAX_ROUNDS = gate_cfg.get("max_challenge_rounds", 3)

        self._active_challenges = {}
        self._challenge_counter = 0
        self._log_dir = os.path.join(SCRIPT_DIR, "gate_logs")
        os.makedirs(self._log_dir, exist_ok=True)

    # ── Evaluate ────────────────────────────────────────

    def evaluate(self, triad_verdict: dict) -> dict:
        """
        Evaluate a Triad verdict.
        Returns gate result with status and any challenge info.
        """
        score = triad_verdict.get("composite_score", 0)
        concerns = triad_verdict.get("concerns", [])
        description = triad_verdict.get("request_summary",
                      triad_verdict.get("structural", {}).get("description", ""))

        if score >= self.AUTO_APPROVE_THRESHOLD:
            result = {
                "gate_result": "AUTO_APPROVE",
                "composite_score": score,
                "message": f"Architecture meets elite standards (score {score}/100). Auto-approved.",
                "challenge_id": None,
                "weaknesses": [],
            }
            self._log_event("auto_approve", result)
            return result

        if score >= self.CHALLENGE_THRESHOLD:
            return self._issue_challenge(score, concerns, description)

        # Reject
        result = {
            "gate_result": "REJECTED",
            "composite_score": score,
            "message": f"Architecture does not meet minimum standards (score {score}/100).",
            "concerns": concerns,
            "recommendations": triad_verdict.get("recommendations", []),
        }
        self._log_event("rejected", result)
        return result

    # ── Challenge ───────────────────────────────────────

    def _issue_challenge(self, score: int, concerns: list,
                         description: str) -> dict:
        self._challenge_counter += 1
        challenge_id = f"CHG-{self._challenge_counter:04d}"

        weaknesses = self._generate_weaknesses(description, score)

        challenge = {
            "gate_result": "CHALLENGED",
            "challenge_id": challenge_id,
            "status": "PAUSED",
            "composite_score": score,
            "gap_from_threshold": self.AUTO_APPROVE_THRESHOLD - score,
            "weaknesses": weaknesses,
            "options": ["convince", "force_proceed"],
            "created_at": datetime.now().isoformat(),
            "resolved_at": None,
            "resolution": None,
            "round": 1,
        }

        self._active_challenges[challenge_id] = challenge
        self._log_event("challenge_issued", challenge)
        return challenge

    def _generate_weaknesses(self, description: str, score: int) -> list:
        if score < 65:
            severity = "CRITICAL"
        elif score < 75:
            severity = "SIGNIFICANT"
        else:
            severity = "MODERATE"

        # Select relevant categories
        desc_lower = description.lower()
        relevant = []
        for cat in WEAKNESS_CATEGORIES:
            cat_words = cat.lower().split()
            if any(w in desc_lower for w in cat_words):
                relevant.append(cat)

        if len(relevant) < 3:
            remaining = [c for c in WEAKNESS_CATEGORIES if c not in relevant]
            random.shuffle(remaining)
            relevant.extend(remaining[:3 - len(relevant)])

        relevant = relevant[:3]

        weaknesses = []
        for i, category in enumerate(relevant):
            templates = WEAKNESS_TEMPLATES.get(category, ["No template available."])
            weaknesses.append({
                "id": i + 1,
                "category": category,
                "severity": severity,
                "challenge": random.choice(templates),
                "required_evidence": f"Provide data or reasoning addressing {category.lower()}.",
            })

        return weaknesses

    # ── Respond (Convince) ──────────────────────────────

    def analyze_response(self, challenge_id: str,
                         user_reasoning: str) -> dict:
        if challenge_id not in self._active_challenges:
            return {"error": f"Challenge {challenge_id} not found or already resolved."}

        challenge = self._active_challenges[challenge_id]
        reasoning_lower = user_reasoning.lower()

        strong_count = sum(1 for s in STRONG_SIGNALS if s in reasoning_lower)
        weak_count = sum(1 for s in WEAK_SIGNALS if s in reasoning_lower)
        word_count = len(user_reasoning.split())

        # Scoring
        reasoning_score = 0
        if word_count >= 100:
            reasoning_score += 3
        elif word_count >= 50:
            reasoning_score += 2
        elif word_count >= 20:
            reasoning_score += 1

        reasoning_score += min(strong_count * 1.5, 5)
        reasoning_score -= weak_count * 0.5

        # Coverage
        addressed = 0
        for w in challenge["weaknesses"]:
            cat_words = w["category"].lower().split()
            if any(cw in reasoning_lower for cw in cat_words):
                addressed += 1
        coverage_bonus = (addressed / max(len(challenge["weaknesses"]), 1)) * 2
        reasoning_score += coverage_bonus
        reasoning_score = max(0, min(10, reasoning_score))

        # Map composite to 0-10 scale
        critic_score_mapped = challenge["composite_score"] / 10
        combined_score = (critic_score_mapped + reasoning_score) / 2
        is_convinced = combined_score >= 7.0

        if is_convinced:
            verdict = "CONVINCED"
            message = (
                f"The Adversarial Gate acknowledges the Commander's reasoning. "
                f"Score: {reasoning_score:.1f}/10. Combined: {combined_score:.1f}/10. "
                f"Architecture marked as Battle-Tested."
            )
            challenge["resolved_at"] = datetime.now().isoformat()
            challenge["resolution"] = "Battle-Tested"
        else:
            verdict = "UNCONVINCED"
            unaddressed = [
                w["category"] for w in challenge["weaknesses"]
                if not any(cw in reasoning_lower for cw in w["category"].lower().split())
            ]
            message = (
                f"The Gate remains unconvinced. Reasoning: {reasoning_score:.1f}/10. "
                f"Combined: {combined_score:.1f}/10. "
                f"Unaddressed: {', '.join(unaddressed) if unaddressed else 'all addressed but insufficient evidence'}. "
                f"Use Hard Override or provide stronger evidence."
            )

        result = {
            "challenge_id": challenge_id,
            "gate_result": verdict,
            "verdict": verdict,
            "reasoning_score": round(reasoning_score, 1),
            "combined_score": round(combined_score, 1),
            "original_composite": challenge["composite_score"],
            "message": message,
            "analysis": {
                "word_count": word_count,
                "strong_signals": strong_count,
                "weak_signals": weak_count,
                "weaknesses_addressed": f"{addressed}/{len(challenge['weaknesses'])}",
                "coverage_score": round(coverage_bonus, 1),
            },
        }

        self._log_event("reasoning_analyzed", result)
        return result

    # ── Hard Override ───────────────────────────────────

    def force_proceed(self, challenge_id: str,
                      commander_note: str = "") -> dict:
        if challenge_id not in self._active_challenges:
            return {"error": f"Challenge {challenge_id} not found."}

        challenge = self._active_challenges[challenge_id]
        gap = challenge["gap_from_threshold"]

        if gap <= 5:
            risk_level = "low"
        elif gap <= 15:
            risk_level = "medium"
        elif gap <= 25:
            risk_level = "high"
        else:
            risk_level = "critical"

        risk_descriptions = {
            "low": "Minor gaps. Proceeding with monitoring recommended.",
            "medium": "Substantive concerns unaddressed. Close monitoring required.",
            "high": "Critical weaknesses bypassed. Full audit required within 30 days.",
            "critical": "Multiple structural risks overridden. Immediate post-deploy review mandatory.",
        }

        override = {
            "challenge_id": challenge_id,
            "gate_result": "COMMANDER_OVERRIDE",
            "risk_level": risk_level,
            "risk_description": risk_descriptions[risk_level],
            "original_composite": challenge["composite_score"],
            "gap_from_threshold": gap,
            "weaknesses_unaddressed": [w["challenge"] for w in challenge["weaknesses"]],
            "commander_note": commander_note,
            "audit_required": risk_level in ("high", "critical"),
            "audit_deadline": "30 days" if risk_level in ("high", "critical") else "N/A",
        }

        challenge["resolved_at"] = datetime.now().isoformat()
        challenge["resolution"] = f"Commander-Override ({risk_level})"

        self._log_event("hard_override", override)
        return override

    # ── Status ──────────────────────────────────────────

    def get_active_challenges(self) -> list:
        return [
            c for c in self._active_challenges.values()
            if c.get("resolved_at") is None
        ]

    # ── Logging ─────────────────────────────────────────

    def _log_event(self, event_type: str, data: dict):
        try:
            log_file = os.path.join(self._log_dir, "gate_audit.json")
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

            if len(existing) > 500:
                existing = existing[-500:]

            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Gate log failed: {e}")
