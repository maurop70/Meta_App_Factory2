---
name: ReportingSkill
description: The "Messenger". Formats the system's raw decision data into human-readable reports (Markdown/Text).
---

# ReportingSkill

## 1. Purpose

To bridge the gap between "System Logic" and "User Understanding". It takes the complex JSON output from Loki and generates a clear, concise executive summary.

## 2. Inputs

- `loki_decision` (dict): The full output payload from the Meta-Skill.

## 3. Outputs

- `report_markdown` (str): A formatted Markdown string ready for display.
- `report_text` (str): A plain text summary (for logs or SMS).

## 4. Templates

- **Executive Summary**: 1-sentence status (e.g., "Status: GO - Sell Iron Condor").
- **Deep Dive**: Full breakdown of Volatility, Sentiment, and Risk.
