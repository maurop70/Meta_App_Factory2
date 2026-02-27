---
name: WatchdogSkill
description: The "Monitor". Tracks active positions, calculates P&L, distance to strikes, and issues HOLD/CLOSE verdicts.
---

# WatchdogSkill

## 1. Purpose

To protect the user AFTER entry. It constantly monitors the "Distance to Danger" (delta/strike proximity) and financial performance.

## 2. Inputs

- `portfolio_state` (dict): The user's active trades (JSON from portfolio.json).
- `market_data` (dict): Current SPX Price and VIX.
- `vol_forecast` (dict): Prediction from VolatilityAgent (Rising/Falling).

## 3. Outputs

- `watchdog_report` (dict):
  - `status`: "SAFE", "WARNING", "DANGER".
  - `verdict`: "HOLD" or "CLOSE".
  - `distance_pct`: float (How far is spot from short strike?).
  - `pl_status`: "Winning" or "Losing" (Estimated).
  - `message`: Human readable advice (e.g., "HOLD: Safe distance (>2%). Volatility dropping.").

## 4. Logic (The "Bark")

- **Safety Zone**: If Spot is > 2% away from Short Strike -> SAFE.
- **Danger Zone**: If Spot is < 1% away -> DANGER (Consider Rolling/Closing).
- **Smart Exit**:
  - If `Profit > 50%` -> CLOSE (Take Profit).
  - If `Danger Zone` AND `Vol Forecast = Rising` -> CLOSE (Don't fight the trend).
  - If `Danger Zone` BUT `Vol Forecast = Falling` -> HOLD (Wait for mean reversion).
