"""
wisdom_vault.py — Cross-Project Memory (Corporate Standards)
═══════════════════════════════════════════════════════════════
Commander-curated knowledge that persists across War Room sessions.
Only approved insights become "Corporate Standards" — injected into
future agent prompts to make the Factory smarter with every build.

Relationship to institutional_memory.py:
  - institutional_memory = raw event log (auto-captured, uncurated)
  - wisdom_vault = curated law (Commander-approved, high-signal)

Storage: Project_Aether/Boardroom_Exchange/wisdom_vault.json

Author: Antigravity Master Architect
Version: 1.0.0
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from difflib import SequenceMatcher

logger = logging.getLogger("WisdomVault")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOARDROOM_DIR = os.path.join(SCRIPT_DIR, "Project_Aether", "Boardroom_Exchange")
VAULT_FILE = os.path.join(BOARDROOM_DIR, "wisdom_vault.json")


# ═══════════════════════════════════════════════════════════════
# §1  CORPORATE STANDARD — THE ATOMIC UNIT OF WISDOM
# ═══════════════════════════════════════════════════════════════

class CorporateStandard(BaseModel):
    """A Commander-approved cross-project learning.

    Only insights that pass Commander review become standards.
    Standards are automatically injected into future agent prompts
    based on domain and applicability matching.
    """
    standard_id: str = Field(..., description="Unique ID e.g. 'WV-20260403-1234'")
    domain: str = Field(..., description="tax | architecture | marketing | legal | financial | operations | branding | security")
    title: str = Field(..., description="One-line insight (e.g. 'SaaS companies should use Delaware C-Corp')")
    insight: str = Field(..., description="Full description of the corporate standard")
    source_project: str = Field("", description="Project that discovered this insight")
    source_agent: str = Field("", description="Agent that produced the insight (CFO, CTO, etc.)")
    applicability: str = Field("universal", description="universal | saas | ecommerce | ai_ml | marketplace | fintech")
    confidence: float = Field(0.8, ge=0.0, le=1.0, description="Confidence score (0-1)")
    status: str = Field("pending", description="pending | approved | rejected")
    approved_by: str = Field("", description="COMMANDER when approved")
    tags: List[str] = Field(default_factory=list, description="Searchable tags")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved_at: str = Field("", description="ISO timestamp of approval")


# ═══════════════════════════════════════════════════════════════
# §2  DOMAIN-AGENT MAPPING
# ═══════════════════════════════════════════════════════════════

AGENT_DOMAIN_MAP: Dict[str, List[str]] = {
    "CMO": ["marketing", "branding", "audience", "positioning"],
    "CFO": ["financial", "tax", "accounting", "pricing", "budgeting"],
    "CTO": ["architecture", "infrastructure", "security", "devops", "performance"],
    "CEO": ["strategy", "operations", "growth", "leadership"],
    "CLO": ["legal", "compliance", "ip", "regulatory"],
    "CRITIC": ["quality", "risk", "validation"],
}

# Reverse map: domain -> relevant agents
DOMAIN_AGENT_MAP: Dict[str, List[str]] = {}
for agent, domains in AGENT_DOMAIN_MAP.items():
    for domain in domains:
        DOMAIN_AGENT_MAP.setdefault(domain, []).append(agent)


# ═══════════════════════════════════════════════════════════════
# §3  WISDOM VAULT — THE CURATED STORE
# ═══════════════════════════════════════════════════════════════

class WisdomVault:
    """Cross-project memory store for Commander-curated corporate standards.

    The Vault is the curated layer above institutional_memory.py.
    Raw lessons are auto-captured; the Vault only stores explicitly
    approved insights that become "Corporate Law" for future projects.
    """

    def __init__(self, vault_path: str = None):
        self.vault_path = vault_path or VAULT_FILE
        self._ensure_dir()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)

    def _load(self) -> List[Dict]:
        try:
            with open(self.vault_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save(self, records: List[Dict]):
        self._ensure_dir()
        with open(self.vault_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, default=str)

    # ── CRUD ──────────────────────────────────────────────────

    def save(self, standard: CorporateStandard) -> str:
        """Save a standard (pending or approved) to the vault."""
        records = self._load()
        # Upsert by standard_id
        existing_idx = next(
            (i for i, r in enumerate(records) if r.get("standard_id") == standard.standard_id),
            None,
        )
        if existing_idx is not None:
            records[existing_idx] = standard.model_dump()
        else:
            records.append(standard.model_dump())
        self._save(records)
        logger.info(f"[Vault] Saved: {standard.standard_id} ({standard.status})")
        return standard.standard_id

    def approve(self, standard_id: str) -> Optional[CorporateStandard]:
        """Commander approves a pending standard. Returns updated standard or None."""
        records = self._load()
        for r in records:
            if r.get("standard_id") == standard_id:
                r["status"] = "approved"
                r["approved_by"] = "COMMANDER"
                r["approved_at"] = datetime.now(timezone.utc).isoformat()
                self._save(records)
                logger.info(f"[Vault] APPROVED: {standard_id}")
                return CorporateStandard(**r)
        logger.warning(f"[Vault] Standard not found for approval: {standard_id}")
        return None

    def reject(self, standard_id: str) -> Optional[CorporateStandard]:
        """Commander rejects a pending standard. Returns updated standard or None."""
        records = self._load()
        for r in records:
            if r.get("standard_id") == standard_id:
                r["status"] = "rejected"
                self._save(records)
                logger.info(f"[Vault] REJECTED: {standard_id}")
                return CorporateStandard(**r)
        logger.warning(f"[Vault] Standard not found for rejection: {standard_id}")
        return None

    def get_approved(self, domain: str = None, applicability: str = None) -> List[CorporateStandard]:
        """Get approved standards, optionally filtered by domain and/or applicability."""
        records = self._load()
        results = [r for r in records if r.get("status") == "approved"]
        if domain:
            results = [r for r in results if r.get("domain") == domain]
        if applicability:
            results = [
                r for r in results
                if r.get("applicability") in (applicability, "universal")
            ]
        return [CorporateStandard(**r) for r in results]

    def get_pending(self) -> List[CorporateStandard]:
        """Get standards awaiting Commander review."""
        records = self._load()
        return [CorporateStandard(**r) for r in records if r.get("status") == "pending"]

    def get_all(self) -> List[CorporateStandard]:
        """Get all standards regardless of status."""
        return [CorporateStandard(**r) for r in self._load()]

    # ── INJECTION ─────────────────────────────────────────────

    def inject_corporate_standards(
        self,
        agent_name: str,
        project_type: str = "universal",
    ) -> str:
        """Build a prompt block of relevant approved standards for an agent.

        Filters by:
        1. Domain relevance to the agent (CMO → marketing, CFO → financial)
        2. Project type applicability (saas, ecommerce, universal)

        Returns:
            Formatted text block for prompt injection, or "" if no standards match.
        """
        relevant_domains = AGENT_DOMAIN_MAP.get(agent_name, [])
        if not relevant_domains:
            return ""

        all_approved = self.get_approved()
        matched = []
        for std in all_approved:
            # Domain match
            if std.domain not in relevant_domains:
                continue
            # Applicability match (universal standards always apply)
            if std.applicability not in (project_type, "universal"):
                continue
            matched.append(std)

        if not matched:
            return ""

        lines = [f"=== CORPORATE STANDARDS ({len(matched)} applicable) ==="]
        for std in matched:
            conf_bar = "█" * int(std.confidence * 10)
            lines.append(
                f"[{std.domain.upper()}] {std.title}\n"
                f"  Insight: {std.insight[:300]}\n"
                f"  Confidence: {conf_bar} ({std.confidence:.0%}) | Source: {std.source_agent}/{std.source_project}\n"
                f"  YOU MUST incorporate this standard into your analysis."
            )
        lines.append("=== END CORPORATE STANDARDS ===")
        return "\n".join(lines)

    # ── AUTO-PROPOSAL ─────────────────────────────────────────

    def propose_from_report(self, report) -> Optional[CorporateStandard]:
        """Analyze an agent report and propose a corporate standard.

        Criteria:
        1. Report confidence >= 0.7
        2. Contains a clear recommendation (not REJECT or UNKNOWN)
        3. Not a duplicate of existing standards (title similarity < 0.8)

        Args:
            report: WarRoomReport instance

        Returns:
            CorporateStandard (status="pending") or None
        """
        # Must have structured data
        if not report.detailed_report or not isinstance(report.detailed_report, dict):
            return None

        # Confidence threshold
        if (report.confidence or 0) < 0.7:
            return None

        # Must have affirmative recommendation
        if report.recommendation in ("REJECT", "UNKNOWN", None):
            return None

        # Extract candidate insight
        insight_text = (
            report.detailed_report.get("executive_summary")
            or report.detailed_report.get("strategic_direction")
            or report.detailed_report.get("market_strategy")
            or report.detailed_report.get("profitability_timeline")
            or report.summary_report
            or ""
        )
        if not insight_text or len(insight_text) < 20:
            return None

        # Build title from the agent's key finding
        title = insight_text[:120].strip()
        if len(title) > 100:
            title = title[:100] + "..."

        # Determine domain from agent
        agent_upper = report.agent.upper() if report.agent else ""
        domains = AGENT_DOMAIN_MAP.get(agent_upper, [])
        domain = domains[0] if domains else "operations"

        # Duplicate check
        existing = self.get_all()
        for ex in existing:
            similarity = SequenceMatcher(None, title.lower(), ex.title.lower()).ratio()
            if similarity > 0.8:
                logger.debug(f"[Vault] Duplicate detected: {title[:50]}... ≈ {ex.title[:50]}...")
                return None

        # Create pending standard
        ts = datetime.now(timezone.utc)
        standard = CorporateStandard(
            standard_id=f"WV-{ts.strftime('%Y%m%d%H%M%S')}-{hash(title) % 10000:04d}",
            domain=domain,
            title=title,
            insight=insight_text[:1000],
            source_project=report.project_id or "",
            source_agent=agent_upper,
            applicability="universal",
            confidence=report.confidence or 0.7,
            status="pending",
            tags=[domain, agent_upper.lower(), report.project_id or ""],
            created_at=ts.isoformat(),
        )
        self.save(standard)
        logger.info(f"[Vault] Proposed: {standard.standard_id} — {title[:60]}...")
        return standard


# ═══════════════════════════════════════════════════════════════
# §4  MODULE-LEVEL SINGLETON
# ═══════════════════════════════════════════════════════════════

_vault = None

def get_wisdom_vault() -> WisdomVault:
    """Get or create the global WisdomVault singleton."""
    global _vault
    if _vault is None:
        _vault = WisdomVault()
    return _vault
