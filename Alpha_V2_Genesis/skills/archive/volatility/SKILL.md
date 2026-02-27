---
name: VolatilitySkill
description: The "Quant" of the system. Analyzes Volatility, Probability, and Skew.
---

# VolatilitySkill

## 1. Purpose

To calculate the statistical probability of success for trades. This skill ignores news and focuses purely on math: Greeks, IV Rank, and Expected Moves.

## 2. Inputs

- `market_data` (from MarketDataSkill): Price history and Option Chains.
- `target_expiration` (date): Date to forecast.

## 3. Outputs

- `volatility_analysis` (dict):
  - `iv_status`: "Low" (<20%), "Normal", "High" (>80%).
  - `iv_rank`: float (0-100).
  - `expected_move_7d`: float (Points).
  - `signal`: "BUY_PREMIUM" (if IV High) or "SELL_PREMIUM" (If IV High & Stable) or "WAIT" (If IV Spiking).

## 4. Key Logic (The "Brain")

- **IV Rank**: (Current - Low_30d) / (High_30d - Low_30d).
- **Mean Reversion**: If IV > 30, assume it will drift down. If IV < 11, assume it will spike.
