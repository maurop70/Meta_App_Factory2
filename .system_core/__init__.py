"""
.system_core — Antigravity Global Skills Package
═══════════════════════════════════════════════════
The canonical, factory-level implementations of reusable
skills that all child projects inherit via symbolic links.

Modules:
    pii_masker      → PII & secrets redaction (from Sentinel_Bridge)
    visual_engine   → Document & visual asset generation (Nano Banana 2)
    market_crawler  → Market research & competitive intelligence

Part of: Venture Studio Inheritance Engine — Phase 1
"""

from .pii_masker import PIIMasker
from .visual_engine import VisualEngine
from .market_crawler import MarketCrawler

__all__ = ["PIIMasker", "VisualEngine", "MarketCrawler"]
