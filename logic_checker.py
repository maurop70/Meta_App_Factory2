"""
logic_checker.py — Native Triad Module 1
═════════════════════════════════════════
Cross-references CMO strategy vs CFO Budget.
Identifies logical contradictions (e.g. "Low CAC" vs $50+ actual CAC).
"""

def evaluate_logic(cmo_strategy: str, cfo_budget: dict) -> dict:
    """
    Evaluates business plan contradictions.
    Returns: {"status": "PASS" | "FAIL", "errors": [...]}
    """
    mismatches = []
    cmo_lower = cmo_strategy.lower()
    
    # 1. CAC Contradiction
    if "low cac" in cmo_lower or "organic" in cmo_lower:
        cac = cfo_budget.get("cac", 0)
        # Assuming typical thresholds for budget mismatch
        if cac >= 50:
            mismatches.append(f"LOGIC_MISMATCH: CMO strategy implies Low CAC, but CFO budget shows ${cac} per lead.")
            
    # 2. Aggressive Growth Contradiction
    if "aggressive growth" in cmo_lower or "blitz" in cmo_lower:
        marketing_spend = cfo_budget.get("marketing_cost", 0)
        if marketing_spend < 5000:
            mismatches.append(f"LOGIC_MISMATCH: Aggressive growth requires significant ad spend, but CFO mapped only ${marketing_spend}.")

    if mismatches:
        return {"status": "FAIL", "errors": mismatches}
        
    return {"status": "PASS", "errors": []}
