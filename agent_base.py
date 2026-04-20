"""
agent_base.py — AgentBase + Universal Data Provenance Protocol (UDPP)
═══════════════════════════════════════════════════════════════════════
All War Room C-Suite agents inherit from AgentBase.

Core concepts:
  ProvenanceClaim  — A single data point with mandatory source attribution
  AgentBase        — Base class with provenance enforcement utilities
  MOCK_PATTERNS    — Strings that immediately flag a claim as invalid

Citation coverage threshold: 80% (CITATION_COVERAGE_THRESHOLD)
Any agent output with fewer than 80% cited claims fails the Hallucination Gate.
"""

from typing import Any
from datetime import datetime, timezone

# ─────────────────────────────────────────────────────────────────────────────
# PROTOCOL CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

CITATION_COVERAGE_THRESHOLD = 0.80   # 80% of ALL claims must be validly cited (qualitative)
NUMERIC_CITATION_THRESHOLD  = 1.00   # 100% of NUMERIC/FINANCIAL claims must be cited (zero tolerance)

# Strings that indicate a claim is simulated, mocked, or uncited.
# Any source_citation or value containing these strings will fail the gate.
MOCK_PATTERNS = [
    "[SIMULATED]", "[simulated]", "SIMULATED",
    "[FALLBACK]", "fallback",
    "placeholder", "Placeholder",
    "hardcoded", "mock data", "test data",
    "dummy", "fake", "N/A", "TBD",
    "API unavailable", "unavailable",
    "not configured", "missing key",
]


# ─────────────────────────────────────────────────────────────────────────────
# PROVENANCE CLAIM
# ─────────────────────────────────────────────────────────────────────────────

class ProvenanceClaim:
    """
    Factory and validator for a single data claim with source attribution.

    A ProvenanceClaim is a dict with:
        value           — The actual data point (any type)
        source_citation — URL, file path, or API endpoint that produced the value
        tool_used       — Which tool was called (e.g. "web_search", "ledger_query")
        confidence      — Float 0.0-1.0 (data quality estimate)
        timestamp_utc   — ISO-8601 timestamp of when the claim was produced
    """

    @staticmethod
    def build(
        value: Any,
        source_citation: str,
        tool_used: str,
        confidence: float = 1.0,
    ) -> dict:
        """Build a validated ProvenanceClaim dict."""
        return {
            "value": value,
            "source_citation": source_citation,
            "tool_used": tool_used,
            "confidence": round(max(0.0, min(1.0, confidence)), 3),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def is_valid(claim: dict) -> bool:
        """
        Returns True if the claim has a non-mock, non-empty source_citation.
        A claim fails if:
          - source_citation is missing, empty, or whitespace-only
          - source_citation contains any MOCK_PATTERNS string
        """
        citation = claim.get("source_citation", "")
        if not citation or not citation.strip():
            return False
        if citation.strip().lower() in ("n/a", "tbd", "none", "null", ""):
            return False
        citation_lower = citation.lower()
        if any(p.lower() in citation_lower for p in MOCK_PATTERNS):
            return False
        return True

    @staticmethod
    def value_has_mock_text(claim: dict) -> bool:
        """Returns True if the claim's value contains mock/placeholder text."""
        val_str = str(claim.get("value", ""))
        return any(p in val_str for p in MOCK_PATTERNS)


# ─────────────────────────────────────────────────────────────────────────────
# AGENT BASE CLASS
# ─────────────────────────────────────────────────────────────────────────────

class AgentBase:
    """
    Universal base class for all War Room C-Suite agents.

    Subclasses implement run() and call:
        1. self.build_provenance_block(claims_dict) → _provenance dict
        2. self.validate_provenance(_provenance) → (is_valid, errors)
        3. self.merge_into_output(flat_result, _provenance) → final output

    The _provenance sidecar is backward-compatible: flat output keys remain
    at the top level unchanged. Provenance lives under the "_provenance" key.
    """

    AGENT_ID = "base"
    
    def __init__(self):
        self._trace = []

    def add_trace(self, message: str, node: str = "INTERNAL", status: str = "INFO"):
        """Add a thought process log entry to the agent's internal trace."""
        self._trace.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": node,
            "message": message,
            "status": status
        })

    def run(self, intent: str) -> dict:
        """Override in subclass. Must return a flat dict with _provenance sidecar."""
        raise NotImplementedError(f"{self.__class__.__name__}.run() not implemented")

    def build_provenance_block(self, claims: dict[str, dict]) -> dict:
        """
        Accepts a {claim_key: ProvenanceClaim} dict.
        Filters out any non-ProvenanceClaim entries.
        Returns the clean provenance block.
        """
        return {
            k: v for k, v in claims.items()
            if isinstance(v, dict) and "source_citation" in v and "value" in v
        }

    def validate_provenance(self, provenance_block: dict) -> tuple[bool, list[str]]:
        """
        Validates a provenance block against UDPP rules.

        Rules:
          1. Citation coverage must meet CITATION_COVERAGE_THRESHOLD (80%)
          2. No mock/simulated text in claim values
          3. Numeric claims must have a valid source_citation

        Returns: (is_valid: bool, errors: list[str])
        """
        if not provenance_block:
            return True, []  # no provenance = no enforcement (agent may not support it yet)

        errors = []
        claims = list(provenance_block.items())
        valid_citation_count = 0

        for key, claim in claims:
            citation_valid = ProvenanceClaim.is_valid(claim)
            if citation_valid:
                valid_citation_count += 1
            else:
                citation = claim.get("source_citation", "")
                errors.append(
                    f"[{self.AGENT_ID}].{key}: invalid or missing source_citation "
                    f"(got: {citation!r})"
                )

            # Rule: no mock text in the value itself
            if ProvenanceClaim.value_has_mock_text(claim):
                val_preview = str(claim.get("value", ""))[:80]
                errors.append(
                    f"[{self.AGENT_ID}].{key}: mock/placeholder text detected in value: {val_preview!r}"
                )

            # Rule: numeric claims must always be cited
            value = claim.get("value")
            if isinstance(value, (int, float)) and not ProvenanceClaim.is_valid(claim):
                errors.append(
                    f"[{self.AGENT_ID}].{key}: numeric claim ({value}) has no valid source_citation"
                )

        # Coverage check
        coverage = valid_citation_count / len(claims) if claims else 1.0
        if coverage < CITATION_COVERAGE_THRESHOLD:
            errors.append(
                f"[{self.AGENT_ID}]: citation coverage {coverage:.0%} is below "
                f"required threshold ({CITATION_COVERAGE_THRESHOLD:.0%}) — "
                f"{valid_citation_count}/{len(claims)} claims properly cited"
            )

        return len(errors) == 0, errors

    def merge_into_output(self, flat_result: dict, provenance_block: dict) -> dict:
        """
        Attaches the _provenance and _trace sidecars to a flat output dict.
        Flat values are preserved unchanged — fully backward-compatible.
        """
        flat_result["_provenance"] = provenance_block
        flat_result["trace"] = self._trace
        flat_result["_agent_id"] = self.AGENT_ID
        return flat_result


