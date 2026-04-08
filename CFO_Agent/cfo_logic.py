from pydantic import BaseModel, Field
from typing import List, Optional

# ═══════════════════════════════════════════════════════════════
#  SCHEMA DEFINITIONS
# ═══════════════════════════════════════════════════════════════

class CMOPayload(BaseModel):
    total: float = 0.0
    allocated: float = 0.0
    categories: dict = {}

class ArchitectRiskPayload(BaseModel):
    structural_score: float = 70.0
    logic_score: float = 70.0
    security_score: float = 70.0
    composite_score: float = 70.0

class CampaignItem(BaseModel):
    name: str = "Unknown"
    budget: float = 0.0
    projected_revenue: float = 0.0

class FinancialPayload(BaseModel):
    """Strictly validates the incoming JSON from Phantom QA tests and Sentinel Relays."""
    cmo_spend: CMOPayload
    architect_risk: ArchitectRiskPayload
    campaign_list: List[CampaignItem] = []
    
    # Optional explicitly financial fields for Phase 2 strict hardening
    cash_on_hand: float = 0.0
    mrr: float = 0.0
    opex: float = 0.0
    liabilities: float = 0.0

class CampaignResult(BaseModel):
    name: str
    budget: float
    projected_revenue: float
    roi_pct: float
    npv: float
    risk_adjusted_roi: float
    irr_note: str

class CFOAnalysisResult(BaseModel):
    """Strict output schema. Passed completely or partially via Excel schema mapping."""
    burn_rate: float
    runway_months: float
    gross_margin: float
    total_roi_pct: float
    fragility_index: float
    composite_score: float
    spend_utilization_pct: float
    unallocated: float
    total_spend: float
    total_revenue: float
    campaigns: List[CampaignResult]
    volatile_variables: List[str]

# ═══════════════════════════════════════════════════════════════
#  PURE FINANCIAL MATHEMATICS
# ═══════════════════════════════════════════════════════════════

DISCOUNT_RATE = 0.10

def calculate_financial_health(data: FinancialPayload) -> CFOAnalysisResult:
    """
    Deterministic Python module for all financial arithmetic.
    LLMs must use the output of this function.
    """
    
    # ── Legacy/Core Math (from cfo_engine.py logic)
    cmo = data.cmo_spend
    risk = data.architect_risk
    camps = data.campaign_list

    # Compute Fragility Index & Volatilities
    composite = risk.composite_score
    fragility_index = round(100.0 - composite, 1)

    volatile_vars = []
    if risk.structural_score < 70: volatile_vars.append("Structural Integrity (Volatility > 1.5x SD)")
    if risk.logic_score < 70: volatile_vars.append("Logic Coherence (Volatility > 1.5x SD)")
    if risk.security_score < 70: volatile_vars.append("Credit Spreads & Security (Volatility > 1.5x SD)")
    if fragility_index > 30: volatile_vars.append("VIX / Tail Risk (Volatility > 1.5x SD)")

    # Compute Campaign Analysis
    campaign_results = []
    total_spend = 0.0
    total_revenue = 0.0
    for c in camps:
        spend = c.budget
        rev = c.projected_revenue
        total_spend += spend
        total_revenue += rev

        roi = round(((rev - spend) / spend) * 100, 2) if spend > 0 else 0.0
        npv = round(rev / (1 + DISCOUNT_RATE) - spend, 2)
        risk_adj_roi = round(roi * (composite / 100), 2)

        campaign_results.append(
            CampaignResult(
                name=c.name,
                budget=spend,
                projected_revenue=rev,
                roi_pct=roi,
                npv=npv,
                risk_adjusted_roi=risk_adj_roi,
                irr_note='Single-period IRR = ROI%' if spend > 0 else 'N/A'
            )
        )

    portfolio_roi = round(((total_revenue - total_spend) / total_spend) * 100, 2) if total_spend > 0 else 0.0
    unallocated = round(cmo.total - cmo.allocated, 2)
    spend_util_pct = round((cmo.allocated / cmo.total) * 100, 2) if cmo.total > 0 else 0.0

    # ── Phase 2 Math (Cash, Liabilities, MRR)
    # Default assumptions if raw financial data is omitted by the legacy payloads
    burn_rate = data.opex - data.mrr
    if burn_rate <= 0:
        runway_months = 999.0  # Profitable
    else:
        runway_months = round(data.cash_on_hand / burn_rate, 1) if burn_rate > 0 else 0.0

    gross_margin = round(((data.mrr - data.opex) / data.mrr) * 100, 2) if data.mrr > 0 else 0.0

    # Apply strict risk logic to explicitly penalize fragility based on Phase 2 math
    # Fragility score increases if runway < 6 months or debt exceeds cash reserves.
    if runway_months < 6.0 and runway_months != 999.0:
        fragility_index += 10.0
        volatile_vars.append("Severe Runway Risk (<6 Months)")
    
    if data.liabilities > data.cash_on_hand and data.cash_on_hand > 0:
        fragility_index += 5.0
        volatile_vars.append("Over-leveraged Risk (Debt > Cash)")
        
    fragility_index = min(fragility_index, 100.0)

    # Reconstruct the CFOAnalysisResult
    return CFOAnalysisResult(
        burn_rate=burn_rate,
        runway_months=runway_months,
        gross_margin=gross_margin,
        total_roi_pct=portfolio_roi,
        fragility_index=fragility_index,
        composite_score=composite,
        spend_utilization_pct=spend_util_pct,
        unallocated=unallocated,
        total_spend=total_spend,
        total_revenue=total_revenue,
        campaigns=campaign_results,
        volatile_variables=volatile_vars
    )
