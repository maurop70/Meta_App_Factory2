import logging

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RiskSkill")

class RiskAgent:
    def __init__(self):
        # Configuration
        self.MIN_IV_RANK = 20.0
        self.MAX_GAMMA_VIX = 25.0
        self.MAX_ALLOCATION_PCT = 0.30 
        self.MIN_AVAILABILITY = 2000 # Absolute minimum free capital required
    
    def evaluate_trade(self, trade_proposal, market_data, portfolio_state, availability=None):
        """
        Evaluates a proposed trade against safety rules.
        availability: Optional explicit check for free capital buffer.
        """
        rejection_reasons = []
        
        # 1. Volatility Floor Check (Don't sell cheap premium)
        iv_rank = market_data.get('vix_rank', 0)
        if trade_proposal['action'] == 'SELL_PREMIUM' and iv_rank < self.MIN_IV_RANK:
            rejection_reasons.append(f"IV Rank ({iv_rank}) is below threshold ({self.MIN_IV_RANK}). Premium is too cheap.")

        # 2. Gamma Cap (Don't trade 0-DTE in panic mode)
        vix = market_data.get('vix', 0)
        if trade_proposal.get('days_to_expiry', 7) < 1 and vix > self.MAX_GAMMA_VIX:
            rejection_reasons.append(f"VIX ({vix}) is too high for 0-DTE trading (Limit {self.MAX_GAMMA_VIX}).")

        # 3. Capital Allocation Check
        capital = portfolio_state.get('capital', 10000)
        margin_req = trade_proposal.get('margin', 0)
        if margin_req > (capital * self.MAX_ALLOCATION_PCT):
            rejection_reasons.append(f"Margin ({margin_req}) exceeds 30% allocation limit.")

        # 4. Safety Guard: Margin Lock
        action = trade_proposal.get('action', '').upper()
        is_risk_reducing = 'CLOSE' in action or 'REDUCE' in action

        if availability is not None and not is_risk_reducing:
             # Basic Solvency Check
             if margin_req > availability:
                  rejection_reasons.append(f"INSUFFICIENT FUNDS: Margin (${margin_req}) > Available (${availability}).")
             
             # Optional: Warn if dripping below threshold but don't block unless strict
             # For now, simply removing the "buffer" subtraction fixes the user's issue.
             elif availability < self.MIN_AVAILABILITY:
                  logger.warning(f"Low Availability (${availability}) < ${self.MIN_AVAILABILITY}, but allowing trade.")
            
        # Decision
        if rejection_reasons:
            return {
                "approved": False,
                "action": "VETO",
                "reasons": rejection_reasons
            }
        else:
            return {
                "approved": True,
                "action": "GO",
                "reasons": ["All checks passed."]
            }