# ─────────────────────────────────────────────────────────────────────────────
# MODULE-LEVEL HELPERS (for use in logic_checker.py)
# ─────────────────────────────────────────────────────────────────────────────

def run_hallucination_gate(provenance_block: dict) -> tuple[str, list[str]]:
    """
    Standalone Hallucination Gate — runs against a combined provenance block
    from all agents (e.g. {"CMO": {...}, "CTO": {...}}).

    Two-tier threshold enforcement:
      - NUMERIC_CITATION_THRESHOLD  = 100% — zero tolerance for uncited numbers
      - CITATION_COVERAGE_THRESHOLD =  80% — global minimum for all claims

    Called by logic_checker.evaluate_logic() before the CEO strategy gate.
    Returns: ("PASS" | "FAIL", errors: list[str])
    """
    errors = []

    for agent_id, agent_claims in provenance_block.items():
        if not isinstance(agent_claims, dict) or agent_id.startswith("_"):
            continue

        valid_count = 0
        total = 0
        numeric_violations = []

        for claim_key, claim in agent_claims.items():
            if not isinstance(claim, dict) or "source_citation" not in claim:
                continue

            total += 1
            value = claim.get("value")
            citation_valid = ProvenanceClaim.is_valid(claim)

            if citation_valid:
                valid_count += 1
            else:
                citation = claim.get("source_citation", "")
                errors.append(
                    f"[{agent_id}].{claim_key}: invalid source_citation: {citation!r}"
                )

            # RULE 1 (100% enforcement): numeric/financial claims must ALWAYS be cited
            if isinstance(value, (int, float)) and not citation_valid:
                numeric_violations.append(
                    f"[{agent_id}].{claim_key}: numeric claim ({value}) lacks valid citation "
                    f"(NUMERIC_CITATION_THRESHOLD=100%)"
                )

            # RULE 2: mock/placeholder text in value
            if ProvenanceClaim.value_has_mock_text(claim):
                val_preview = str(value)[:80]
                errors.append(
                    f"[{agent_id}].{claim_key}: mock/placeholder text in value: {val_preview!r}"
                )

        # Apply 100% rule for numerics (independent of global coverage)
        errors.extend(numeric_violations)

        # Apply 80% global coverage rule for all claims
        if total > 0:
            coverage = valid_count / total
            if coverage < CITATION_COVERAGE_THRESHOLD:
                errors.append(
                    f"[{agent_id}]: global citation coverage {coverage:.0%} < "
                    f"required {CITATION_COVERAGE_THRESHOLD:.0%} "
                    f"({valid_count}/{total} claims cited)"
                )

    status = "FAIL" if errors else "PASS"
    return status, errors
