---
name: SentimentSkill
description: The "Analyst". Parses news, earnings calendar, and global events.
---

# SentimentSkill

## 1. Purpose

To provide the qualitative context that math misses. This agent determines if the market is driven by Fear or Greed and identifies upcoming "Event Risks" (Earnings, Fed).

## 2. Inputs

- `news_stream` (list): Headlines from MarketDataSkill.
- `calendar` (dict): Upcoming events.

## 3. Outputs

- `sentiment_analysis` (dict):
  - `score`: float (-1.0 to 1.0).
  - `bias`: "Bullish", "Bearish", "Neutral".
  - `narrative`: Summary string (e.g., "Tech sector weakness driving fear").
  - `event_risk`: bool (True if major event in < 48h).

## 4. Key Logic

- **Keyword Scoring**: Score words like "Crash", "Surge", "Inflation".
- **Event Awareness**: If 'Fed Meeting' or 'CPI' is < 2 days away -> `event_risk = True`.
- **Contrarian Check**: If Score is Extreme (>0.9 or <-0.9), flag as "Overreaction".
