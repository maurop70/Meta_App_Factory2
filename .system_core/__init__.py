"""
.system_core — Antigravity Global Skills Package
═══════════════════════════════════════════════════
The canonical, factory-level implementations of reusable
skills that all child projects inherit via symbolic links.

Modules:
    pii_masker            → PII & secrets redaction (from Sentinel_Bridge)
    visual_engine         → Document & visual asset generation (Nano Banana 2)
    market_crawler        → Market research & competitive intelligence
    deploy_shield         → Deployment sanitization before third-party delivery
    wisdom_accumulator    → Institutional memory from Socratic persuasions
    kill_switch           → Emergency API key protection (panic/restore)

Part of: Venture Studio Inheritance Engine — Phase 1 + SOPs
"""

from .pii_masker import PIIMasker
from .visual_engine import VisualEngine
from .market_crawler import MarketCrawler
from .deploy_shield import DeployShield
from .wisdom_accumulator import WisdomAccumulator
from .kill_switch import KillSwitch

__all__ = [
    "PIIMasker", "VisualEngine", "MarketCrawler",
    "DeployShield", "WisdomAccumulator", "KillSwitch",
]
