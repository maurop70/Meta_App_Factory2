"""
core_framework/ops_simulator.py — Fulfillment & Cold-Chain Cost Model (CIO dependency)
═══════════════════════════════════════════════════════════════════════════════════
Deterministically models the operational overhead of selling a perishable CPG
product online: 3PL fulfillment, shipping carriers, cold-chain spoilage, and
Shopify (storefront) transaction overhead. Spoilage is ALWAYS an explicit line
item — never buried inside a blended cost.

Usage:
    from core_framework.ops_simulator import OpsInputs, simulate_fulfillment
    sim = simulate_fulfillment(OpsInputs(...))
    # sim["line_items"] → [{name, cost, ...}], sim["cost_per_order"], sim["spoilage_rate"]
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Carrier:
    name: str
    cost_per_lb: float
    transit_days: float
    cold_chain_capable: bool = True


@dataclass
class OpsInputs:
    orders_per_month: int
    avg_order_weight_lb: float
    avg_order_value: float
    # 3PL
    pick_pack_fee_per_order: float
    storage_fee_per_order: float
    # cold-chain
    requires_cold_chain: bool = True
    target_temp_c: float = -18.0           # frozen default
    gel_pack_cost_per_order: float = 0.0
    insulated_box_cost_per_order: float = 0.0
    base_spoilage_rate: float = 0.0        # fraction lost in transit (explicit, not assumed)
    spoilage_buffer_rate: float = 0.0      # extra safety buffer stocked to cover spoilage
    # storefront
    shopify_fee_pct: float = 0.029         # 2.9% standard
    shopify_flat_fee: float = 0.30
    carriers: list = field(default_factory=list)   # list[Carrier]


def select_carrier(inp: OpsInputs):
    """Pick the lowest landed-cost carrier that satisfies cold-chain need.
    Returns (carrier, rationale)."""
    eligible = [c for c in inp.carriers
                if (c.cold_chain_capable or not inp.requires_cold_chain)]
    if not eligible:
        return None, "No carrier meets the cold-chain requirement."
    best = min(eligible, key=lambda c: c.cost_per_lb * inp.avg_order_weight_lb)
    rationale = (
        f"Selected {best.name}: lowest landed cost "
        f"(${round(best.cost_per_lb * inp.avg_order_weight_lb, 2)}/order at "
        f"{inp.avg_order_weight_lb} lb), {best.transit_days}-day transit"
        + (", cold-chain capable" if best.cold_chain_capable else "")
        + "."
    )
    return best, rationale


def simulate_fulfillment(inp: OpsInputs) -> dict:
    """Deterministic per-order + monthly fulfillment cost model with explicit
    spoilage, carrier, and Shopify line items."""
    carrier, carrier_rationale = select_carrier(inp)
    carrier_cost = round((carrier.cost_per_lb * inp.avg_order_weight_lb), 2) if carrier else 0.0

    cold_chain_cost = round(inp.gel_pack_cost_per_order + inp.insulated_box_cost_per_order, 2) \
        if inp.requires_cold_chain else 0.0

    # Spoilage cost = (base spoilage + buffer) applied to order value (lost goods).
    effective_spoilage_rate = round(inp.base_spoilage_rate + inp.spoilage_buffer_rate, 4)
    spoilage_cost = round(inp.avg_order_value * effective_spoilage_rate, 2)

    shopify_overhead = round(inp.avg_order_value * inp.shopify_fee_pct + inp.shopify_flat_fee, 2)

    threepl_cost = round(inp.pick_pack_fee_per_order + inp.storage_fee_per_order, 2)

    line_items = [
        {"name": "3PL Pick/Pack + Storage", "cost_per_order": threepl_cost},
        {"name": f"Carrier ({carrier.name if carrier else 'NONE'})", "cost_per_order": carrier_cost},
        {"name": "Cold-Chain Packaging (gel + insulated box)", "cost_per_order": cold_chain_cost},
        {"name": "Spoilage (incl. buffer)", "cost_per_order": spoilage_cost},
        {"name": "Shopify Transaction Overhead", "cost_per_order": shopify_overhead},
    ]
    cost_per_order = round(sum(li["cost_per_order"] for li in line_items), 2)
    monthly_cost = round(cost_per_order * inp.orders_per_month, 2)

    return {
        "line_items": line_items,
        "cost_per_order": cost_per_order,
        "monthly_fulfillment_cost": monthly_cost,
        "spoilage_rate": effective_spoilage_rate,
        "carrier": {"name": carrier.name if carrier else None, "rationale": carrier_rationale},
        "cold_chain": {
            "required": inp.requires_cold_chain,
            "target_temp_c": inp.target_temp_c,
            "spoilage_buffer_rate": inp.spoilage_buffer_rate,
        },
        "speculative": False,
    }


def build_ops_blueprint(inp: OpsInputs,
                        storefront: str = "Shopify",
                        threepl: str = "3PL Cold-Storage Partner",
                        erp: str = "Core B2B ERP") -> dict:
    """Assemble the CIO Operational & Fulfillment Integration Blueprint that the
    structural Critic gate requires (API specs + cold-chain + carriers)."""
    sim = simulate_fulfillment(inp)
    carrier, rationale = select_carrier(inp)
    return {
        "api_integrations": [
            {"from": storefront, "to": threepl, "interface": "REST webhook",
             "params": {"endpoint": "/orders/create", "auth": "HMAC webhook signature",
                        "payload": "order_id, sku, qty, ship_to, temp_class"}},
            {"from": threepl, "to": erp, "interface": "REST/SFTP sync",
             "params": {"endpoint": "/inventory/adjust", "auth": "API key",
                        "payload": "sku, on_hand, lot, expiry"}},
            {"from": storefront, "to": erp, "interface": "REST",
             "params": {"endpoint": "/sales/post", "auth": "OAuth2",
                        "payload": "order_id, revenue, tax, customer"}},
        ],
        "cold_chain": {
            "target_temp_c": inp.target_temp_c,
            "spoilage_buffer_rate": inp.spoilage_buffer_rate,
            "base_spoilage_rate": inp.base_spoilage_rate,
            "packaging": "gel packs + insulated liner",
        },
        "carriers": [{
            "name": carrier.name if carrier else None,
            "cost_per_order": round((carrier.cost_per_lb * inp.avg_order_weight_lb), 2) if carrier else 0.0,
            "transit_days": carrier.transit_days if carrier else None,
            "rationale": rationale,
        }],
        "cost_model": sim,
    }
