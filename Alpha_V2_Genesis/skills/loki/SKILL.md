---
name: MetaSkill
description: "Loki". The Coordinator that synthesizes inputs and makes final decisions.
---

# MetaSkill (Loki)

## 1. Purpose

To act as the conductor of the orchestra. Loki does not generate data; he weighs the opinions of his specialists to form a coherent strategy.

## 2. Inputs

- `volatility_signal` (from VolatilitySkill).
- `sentiment_signal` (from SentimentSkill).
- `market_data` (from MarketDataSkill).
- `risk_veto` (from RiskSkill).

## 3. Outputs

- `final_decision` (dict):
  - `action`: "OPEN_TRADE", "CLOSE_TRADE", "WAIT".
  - `strategy`: "Iron Condor", "Put Credit Spread", etc.
  - `confidence`: float (0-100%).
  - `rationale`: Human-readable explanation.

## 4. Decision Logic (The "Vote")

- **Consensus**: If Volatility AND Sentiment agree -> High Confidence.
- **Conflict**:
  - If Volatility says "Sell Premium" but Sentiment says "Fear" -> Loki checks Risk.
  - If Risk says "Safe", Loki executes but with *Reduced Size*.
- **Veto**: If RiskSkill says "No", Loki returns "WAIT" immediately.
