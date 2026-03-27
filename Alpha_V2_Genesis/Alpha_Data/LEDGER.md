# ALPHA V2 GENESIS - STRATEGY LEDGER
**Generated:** 2026-03-27 16:54:44  |  **Engine:** Lead Quant Architect v2.0

---

## EXECUTIVE SUMMARY

| Metric | Value |
| :--- | :--- |
| **Portfolio Health** | GREEN |
| **Open Positions** | 2 |
| **SPX Spot** | 6,368.85 |
| **VIX** | 31.05 (RISING) |
| **IV Rank (52W)** | 37.8% |
| **IV-HV Spread** | +17.2pp (Seller Edge) |
| **N8N System Health** | UNKNOWN (0 failures in log) |
| **Last Hot Updates** | 0 n8n pushes detected |

---

## THE ELABORATED LEDGER (Log Intelligence)

> System parsed `alpha.log`. Health: **UNKNOWN**

---

## ACTIVE TRADE REPORTS

### exec_1774625614

| | |
| :--- | :--- |
| **Strategy** | 35 DTE Iron Condor |
| **Opened** | 2026-03-27 |
| **Expires** | 2026-05-01 (35 DTE remaining) |
| **Credit Received** | $10.20 |
| **Current Mark** | $9.8 |
| **P&L So Far** | +$0.40 (3.9% of max profit) |
| **50% Profit Target** | $5.10 mark |
| **21-DTE Exit Date** | 2026-04-10 |
| **Strikes** | 5975/6000 Put · 6800/6825 Call |

**Position Greeks (Black-Scholes, Live)**

| Greek | Value | Meaning |
| :--- | :---: | :--- |
| **Theta** (θ) | `+$-17.23/day` | $17.23/day income from time decay |
| **Vega** (ν) | `$53.66/pp` | $53.66 P&L change per 1pp VIX move (gain on vol expansion) |
| **Delta** (δ) | `+0.80/pt` | Position is near delta-neutral ($0.80/pt) |
| **Gamma** (γ) | `0.0000581` | Convexity risk per $1 SPX move |

**Entry Rating at Open: [A] GOOD ENTRY** (Score: 5/9)

**Reasons FOR the trade:**

- IV Rank 38%: moderate — acceptable premium for 45-DTE
- IV-HV spread +17.2pp: market significantly over-pricing vol vs realized — strong seller edge
- Short put 5.8% OTM — adequate buffer
- Short call 6.8% OTM (431 pts) — upside well protected
- 35 DTE: optimal theta/gamma ratio for Core Income strategy

**Risks at entry:**

- VIX trending UP (3-day) — short-term headwind; mark-to-market may go negative before recovering

**Daily Thesis Update: [OK] THESIS INTACT** (Drift Score: +2)

- STABLE: SPX has moved only +0.0% — original thesis intact
- EDGE: IV-HV spread remains +17.2pp — seller advantage intact

**Challenger Scan: HOLD CURRENT**

| | Current | Challenger |
| :--- | :---: | :---: |
| Short Put | 6000 | 5730 |
| Short Call | 6800 | 7040 |
| Credit | $10.20 | $6.10 |
| Put Margin | 5.79% | 10.03% |
| Expiry | 2026-05-01 | 2026-05-08 |

> HOLD CURRENT: Existing position is competitive or superior. No pivot justified.

---

### exec_1774626782

| | |
| :--- | :--- |
| **Strategy** | 48 DTE Iron Condor |
| **Opened** | 2026-03-27 |
| **Expires** | 2026-05-15 (49 DTE remaining) |
| **Credit Received** | $4.95 |
| **Current Mark** | $5.95 |
| **P&L So Far** | +$-1.00 (-20.2% of max profit) |
| **50% Profit Target** | $2.48 mark |
| **21-DTE Exit Date** | 2026-04-24 |
| **Strikes** | 5875/5890 Put · 6915/6930 Call |

**Position Greeks (Black-Scholes, Live)**

| Greek | Value | Meaning |
| :--- | :---: | :--- |
| **Theta** (θ) | `+$-8.54/day` | $8.54/day income from time decay |
| **Vega** (ν) | `$34.81/pp` | $34.81 P&L change per 1pp VIX move (gain on vol expansion) |
| **Delta** (δ) | `+0.23/pt` | Position is near delta-neutral ($0.23/pt) |
| **Gamma** (γ) | `0.0000271` | Convexity risk per $1 SPX move |

**Entry Rating at Open: [A+] STRONG ENTRY** (Score: 6/9)

**Reasons FOR the trade:**

- IV Rank 38%: moderate — acceptable premium for 45-DTE
- IV-HV spread +17.2pp: market significantly over-pricing vol vs realized — strong seller edge
- Short put 7.5% OTM (478 pts) — requires 8 consecutive avg-size down days to breach
- Short call 8.6% OTM (546 pts) — upside well protected
- 49 DTE: optimal theta/gamma ratio for Core Income strategy

**Risks at entry:**

- VIX trending UP (3-day) — short-term headwind; mark-to-market may go negative before recovering

**Daily Thesis Update: [OK] THESIS INTACT** (Drift Score: +2)

- STABLE: SPX has moved only +0.0% — original thesis intact
- EDGE: IV-HV spread remains +17.2pp — seller advantage intact

**Challenger Scan: PIVOT RECOMMENDED**

| | Current | Challenger |
| :--- | :---: | :---: |
| Short Put | 5890 | 5730 |
| Short Call | 6915 | 7040 |
| Credit | $4.95 | $6.10 |
| Put Margin | 7.52% | 10.03% |
| Expiry | 2026-05-15 | 2026-05-08 |

> PIVOT RECOMMENDED: Challenger offers significantly better margin at comparable credit.

---

## ACTIVE RECOMMENDATIONS

- **PIVOT ALERT** on position(s): exec_1774626782 — See Challenger Scan section above.

---

## IMPLEMENTATION NOTES

- **N8N Daily Cron**: Set a Schedule Trigger in n8n → runs daily at 09:15 EST (Mon-Fri)
  → Calls `POST http://<ngrok_url>/api/ledger/refresh` to trigger this engine remotely.
- **Log Brittleness**: N8N Genesis failures require the `alpha-research-v3` workflow to be **Active** in n8n Cloud.
  Run `python -m scripts.n8n_audit` to verify all webhooks are live.
- **Ledger State**: Persisted at `Alpha_Data/ledger_state.json` — survives server restarts.
- **Auto-trigger**: `infrastructure_supervisor.py` now watches `portfolio.json` for new trades
  and triggers this ledger engine when a new OPEN position is detected.

_Ledger engine: Alpha V2 Genesis Quant Architect v2.0 | Antigravity AI_