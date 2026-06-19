"""
core_framework/syndicated_data.py — Syndicated Category Data (SPINS / Nielsen)
═════════════════════════════════════════════════════════════════════════════
Ingests SPINS/Nielsen category-velocity data and validates TAM/SAM/SOM sizing.
If live credentials (SPINS_API_KEY / NIELSEN_API_KEY) are configured it will use
them; otherwise it loads a bundled sandbox sample so downstream TAM/SAM/SOM
validation can run offline. Sandbox rows are explicitly flagged `source="sandbox"`.

Usage:
    from core_framework.syndicated_data import ingest_category_velocities, validate_tam_sam_som
    data = ingest_category_velocities("frozen novelty snacks")
    sizing = validate_tam_sam_som(data, sam_fraction=0.15, som_fraction=0.02)
"""

from __future__ import annotations

import os
import logging

logger = logging.getLogger("syndicated_data")

# Bundled sandbox sample — representative SPINS-style category velocities.
# Values are illustrative sandbox figures, NOT live market data.
_SANDBOX = {
    "frozen novelty snacks": [
        {"category": "Frozen Novelty Snacks", "dollar_sales_52wk": 4_200_000_000,
         "unit_velocity_per_store_per_week": 38.4, "pct_change_yoy": 6.1, "source": "sandbox"},
        {"category": "Better-For-You Frozen", "dollar_sales_52wk": 1_150_000_000,
         "unit_velocity_per_store_per_week": 12.7, "pct_change_yoy": 11.3, "source": "sandbox"},
    ],
    "frozen chocolate-covered fruit": [
        {"category": "Frozen Chocolate-Covered Fruit", "dollar_sales_52wk": 310_000_000,
         "unit_velocity_per_store_per_week": 7.9, "pct_change_yoy": 18.5, "source": "sandbox"},
    ],
}

_DEFAULT_SANDBOX = [
    {"category": "General CPG Category", "dollar_sales_52wk": 500_000_000,
     "unit_velocity_per_store_per_week": 10.0, "pct_change_yoy": 4.0, "source": "sandbox"},
]


def _live_ingest(category: str):
    """Hook for live SPINS/Nielsen ingestion. Returns [] if no creds/endpoint.
    (Left as a thin shim — wire the real endpoint when credentials are provisioned.)"""
    spins_key = os.getenv("SPINS_API_KEY", "")
    nielsen_key = os.getenv("NIELSEN_API_KEY", "")
    if not (spins_key or nielsen_key):
        return []
    # Real HTTP ingestion would go here; intentionally not fabricated.
    logger.info("SPINS/Nielsen credentials present but live ingestion not yet wired.")
    return []


def ingest_category_velocities(category: str) -> dict:
    """Return {category, velocities:[...], source}. Always yields >=1 velocity point."""
    live = _live_ingest(category)
    if live:
        return {"category": category, "velocities": live, "source": "live"}
    key = (category or "").strip().lower()
    rows = _SANDBOX.get(key)
    if not rows:
        # Substring match, else default.
        for k, v in _SANDBOX.items():
            if k in key or key in k:
                rows = v
                break
    rows = rows or _DEFAULT_SANDBOX
    return {"category": category, "velocities": list(rows), "source": "sandbox"}


def validate_tam_sam_som(data: dict, sam_fraction: float = 0.15, som_fraction: float = 0.02) -> dict:
    """Derive TAM/SAM/SOM from the largest category dollar-sales figure.
    SAM/SOM are explicit fractions of TAM (no hidden assumptions)."""
    velocities = (data or {}).get("velocities") or []
    if not velocities:
        return {"valid": False, "error": "No category velocity data points ingested."}
    tam = max(v.get("dollar_sales_52wk", 0) for v in velocities)
    sam = round(tam * sam_fraction, 2)
    som = round(tam * som_fraction, 2)
    return {
        "valid": tam > 0,
        "tam": tam,
        "sam": sam,
        "som": som,
        "sam_fraction": sam_fraction,
        "som_fraction": som_fraction,
        "data_points": len(velocities),
        "source": data.get("source"),
    }
