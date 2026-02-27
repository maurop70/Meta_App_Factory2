# Alpha V2 Genesis — Agent Manifest

**Identity**: Autonomous Strategic Financial Intelligence System  
**Version**: 2.0 — Production Release  
**Last Updated**: 2026-02-23  
**Context**: "Wall Street Grade" SPX options strategy formulator and risk monitor.

---

## Capabilities

1. **Market Analysis**: Ingests live SPX/VIX data via `yfinance` and synthesizes a dual-strategy trade recommendation (Tactical 7-DTE or Core Income 45-DTE).
2. **Strategy Formulation**: Designs Iron Condor positions with dynamic wing width and strike selection based on VIX regime.
3. **AI Research Integration**: Polls n8n Cloud Brain (`alpha-research-v3`) for sentiment, macro outlook, and market bias during defined execution windows.
4. **Macro Risk Tracking**: Receives FOMC, BEA, and GDP event data from n8n Macro Event Tracker via `/api/hot_update`.
5. **Reporting**: Generates `market_memo.md` (Analyst Memo) and live `portfolio.json` updates.
6. **Self-Healing Infrastructure**: Auto-reprograms n8n webhook URL on every server restart via `self_heal_n8n()`.

---

## Integration Points

| System | Role | Communication |
| :--- | :--- | :--- |
| **n8n Cloud (Alpha Research V3)** | AI Research Brain | `POST` to `/webhook/alpha-research-v3` |
| **n8n Cloud (Macro Event Tracker)** | Economic Calendar | n8n `POST` to `/api/hot_update` |
| **ngrok** | External Tunnel | Auto-managed by `pyngrok` on startup |
| **React UI (alpha_ui)** | Dashboard | REST API on Port 5005 |
| **yfinance** | Market Data | Direct Python library calls |

---

## Budget & Execution Gates

- **Live Cloud Research**: Mon–Tue, 9:00 AM – 4:00 PM EST only.
- **Standby Mode**: All other times — local cache only, zero cloud cost.
- **Health Check Interval**: 5-minute ping throttle.
