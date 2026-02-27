---
name: RiskSkill
description: The "Guardian". Enforces safety rules, position sizing, and stop-losses.
---

# RiskSkill

## 1. Purpose

To be the "No-Man". It assesses every proposed trade against strict safety rules. It has VETO power over all other agents.

## 2. Inputs

- `proposed_trade` (dict): The strategy Loki wants to execute.
- `portfolio_state` (dict): Current positions and cash.
- `market_conditions` (dict): Volatility and Sentiment summary.

## 3. Outputs

- `risk_assessment` (dict):
  - `approved`: bool.
  - `reason`: str (e.g., "Rejection: IV Rank (15) < Threshold (20)").
  - `sizing_rec`: int (Max contracts allowed).
  - `stop_loss_level`: float (Price point).

## 4. Hard Rules (Immutable)

1. **IV Floor**: No selling premium if IV Rank < 20.
2. **Gamma Cap**: No 0-DTE trades if VIX > 25 (Too fast to manage).
3. **Diversification**: Max allocation in one ticker = 10% of NAV.
