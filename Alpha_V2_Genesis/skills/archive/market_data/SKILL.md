---
name: MarketDataSkill
description: The "Senses" of the Alpha System. Fetches raw market data, option chains, and news.
---

# MarketDataSkill

## 1. Purpose

To serve as the single source of truth for all external data. This skill handles the connections to APIs (yfinance, etc.), manages rate limits, and normalizes data for other skills.

## 2. Inputs

- `tickers` (list): Symbols to fetch (e.g., ["^SPX", "^VIX"]).
- `data_type` (str): "price", "chain", "news".
- `lookback` (str): Period for historical data (e.g., "30d").

## 3. Outputs

- `market_state` (dict):
  - `current_price`: float
  - `history`: pd.DataFrame (JSON serialized)
  - `iv_surface`: dict (Strike -> IV)
  - `news_stream`: list of dicts

## 4. Constraints

- **Reliability**: Must implement validation. If `yfinance` fails, return strict ERROR, do not guess.
- **Speed**: Cache requests for 60 seconds to prevent API bans.
