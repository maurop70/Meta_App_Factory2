# ALPHA V2 GENESIS - STRATEGY LEDGER
**Generated:** 2026-03-20 17:02:51  |  **Engine:** Lead Quant Architect v2.0

---

## EXECUTIVE SUMMARY

| Metric | Value |
| :--- | :--- |
| **Portfolio Health** | GREEN |
| **Open Positions** | 1 |
| **SPX Spot** | 6,506.48 |
| **VIX** | 26.78 (RISING) |
| **IV Rank (52W)** | 28.7% |
| **IV-HV Spread** | +12.9pp (Seller Edge) |
| **N8N System Health** | UNKNOWN (0 failures in log) |
| **Last Hot Updates** | 0 n8n pushes detected |

---

## THE ELABORATED LEDGER (Log Intelligence)

> System parsed `alpha.log`. Health: **UNKNOWN**

---

## ACTIVE TRADE REPORTS

### exec_1774037257

| | |
| :--- | :--- |
| **Strategy** | 42 DTE IRON CONDOR |
| **Opened** | 2026-03-20 |
| **Expires** | 2026-05-01 (42 DTE remaining) |
| **Credit Received** | $7.85 |
| **Current Mark** | $1.3 |
| **P&L So Far** | +$6.55 (83.4% of max profit) |
| **50% Profit Target** | $3.92 mark |
| **21-DTE Exit Date** | 2026-04-10 |
| **Strikes** | 5975/6000 Put · 6975/6950 Call |

**Position Greeks (Black-Scholes, Live)**

| Greek | Value | Meaning |
| :--- | :---: | :--- |
| **Theta** (θ) | `+$14.00/day` | $14.00/day income from time decay |
| **Vega** (ν) | `$-33.09/pp` | $33.09 P&L change per 1pp VIX move (loss on vol expansion) |
| **Delta** (δ) | `-2.58/pt` | Position is near delta-neutral ($2.58/pt) |
| **Gamma** (γ) | `-0.0000212` | Convexity risk per $1 SPX move |

**Entry Rating at Open: [A] GOOD ENTRY** (Score: 4/9)

**Reasons FOR the trade:**

- IV-HV spread +12.9pp: market significantly over-pricing vol vs realized — strong seller edge
- Short put 7.8% OTM (506 pts) — requires 10 consecutive avg-size down days to breach
- Short call 7.2% OTM (468 pts) — upside well protected
- 42 DTE: optimal theta/gamma ratio for Core Income strategy

**Risks at entry:**

- IV Rank 29%: below median — premium is thin for the risk taken
- VIX trending UP (3-day) — short-term headwind; mark-to-market may go negative before recovering

**Daily Thesis Update: [OK] THESIS INTACT** (Drift Score: +2)

- STABLE: SPX has moved only +0.0% — original thesis intact
- EDGE: IV-HV spread remains +12.9pp — seller advantage intact

**Challenger Scan: HOLD CURRENT**

| | Current | Challenger |
| :--- | :---: | :---: |
| Short Put | 6000 | 5855 |
| Short Call | 6975 | 7190 |
| Credit | $7.85 | $0.00 |
| Put Margin | 7.78% | 10.01% |
| Expiry | 2026-05-01 | 2026-05-01 |

> HOLD CURRENT: Existing position is competitive or superior. No pivot justified.

---

## ACTIVE RECOMMENDATIONS

- No pivot alerts. All active positions are within thesis tolerance.
- Continue monitoring upcoming macro events.

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