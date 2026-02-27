"""
╔══════════════════════════════════════════════════════════════╗
║  ALPHA V2 GENESIS — STRATEGY LEDGER ENGINE                  ║
║  Lead Quantitative Architect Module                          ║
║                                                              ║
║  Responsibilities:                                           ║
║  1. Event-Triggered Trade Rationale Reports                  ║
║  2. Perpetual Daily Recalibration + Thesis Drift Detection   ║
║  3. Proactive Challenger Scan + Pivot Alerts                 ║
║  4. Structured output: LEDGER.md + ledger_state.json         ║
╚══════════════════════════════════════════════════════════════╝
"""
import os, sys, json, re, logging, time
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
try:
    from scipy.stats import norm
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False

# ── Path Setup ─────────────────────────────────────────────────
ROOT    = os.path.dirname(os.path.abspath(__file__))
DATA    = os.path.join(ROOT, "Alpha_Data")
LOG_SRC = os.path.join(ROOT, "alpha.log")
PORTFOLIO_PATH  = os.path.join(DATA, "portfolio.json")
EVENTS_PATH     = os.path.join(DATA, "upcoming_events.json")
STATE_PATH      = os.path.join(DATA, "ledger_state.json")
LEDGER_MD_PATH  = os.path.join(DATA, "LEDGER.md")
JOURNAL_PATH    = os.path.join(DATA, "trade_journal.json")

os.makedirs(DATA, exist_ok=True)

# ── Alert Manager (Priority 3) ──────────────────────────────────
try:
    from alert_manager import (
        alert_thesis_broken, alert_pivot_recommended,
        alert_dte_exit_window, alert_profit_target,
    )
    ALERTS_OK = True
except ImportError:
    ALERTS_OK = False
    # Define no-op stubs so code paths are always safe
    def alert_thesis_broken(*a, **k):   pass
    def alert_pivot_recommended(*a, **k): pass
    def alert_dte_exit_window(*a, **k): pass
    def alert_profit_target(*a, **k):   pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - Ledger - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(DATA, "ledger.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("StrategyLedger")

# ── Known Catalyst Calendar (next ~30 days from any given date) ──
CATALYST_CALENDAR = [
    ("2026-02-26", "Consumer Confidence (CB)",         "MED",  "Retail macro pulse"),
    ("2026-02-27", "Q4 GDP (2nd Estimate)",             "HIGH", "GDP surprise = SPX gap"),
    ("2026-02-28", "PCE Inflation",                     "HIGH", "Fed's preferred inflation metric"),
    ("2026-03-05", "ISM Services PMI",                  "MED",  "Economy health"),
    ("2026-03-07", "Nonfarm Payrolls",                  "HIGH", "Biggest monthly vol event"),
    ("2026-03-11", "CPI (Feb 2026)",                    "HIGH", "Inflation print — VIX spike risk"),
    ("2026-03-12", "PPI (Feb 2026)",                    "MED",  "Producer price feed-through"),
    ("2026-03-14", "Michigan Consumer Sentiment",       "MED",  "Inflation expectations"),
    ("2026-03-18", "FOMC Meeting (Day 1)",               "HIGH", "Rate decision — highest vol event"),
    ("2026-03-19", "FOMC Decision + Press Conference",  "HIGH", "Powell presser = VIX spike guaranted"),
]


# ══════════════════════════════════════════════════════════════════
# 0. BLACK-SCHOLES GREEKS ENGINE (Priority 1 upgrade)
# ══════════════════════════════════════════════════════════════════

def _fetch_risk_free_rate():
    """Fetches 10Y US Treasury yield as the risk-free rate proxy."""
    try:
        tnx = yf.Ticker("^TNX")
        hist = tnx.history(period="1d")
        return float(hist["Close"].iloc[-1]) / 100.0  # e.g. 4.25 → 0.0425
    except Exception:
        return 0.043  # Sensible default if fetch fails


def bs_greeks(flag, S, K, t, r, sigma):
    """
    Computes Black-Scholes analytical Greeks for a single option leg.

    Args:
        flag  : 'c' for call, 'p' for put
        S     : Underlying spot price (e.g. 6827.0)
        K     : Strike price
        t     : Time to expiry in YEARS (e.g. 46/365 = 0.126)
        r     : Risk-free rate as decimal (e.g. 0.043)
        sigma : Implied volatility as decimal (e.g. 0.22)

    Returns dict with:
        delta : Rate of change of option price vs underlying (per $1 SPX move)
        gamma : Rate of change of delta (convexity)
        theta : Daily P&L from time decay IN DOLLARS per $100 notional
        vega  : $ change per 1 percentage-point change in IV
    """
    if not SCIPY_OK or t <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "source": "unavailable"}

    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)

    pdf_d1 = norm.pdf(d1)

    if flag == 'c':
        delta = norm.cdf(d1)
        # Theta: daily dollar decay (divide annualised by 365)
        theta = (-(S * pdf_d1 * sigma) / (2 * np.sqrt(t))
                 - r * K * np.exp(-r * t) * norm.cdf(d2)) / 365
    else:  # put
        delta = norm.cdf(d1) - 1
        theta = (-(S * pdf_d1 * sigma) / (2 * np.sqrt(t))
                 + r * K * np.exp(-r * t) * norm.cdf(-d2)) / 365

    gamma = pdf_d1 / (S * sigma * np.sqrt(t))
    # Vega: $ change per 1pp move in IV (divide by 100 since sigma is in decimal)
    vega  = S * pdf_d1 * np.sqrt(t) / 100

    return {
        "delta": round(delta, 5),
        "gamma": round(gamma, 7),
        "theta": round(theta, 4),   # $/day per single option
        "vega":  round(vega, 4),    # $ per 1pp IV change per single option
        "source": "black_scholes"
    }


def compute_position_greeks(legs_with_greeks, multiplier=100):
    """
    Aggregates per-leg Black-Scholes Greeks into net POSITION Greeks for an Iron Condor.

    Args:
        legs_with_greeks : list of dicts with keys sign, delta, gamma, theta, vega
        multiplier       : contract multiplier (100 for SPX options = controls $100/pt)

    Returns net position Greeks scaled to dollar impact:
        net_delta  : ~0 at entry for a balanced IC ($ P&L per $1 SPX move)
        net_gamma  : should be negative for short IC (loses on large moves)
        net_theta  : should be POSITIVE ($/day income)
        net_vega   : should be NEGATIVE (loses when vol rises)
        pop        : rough probability of profit (1 - prob of touching short put)
    """
    net = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    for leg in legs_with_greeks:
        sign = leg.get("sign", 1)
        for g in ["delta", "gamma", "theta", "vega"]:
            net[g] += sign * leg.get(g, 0.0)

    # Scale to dollar impact per contract
    return {
        "net_delta_per_pt":   round(net["delta"] * multiplier, 2),
        "net_theta_per_day":  round(net["theta"] * multiplier, 2),
        "net_vega_per_pp":    round(net["vega"]  * multiplier, 2),
        "net_gamma":          round(net["gamma"], 7),
        "interpretation": {
            "theta":  f"${abs(round(net['theta']*multiplier,2)):.2f}/day income from time decay",
            "vega":   f"${abs(round(net['vega']*multiplier,2)):.2f} P&L change per 1pp VIX move ({'loss' if net['vega'] < 0 else 'gain'} on vol expansion)",
            "delta":  f"Position is {'bearish' if net['delta'] < -0.05 else 'bullish' if net['delta'] > 0.05 else 'near delta-neutral'} (${abs(round(net['delta']*multiplier,2)):.2f}/pt)",
        }
    }


# ══════════════════════════════════════════════════════════════════
# 1. MARKET DATA LAYER
# ══════════════════════════════════════════════════════════════════

def fetch_market_snapshot():
    """Fetches live SPX, VIX, IV Rank, HV30, and trend data."""
    spx_t = yf.Ticker("^GSPC")
    vix_t = yf.Ticker("^VIX")
    spx_1y = spx_t.history(period="1y")
    vix_1y = vix_t.history(period="1y")

    spx_now = float(spx_1y["Close"].iloc[-1])
    vix_now = float(vix_1y["Close"].iloc[-1])

    vix_hi  = float(vix_1y["High"].max())
    vix_lo  = float(vix_1y["Low"].min())
    vix_med = float(vix_1y["Close"].median())
    vix_avg = float(vix_1y["Close"].mean())
    iv_rank = ((vix_now - vix_lo) / (vix_hi - vix_lo)) * 100 if vix_hi > vix_lo else 50.0

    spx_ret = spx_1y["Close"].pct_change().dropna()
    hv30    = float(spx_ret.iloc[-30:].std() * np.sqrt(252) * 100)

    trend_5d  = float(((spx_now - spx_1y["Close"].iloc[-6]) / spx_1y["Close"].iloc[-6]) * 100)
    trend_30d = float(((spx_now - spx_1y["Close"].iloc[-23]) / spx_1y["Close"].iloc[-23]) * 100)

    vix_3d_chg = float(vix_now - vix_1y["Close"].iloc[-4])
    vix_trend  = "RISING" if vix_3d_chg > 0.5 else ("FALLING" if vix_3d_chg < -0.5 else "FLAT")

    daily_moves = spx_1y["Close"].pct_change().iloc[-20:] * 100
    avg_move    = float(daily_moves.abs().mean())

    return {
        "timestamp":   datetime.now().isoformat(),
        "spx":         round(spx_now, 2),
        "vix":         round(vix_now, 2),
        "iv_rank":     round(iv_rank, 1),
        "iv_pctile":   round(float((vix_1y["Close"] < vix_now).mean() * 100), 1),
        "hv30":        round(hv30, 1),
        "iv_hv_spread":round(vix_now - hv30, 1),
        "vix_hi_52w":  round(vix_hi, 1),
        "vix_lo_52w":  round(vix_lo, 1),
        "vix_median":  round(vix_med, 1),
        "vix_mean":    round(vix_avg, 1),
        "vix_trend":   vix_trend,
        "vix_3d_chg":  round(vix_3d_chg, 2),
        "trend_5d":    round(trend_5d, 2),
        "trend_30d":   round(trend_30d, 2),
        "avg_daily_move": round(avg_move, 2),
    }


def fetch_leg_data(expiry, legs, spot=None, r=None, compute_greeks=True):
    """
    Fetches live option marks, IV, and real Black-Scholes Greeks for each leg.
    spot: SPX spot price for BS calculation
    r   : risk-free rate (fetched live if None)
    """
    spx = yf.Ticker("^SPX")
    try:
        chain = spx.option_chain(expiry)
    except Exception as e:
        logger.warning(f"Option chain fetch failed for {expiry}: {e}")
        return []

    today    = datetime.now().date()
    exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
    t_years  = max((exp_date - today).days / 365.0, 1/365)  # at least 1 day
    rfr      = r if r is not None else _fetch_risk_free_rate()

    results = []
    for label, strike, opt_type, sign in legs:
        df = chain.calls if opt_type == "call" else chain.puts
        row = df[df["strike"] == strike]
        if row.empty:
            idx = (df["strike"] - strike).abs().idxmin()
            row = df.iloc[[idx]]
        bid   = float(row["bid"].values[0])
        ask   = float(row["ask"].values[0])
        mark  = (bid + ask) / 2
        iv_d  = float(row["impliedVolatility"].values[0])   # decimal (e.g. 0.22)
        iv_pc = round(iv_d * 100, 2)                         # percentage (e.g. 22.0)

        # Real Black-Scholes Greeks
        greeks = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "source": "unavailable"}
        if compute_greeks and spot and iv_d > 0:
            greeks = bs_greeks(
                flag  = 'c' if opt_type == 'call' else 'p',
                S     = spot,
                K     = float(strike),
                t     = t_years,
                r     = rfr,
                sigma = iv_d,
            )

        results.append({
            "label":  label, "strike": strike,
            "type":   opt_type, "sign": sign,
            "bid":    round(bid, 2), "ask": round(ask, 2),
            "mark":   round(mark, 2),
            "iv_pct": iv_pc,
            "iv_dec": round(iv_d, 5),
            # Real Greeks (per single option, unscaled)
            "delta":  greeks["delta"],
            "gamma":  greeks["gamma"],
            "theta":  greeks["theta"],
            "vega":   greeks["vega"],
            "greeks_source": greeks["source"],
        })
    return results


# ══════════════════════════════════════════════════════════════════
# 2. LOG PARSER — "The Elaborated Ledger" feed
# ══════════════════════════════════════════════════════════════════

def parse_alpha_log(max_lines=50):
    """
    Reads alpha.log and extracts key signals:
    - N8N failure bursts (brittleness indicator)
    - Loki confidence score trajectory
    - Hot update activity (n8n pushing data)
    - Server health events
    Returns a structured digest.
    """
    if not os.path.exists(LOG_SRC):
        return {"errors": [], "snapshots": [], "n8n_failures": 0, "hot_updates": 0, "health": "UNKNOWN"}

    try:
        with open(LOG_SRC, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-max_lines:]
    except Exception as e:
        return {"errors": [str(e)], "snapshots": [], "n8n_failures": 0, "hot_updates": 0, "health": "UNKNOWN"}

    errors        = []
    snapshots     = []
    n8n_failures  = 0
    hot_updates   = 0
    confidence_scores = []

    for line in lines:
        if "N8N Genesis Request Failed" in line or "ERROR" in line:
            n8n_failures += 1
            errors.append(line.strip())
        if "hot_update" in line and "200" in line:
            hot_updates += 1
        if "Alpha Confidence Score:" in line:
            m = re.search(r"Score: ([\d.]+)", line)
            if m:
                confidence_scores.append(float(m.group(1)))
        if "Snapshot:" in line and "spx" in line:
            m_spx = re.search(r"'spx': ([\d.]+)", line)
            m_vix = re.search(r"'vix': ([\d.]+)", line)
            if m_spx and m_vix:
                snapshots.append({"spx": float(m_spx.group(1)), "vix": float(m_vix.group(1))})

    health = "DEGRADED" if n8n_failures > 5 else ("UNSTABLE" if n8n_failures > 0 else "HEALTHY")

    return {
        "errors":           errors[-5:],  # last 5 errors only
        "snapshots":        snapshots[-5:],
        "n8n_failures":     n8n_failures,
        "hot_updates":      hot_updates,
        "confidence_trend": confidence_scores,
        "avg_confidence":   round(sum(confidence_scores)/len(confidence_scores), 1) if confidence_scores else None,
        "health":           health,
    }


# ══════════════════════════════════════════════════════════════════
# 3. TRADE RATIONALE REPORT (Event-Triggered)
# ══════════════════════════════════════════════════════════════════

def generate_trade_rationale(trade, snap):
    """
    Full Trade Rationale Report for a given position.
    Mirrors the analysis from our greek_decompose + trade_review work.
    Returns a structured dict + markdown block.
    """
    entry_date  = trade.get("open_date", "Unknown")
    expiry      = trade.get("expiration_date", "")
    short_put   = trade.get("short_put_strike", 0)
    short_call  = trade.get("short_call_strike", 0)
    long_put    = trade.get("long_put_strike", 0)
    long_call   = trade.get("long_call_strike", 0)
    credit      = trade.get("credit_received") or trade.get("open_price", 0)
    strategy    = trade.get("strategy", "IRON_CONDOR")

    today    = datetime.now().date()
    exp_date = datetime.strptime(expiry, "%Y-%m-%d").date() if expiry else today + timedelta(days=45)
    dte      = (exp_date - today).days

    spx_now  = snap["spx"]
    vix_now  = snap["vix"]
    iv_rank  = snap["iv_rank"]
    hv30     = snap["hv30"]
    iv_spread= snap["iv_hv_spread"]

    put_dist_pct  = round(((spx_now - short_put)  / spx_now) * 100, 2) if short_put else 0
    call_dist_pct = round(((short_call - spx_now) / spx_now) * 100, 2) if short_call else 0
    avg_move      = snap["avg_daily_move"]
    put_breach_days  = int((spx_now - short_put) / (avg_move / 100 * spx_now)) if short_put and avg_move else 999
    call_breach_days = int((short_call - spx_now) / (avg_move / 100 * spx_now)) if short_call and avg_move else 999

    # Score rubric
    score = 0
    pros, cons = [], []

    if iv_rank > 50:
        score += 2; pros.append(f"IV Rank {iv_rank:.0f}%: elevated — premium is above 50th percentile")
    elif iv_rank > 30:
        score += 1; pros.append(f"IV Rank {iv_rank:.0f}%: moderate — acceptable premium for 45-DTE")
    else:
        score -= 1; cons.append(f"IV Rank {iv_rank:.0f}%: below median — premium is thin for the risk taken")

    if iv_spread > 5:
        score += 2; pros.append(f"IV-HV spread +{iv_spread:.1f}pp: market significantly over-pricing vol vs realized — strong seller edge")
    elif iv_spread > 2:
        score += 1; pros.append(f"IV-HV spread +{iv_spread:.1f}pp: slight seller edge")
    elif iv_spread < 0:
        score -= 2; cons.append(f"IV-HV spread {iv_spread:.1f}pp: IV BELOW realized — sellers have no structural edge")

    if put_dist_pct > 6:
        score += 2; pros.append(f"Short put {put_dist_pct:.1f}% OTM ({int(spx_now-short_put)} pts) — requires {put_breach_days} consecutive avg-size down days to breach")
    elif put_dist_pct > 4:
        score += 1; pros.append(f"Short put {put_dist_pct:.1f}% OTM — adequate buffer")
    else:
        score -= 1; cons.append(f"Short put only {put_dist_pct:.1f}% OTM — thin margin given current vol")

    if call_dist_pct > 5:
        score += 1; pros.append(f"Short call {call_dist_pct:.1f}% OTM ({int(short_call-spx_now)} pts) — upside well protected")
    else:
        score -= 1; cons.append(f"Short call {call_dist_pct:.1f}% OTM — call side needs monitoring on rallies")

    if snap["vix_trend"] == "FALLING":
        score += 1; pros.append("VIX trending DOWN (3-day) — IV compression benefits short-vol positions")
    elif snap["vix_trend"] == "RISING":
        score -= 1; cons.append("VIX trending UP (3-day) — short-term headwind; mark-to-market may go negative before recovering")

    if 35 <= dte <= 55:
        score += 1; pros.append(f"{dte} DTE: optimal theta/gamma ratio for Core Income strategy")
    elif dte < 21:
        cons.append(f"Only {dte} DTE: consider closing — gamma exposure rising")

    rating = (
        "STRONG ENTRY" if score >= 6
        else "GOOD ENTRY" if score >= 4
        else "MARGINAL"  if score >= 2
        else "POOR TIMING"
    )

    # Upcoming catalysts within expiry window
    upcoming = []
    for ev_date, ev_name, impact, note in CATALYST_CALENDAR:
        ev_d = datetime.strptime(ev_date, "%Y-%m-%d").date()
        days_away = (ev_d - today).days
        if 0 <= days_away <= dte:
            upcoming.append({"date": ev_date, "event": ev_name, "impact": impact, "note": note, "days_away": days_away})

    return {
        "trade_id":        trade.get("id", "unknown"),
        "entry_date":      entry_date,
        "expiry":          expiry,
        "dte_at_report":   dte,
        "credit_opened":   credit,
        "put_dist_pct":    put_dist_pct,
        "call_dist_pct":   call_dist_pct,
        "put_breach_days": put_breach_days,
        "call_breach_days":call_breach_days,
        "rating":          rating,
        "score":           score,
        "pros":            pros,
        "cons":            cons,
        "upcoming_events": upcoming,
        "snapshot_at_report": snap,
    }


# ══════════════════════════════════════════════════════════════════
# 4. THESIS DRIFT DETECTOR (Daily Recalibration)
# ══════════════════════════════════════════════════════════════════

def detect_thesis_drift(original_thesis, current_snap):
    """
    Compares original entry conditions against today's market.
    Returns a drift score and list of flagged changes.
    """
    orig_snap = original_thesis.get("snapshot_at_report", {})
    flags     = []
    drift_score = 0  # positive = thesis stronger, negative = thesis weaker

    # VIX direction drift
    vix_delta = current_snap["vix"] - orig_snap.get("vix", current_snap["vix"])
    if vix_delta > 3:
        flags.append(f"DRIFT: VIX rose +{vix_delta:.1f} since entry — IV expansion hurts mark-to-market")
        drift_score -= 2
    elif vix_delta < -3:
        flags.append(f"TAILWIND: VIX fell {vix_delta:.1f} since entry — IV compression accelerating P&L")
        drift_score += 2

    # SPX directional drift
    spx_delta_pct = ((current_snap["spx"] - orig_snap.get("spx", current_snap["spx"])) / orig_snap.get("spx", current_snap["spx"])) * 100
    if spx_delta_pct < -2:
        flags.append(f"DRIFT: SPX down {spx_delta_pct:.1f}% since entry — put side under increasing pressure")
        drift_score -= 2
    elif spx_delta_pct > 3:
        flags.append(f"DRIFT: SPX up {spx_delta_pct:.1f}% since entry — call side approaching, monitor short call")
        drift_score -= 1
    elif abs(spx_delta_pct) < 1:
        flags.append(f"STABLE: SPX has moved only {spx_delta_pct:+.1f}% — original thesis intact")
        drift_score += 1

    # IV Rank drift
    iv_rank_delta = current_snap["iv_rank"] - orig_snap.get("iv_rank", current_snap["iv_rank"])
    if iv_rank_delta > 15:
        flags.append(f"DRIFT: IV Rank expanded +{iv_rank_delta:.0f}pp — position losing value but theta will recover")
        drift_score -= 1
    elif iv_rank_delta < -15:
        flags.append(f"TAILWIND: IV Rank compressed {iv_rank_delta:.0f}pp — vega gains are accelerating P&L")
        drift_score += 1

    # IV-HV spread health
    if current_snap["iv_hv_spread"] < 2:
        flags.append("WARNING: IV-HV spread narrowed to near zero — seller's structural edge is eroding")
        drift_score -= 1
    elif current_snap["iv_hv_spread"] > 5:
        flags.append(f"EDGE: IV-HV spread remains +{current_snap['iv_hv_spread']:.1f}pp — seller advantage intact")
        drift_score += 1

    status = (
        "THESIS INTACT"     if drift_score >= 1
        else "THESIS NEUTRAL" if drift_score == 0
        else "THESIS DRIFTING" if drift_score >= -2
        else "THESIS BROKEN"
    )

    return {
        "drift_score":  drift_score,
        "status":       status,
        "flags":        flags,
        "spx_delta_pct": round(spx_delta_pct, 2),
        "vix_delta":    round(vix_delta, 2),
    }


# ══════════════════════════════════════════════════════════════════
# 5. CHALLENGER SCANNER + PIVOT ALERT
# ══════════════════════════════════════════════════════════════════

def scan_for_challenger(snap, active_trade, target_dte=45):
    """
    Identifies if a fresh Iron Condor at current optimal strikes
    offers meaningfully better risk-adjusted credit than the active position.
    Returns challenger details + pivot recommendation if warranted.
    """
    spx   = snap["spx"]
    vix   = snap["vix"]

    # Optimal delta-based strike selection (0.10 delta ~ 10% OTM for 45 DTE)
    delta_distance = 0.10 if vix >= 15 else 0.08
    put_dist  = spx * delta_distance
    call_dist = spx * delta_distance * 1.05  # Calls slightly wider (skew-adjusted)

    chal_short_put  = round((spx - put_dist)  / 5) * 5
    chal_long_put   = chal_short_put - 25
    chal_short_call = round((spx + call_dist) / 5) * 5
    chal_long_call  = chal_short_call + 25

    # Fetch expiry
    try:
        spx_ticker  = yf.Ticker("^SPX")
        expirations = spx_ticker.options
        today = datetime.now().date()
        best_exp = None
        min_diff = float("inf")
        for exp_str in expirations:
            exp_d = datetime.strptime(exp_str, "%Y-%m-%d").date()
            diff  = abs((exp_d - today).days - target_dte)
            if diff < min_diff and (exp_d - today).days > 0:
                min_diff = diff
                best_exp = exp_str
    except Exception:
        best_exp = None

    if not best_exp:
        return {"available": False, "reason": "Could not fetch option expirations"}

    legs = [
        ("Long Put",   chal_long_put,   "put",  -1),
        ("Short Put",  chal_short_put,  "put",  +1),
        ("Short Call", chal_short_call, "call", +1),
        ("Long Call",  chal_long_call,  "call", -1),
    ]

    leg_data = fetch_leg_data(best_exp, legs)
    if not leg_data:
        return {"available": False, "reason": "Option chain unavailable"}

    net_credit = sum(r["sign"] * r["mark"] for r in leg_data)

    # Compare against active position's original credit
    active_credit  = active_trade.get("credit_received") or active_trade.get("open_price", 0)
    active_put_pct = ((spx - active_trade.get("short_put_strike", 0)) / spx) * 100

    challenger_put_pct  = ((spx - chal_short_put)  / spx) * 100
    challenger_call_pct = ((chal_short_call - spx)  / spx) * 100

    # Pivot is warranted if challenger has meaningfully better margin OR credit
    pivot_warranted = (challenger_put_pct > active_put_pct * 1.05) and (net_credit >= active_credit * 0.7)

    return {
        "available":          True,
        "expiry":             best_exp,
        "strikes":            {"short_put": chal_short_put, "long_put": chal_long_put, "short_call": chal_short_call, "long_call": chal_long_call},
        "net_credit":         round(net_credit, 2),
        "put_margin_pct":     round(challenger_put_pct, 2),
        "call_margin_pct":    round(challenger_call_pct, 2),
        "active_credit":      active_credit,
        "active_put_pct":     round(active_put_pct, 2),
        "pivot_warranted":    pivot_warranted,
        "pivot_rationale":    (
            "PIVOT RECOMMENDED: Challenger offers significantly better margin at comparable credit."
            if pivot_warranted
            else "HOLD CURRENT: Existing position is competitive or superior. No pivot justified."
        ),
        "leg_detail":         leg_data,
    }


# ══════════════════════════════════════════════════════════════════
# 6. STATE MANAGER (Persistence + Versioning)
# ══════════════════════════════════════════════════════════════════

def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"version": "2.0", "positions": {}, "last_run": None}


def save_state(state):
    state["last_run"] = datetime.now().isoformat()
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)


def load_portfolio():
    try:
        with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "positions" in data:
            return [p for p in data["positions"] if p.get("status") == "OPEN"]
        return []
    except Exception as e:
        logger.error(f"Portfolio load failed: {e}")
        return []


# ══════════════════════════════════════════════════════════════════
# 5b. CLOSED TRADE JOURNAL (Priority 5)
# ══════════════════════════════════════════════════════════════════

def track_closed_positions(state: dict, current_open_ids: set) -> int:
    """
    Compares the previously tracked positions in ledger state against
    the currently OPEN positions in portfolio.json.

    Any position that was previously active but is now gone (closed)
    gets archived to Alpha_Data/trade_journal.json.

    Returns count of newly archived trades.
    """
    journal = []
    if os.path.exists(JOURNAL_PATH):
        try:
            with open(JOURNAL_PATH, "r", encoding="utf-8") as f:
                journal = json.load(f)
        except Exception:
            pass

    known_ids  = set(state["positions"].keys())
    closed_ids = known_ids - current_open_ids
    archived   = 0

    for tid in closed_ids:
        # Skip if already in journal
        if any(j["trade_id"] == tid for j in journal):
            del state["positions"][tid]
            continue

        pstate = state["positions"][tid]
        thesis = pstate.get("original_thesis", {})
        credit = thesis.get("credit_opened", 0)
        final_mark = pstate.get("current_mark", 0)
        realized_pnl = round(credit - final_mark, 2)
        realized_pnl_pct = round((realized_pnl / credit * 100) if credit else 0, 1)

        # Compute max drawdown from daily update history
        updates = pstate.get("daily_updates", [])
        mark_values = [u.get("current_mark", credit) for u in updates if u.get("current_mark")]
        max_mark    = max(mark_values) if mark_values else credit
        max_drawdown_pct = round(((max_mark - credit) / credit * 100) if credit else 0, 1)

        entry_date = thesis.get("entry_date", "")
        try:
            entry_dt   = datetime.strptime(entry_date, "%Y-%m-%d")
            days_held  = (datetime.now() - entry_dt).days
        except Exception:
            days_held = None

        # Drift summary
        drift_scores = [u.get("drift_score", 0) for u in updates]
        worst_drift  = min(drift_scores) if drift_scores else 0

        entry = {
            "trade_id":            tid,
            "strategy":            thesis.get("strategy", "IRON_CONDOR"),
            "entry_date":          entry_date,
            "close_date":          datetime.now().strftime("%Y-%m-%d"),
            "expiry":              thesis.get("expiry", ""),
            "credit_received":     credit,
            "close_mark":          final_mark,
            "realized_pnl":        realized_pnl,
            "realized_pnl_pct":    realized_pnl_pct,
            "days_held":           days_held,
            "entry_rating":        thesis.get("rating", "?"),
            "entry_score":         thesis.get("score", 0),
            "worst_drift_score":   worst_drift,
            "max_drawdown_pct":    max_drawdown_pct,
            "closes_at":           datetime.now().isoformat(),
            "strikes": {
                "long_put":        pstate.get("original_thesis", {}).get("put_dist_pct", 0),
                "short_put":       thesis.get("put_dist_pct", 0),
                "short_call":      thesis.get("call_dist_pct", 0),
            },
        }

        journal.append(entry)
        logger.info(
            f"[Journal] Archived: {tid} | P&L: ${realized_pnl:+.2f} "
            f"({realized_pnl_pct:+.1f}%) | {days_held}d held | Rating: {thesis.get('rating','?')}"
        )

        # Remove from active state
        del state["positions"][tid]
        archived += 1

    if archived > 0 or not os.path.exists(JOURNAL_PATH):
        with open(JOURNAL_PATH, "w", encoding="utf-8") as f:
            json.dump(journal, f, indent=2, default=str)

    return archived


# ══════════════════════════════════════════════════════════════════
# 7. LEDGER MARKDOWN WRITER
# ══════════════════════════════════════════════════════════════════

def _star(impact):
    return "[HIGH]" if impact == "HIGH" else "[MED]"

def _drift_icon(status):
    return {"THESIS INTACT": "OK", "THESIS NEUTRAL": "~~", "THESIS DRIFTING": "!!", "THESIS BROKEN": "XX"}.get(status, "??")

def write_ledger_md(state, snap, log_digest, positions):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    open_count   = len(positions)
    portfolio_health = "GREEN" if all(
        state["positions"].get(p.get("id", ""), {}).get("drift", {}).get("drift_score", 0) >= -1
        for p in positions
    ) else "YELLOW"

    lines = [
        "# ALPHA V2 GENESIS - STRATEGY LEDGER",
        f"**Generated:** {now_str}  |  **Engine:** Lead Quant Architect v2.0",
        "",
        "---",
        "",
        "## EXECUTIVE SUMMARY",
        "",
        f"| Metric | Value |",
        f"| :--- | :--- |",
        f"| **Portfolio Health** | {portfolio_health} |",
        f"| **Open Positions** | {open_count} |",
        f"| **SPX Spot** | {snap['spx']:,.2f} |",
        f"| **VIX** | {snap['vix']:.2f} ({snap['vix_trend']}) |",
        f"| **IV Rank (52W)** | {snap['iv_rank']:.1f}% |",
        f"| **IV-HV Spread** | +{snap['iv_hv_spread']:.1f}pp (Seller Edge) |",
        f"| **N8N System Health** | {log_digest['health']} ({log_digest['n8n_failures']} failures in log) |",
        f"| **Last Hot Updates** | {log_digest['hot_updates']} n8n pushes detected |",
        "",
        "---",
        "",
        "## THE ELABORATED LEDGER (Log Intelligence)",
        "",
        f"> System parsed `alpha.log`. Health: **{log_digest['health']}**",
        "",
    ]

    if log_digest["n8n_failures"] > 0:
        lines += [
            f"### System Errors Detected ({log_digest['n8n_failures']} in recent log)",
            "",
            "| # | Error |",
            "| :--- | :--- |",
        ]
        for i, e in enumerate(log_digest["errors"], 1):
            short = e[:120].replace("|", "/")
            lines.append(f"| {i} | `{short}` |")
        lines += [
            "",
            "> **Action Required**: N8N Genesis intermittent failures detected. ",
            "> Review webhook URL in `.env` and verify n8n workflow is **Active**.",
            "",
        ]

    if log_digest.get("avg_confidence"):
        lines += [
            f"**Alpha Confidence Score (Log Avg):** {log_digest['avg_confidence']:.1f}/100",
            "",
        ]

    lines += [
        "---",
        "",
        "## ACTIVE TRADE REPORTS",
        "",
    ]

    for pos in positions:
        tid    = pos.get("id", "unknown")
        pstate = state["positions"].get(tid, {})
        thesis = pstate.get("original_thesis", {})
        drift  = pstate.get("drift", {})

        credit = pos.get("credit_received") or pos.get("open_price", 0)
        expiry = pos.get("expiration_date", "")
        today  = datetime.now().date()
        exp_d  = datetime.strptime(expiry, "%Y-%m-%d").date() if expiry else today + timedelta(days=45)
        dte    = (exp_d - today).days
        pnl_val = credit - (pstate.get("current_mark", credit))

        lines += [
            f"### {tid}",
            "",
            f"| | |",
            f"| :--- | :--- |",
            f"| **Strategy** | {pos.get('strategy','IRON_CONDOR')} |",
            f"| **Opened** | {pos.get('open_date','?')} |",
            f"| **Expires** | {expiry} ({dte} DTE remaining) |",
            f"| **Credit Received** | ${credit:.2f} |",
            f"| **Current Mark** | ${pstate.get('current_mark', 'N/A')} |",
            f"| **P&L So Far** | +${pnl_val:.2f} ({round(pnl_val/credit*100,1)}% of max profit) |" if isinstance(pnl_val, float) and credit else f"| **P&L So Far** | — |",
            f"| **50% Profit Target** | ${round(credit/2,2):.2f} mark |",
            f"| **21-DTE Exit Date** | {(datetime.strptime(expiry,'%Y-%m-%d') - timedelta(days=21)).strftime('%Y-%m-%d') if expiry else '?'} |",
            f"| **Strikes** | {pos.get('long_put_strike',0)}/{pos.get('short_put_strike',0)} Put · {pos.get('short_call_strike',0)}/{pos.get('long_call_strike',0)} Call |",
            "",
        ]

        # ── Real Greeks Table ─────────────────────────────────────
        pg = pstate.get("position_greeks")
        if pg:
            interp = pg.get("interpretation", {})
            lines += [
                "**Position Greeks (Black-Scholes, Live)**",
                "",
                "| Greek | Value | Meaning |",
                "| :--- | :---: | :--- |",
                f"| **Theta** (θ) | `+${pg['net_theta_per_day']:.2f}/day` | {interp.get('theta','')} |",
                f"| **Vega** (ν) | `${pg['net_vega_per_pp']:.2f}/pp` | {interp.get('vega','')} |",
                f"| **Delta** (δ) | `{pg['net_delta_per_pt']:+.2f}/pt` | {interp.get('delta','')} |",
                f"| **Gamma** (γ) | `{pg['net_gamma']:.7f}` | Convexity risk per $1 SPX move |",
                "",
            ]

        if thesis:
            rating_icon = {"STRONG ENTRY": "A+", "GOOD ENTRY": "A", "MARGINAL": "C", "POOR TIMING": "D"}.get(thesis.get("rating", ""), "?")
            lines += [
                f"**Entry Rating at Open: [{rating_icon}] {thesis.get('rating','?')}** (Score: {thesis.get('score',0)}/9)",
                "",
                "**Reasons FOR the trade:**",
                "",
            ]
            for p in thesis.get("pros", []):
                lines.append(f"- {p}")
            lines += ["", "**Risks at entry:**", ""]
            for c in thesis.get("cons", []):
                lines.append(f"- {c}")
            lines.append("")

        if drift:
            icon = _drift_icon(drift.get("status", ""))
            lines += [
                f"**Daily Thesis Update: [{icon}] {drift.get('status','?')}** (Drift Score: {drift.get('drift_score',0):+d})",
                "",
            ]
            for flag in drift.get("flags", []):
                lines.append(f"- {flag}")
            lines.append("")

        chall = pstate.get("challenger", {})
        if chall and chall.get("available"):
            pivot = chall.get("pivot_warranted", False)
            pivot_label = "PIVOT RECOMMENDED" if pivot else "HOLD CURRENT"
            lines += [
                f"**Challenger Scan: {pivot_label}**",
                "",
                f"| | Current | Challenger |",
                f"| :--- | :---: | :---: |",
                f"| Short Put | {pos.get('short_put_strike',0)} | {chall['strikes']['short_put']} |",
                f"| Short Call | {pos.get('short_call_strike',0)} | {chall['strikes']['short_call']} |",
                f"| Credit | ${credit:.2f} | ${chall['net_credit']:.2f} |",
                f"| Put Margin | {thesis.get('put_dist_pct','?')}% | {chall['put_margin_pct']:.2f}% |",
                f"| Expiry | {expiry} | {chall['expiry']} |",
                "",
                f"> {chall['pivot_rationale']}",
                "",
            ]

        upcoming = thesis.get("upcoming_events", [])
        if upcoming:
            lines += ["**Upcoming Catalysts within Trade Window:**", ""]
            for ev in upcoming:
                lines.append(f"- {_star(ev['impact'])} **{ev['event']}** ({ev['date']}, in {ev['days_away']}d) — {ev['note']}")
            lines.append("")

        lines += ["---", ""]

    lines += [
        "## ACTIVE RECOMMENDATIONS",
        "",
    ]

    # Pivot alerts
    pivot_alerts = [
        p.get("id") for p in positions
        if state["positions"].get(p.get("id",""), {}).get("challenger", {}).get("pivot_warranted", False)
    ]
    if pivot_alerts:
        lines += [f"- **PIVOT ALERT** on position(s): {', '.join(pivot_alerts)} — See Challenger Scan section above."]

    # Thesis drift alerts
    broken = [
        p.get("id") for p in positions
        if state["positions"].get(p.get("id",""), {}).get("drift", {}).get("status") == "THESIS BROKEN"
    ]
    if broken:
        lines += [f"- **THESIS BROKEN** on: {', '.join(broken)} — Re-evaluate position immediately."]

    # Generic hold
    if not pivot_alerts and not broken:
        lines += ["- No pivot alerts. All active positions are within thesis tolerance.", "- Continue monitoring upcoming macro events."]

    lines += [
        "",
        "---",
        "",
        "## IMPLEMENTATION NOTES",
        "",
        "- **N8N Daily Cron**: Set a Schedule Trigger in n8n → runs daily at 09:15 EST (Mon-Fri)",
        "  → Calls `POST http://<ngrok_url>/api/ledger/refresh` to trigger this engine remotely.",
        "- **Log Brittleness**: N8N Genesis failures require the `alpha-research-v3` workflow to be **Active** in n8n Cloud.",
        "  Run `python -m scripts.n8n_audit` to verify all webhooks are live.",
        "- **Ledger State**: Persisted at `Alpha_Data/ledger_state.json` — survives server restarts.",
        "- **Auto-trigger**: `infrastructure_supervisor.py` now watches `portfolio.json` for new trades",
        "  and triggers this ledger engine when a new OPEN position is detected.",
        "",
        "_Ledger engine: Alpha V2 Genesis Quant Architect v2.0 | Antigravity AI_",
    ]

    with open(LEDGER_MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Ledger written to {LEDGER_MD_PATH}")


# ══════════════════════════════════════════════════════════════════
# 8. MAIN ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════

def run_ledger(force_full=False):
    logger.info("=== Strategy Ledger Run Started ===")

    state     = load_state()
    positions = load_portfolio()
    log_dig   = parse_alpha_log(max_lines=80)

    # Archive any positions that have closed since last run (Priority 5)
    current_open_ids = {p.get("id") for p in positions}
    archived = track_closed_positions(state, current_open_ids)
    if archived:
        logger.info(f"Archived {archived} closed position(s) to trade journal.")

    if not positions:
        logger.info("No open positions found. Ledger will produce summary only.")

    try:
        snap = fetch_market_snapshot()
        logger.info(f"Market: SPX={snap['spx']} VIX={snap['vix']} IVR={snap['iv_rank']}% HV30={snap['hv30']}%")
    except Exception as e:
        logger.error(f"Market snapshot failed: {e}")
        snap = {}

    for pos in positions:
        tid = pos.get("id", "unknown")
        pstate = state["positions"].setdefault(tid, {})

        # 1. First-time: generate original thesis (or if forced)
        if "original_thesis" not in pstate or force_full:
            logger.info(f"[{tid}] Generating original trade rationale...")
            thesis = generate_trade_rationale(pos, snap)
            pstate["original_thesis"]       = thesis
            pstate["entry_snapshot"]        = snap
            pstate["first_seen"]            = datetime.now().isoformat()
            logger.info(f"[{tid}] Entry Rating: {thesis['rating']} (Score {thesis['score']})")

        # 2. Daily drift detection
        logger.info(f"[{tid}] Running thesis drift analysis...")
        drift = detect_thesis_drift(pstate["original_thesis"], snap)
        pstate["drift"] = drift
        pstate["drift"]["updated_at"] = datetime.now().isoformat()
        logger.info(f"[{tid}] Thesis Status: {drift['status']} (Drift: {drift['drift_score']:+d})")

        # Priority 3 — Alert: Thesis Broken
        if drift["status"] == "THESIS BROKEN":
            alert_thesis_broken(tid, drift.get("flags", []))

        # 3. Fetch current mark + REAL GREEKS
        try:
            expiry = pos.get("expiration_date", "")
            legs = [
                ("Long Put",   pos.get("long_put_strike",0),   "put",  -1),
                ("Short Put",  pos.get("short_put_strike",0),  "put",  +1),
                ("Short Call", pos.get("short_call_strike",0), "call", +1),
                ("Long Call",  pos.get("long_call_strike",0),  "call", -1),
            ]
            rfr      = _fetch_risk_free_rate()
            leg_data = fetch_leg_data(expiry, legs, spot=snap.get("spx"), r=rfr)
            if leg_data:
                current_mark = round(sum(r["sign"] * r["mark"] for r in leg_data), 2)
                pstate["current_mark"] = current_mark
                logger.info(f"[{tid}] Current mark: ${current_mark:.2f}")

                # ── Real Position Greeks ─────────────────────────────
                pos_greeks = compute_position_greeks(leg_data)
                pstate["position_greeks"] = pos_greeks
                logger.info(
                    f"[{tid}] Greeks: θ={pos_greeks['net_theta_per_day']:+.2f}$/day  "
                    f"v={pos_greeks['net_vega_per_pp']:+.2f}$/pp  "
                    f"δ={pos_greeks['net_delta_per_pt']:+.2f}$/pt"
                )

                # Priority 3 — Alert: 50% profit target hit
                sent = pstate.setdefault("alerts_sent", {})
                credit_at_open = pos.get("credit_received") or pos.get("open_price", 0)
                pnl_pct = ((credit_at_open - current_mark) / credit_at_open * 100) if credit_at_open else 0
                if pnl_pct >= 50 and not sent.get("profit_50"):
                    alert_profit_target(tid, pnl_pct, current_mark, credit_at_open)
                    sent["profit_50"] = True

                # Priority 3 — Alert: 21-DTE exit window
                expiry_d = datetime.strptime(expiry, "%Y-%m-%d").date() if expiry else None
                dte_now  = (expiry_d - datetime.now().date()).days if expiry_d else 999
                if dte_now <= 21 and not sent.get("dte_21"):
                    alert_dte_exit_window(tid, dte_now)
                    sent["dte_21"] = True
        except Exception as e:
            logger.warning(f"[{tid}] Mark/Greeks fetch failed: {e}")

        # 4. Challenger scan
        logger.info(f"[{tid}] Scanning for challenger opportunities...")
        try:
            challenger = scan_for_challenger(snap, pos)
            pstate["challenger"] = challenger
            if challenger.get("pivot_warranted"):
                logger.warning(f"[{tid}] PIVOT ALERT: Challenger at {challenger['strikes']['short_put']}/{challenger['strikes']['short_call']} offers better margin!")
                # Priority 3 — Alert: Pivot recommended
                sent = pstate.setdefault("alerts_sent", {})
                if not sent.get("pivot"):
                    alert_pivot_recommended(tid, challenger)
                    sent["pivot"] = True
            else:
                logger.info(f"[{tid}] {challenger.get('pivot_rationale','No pivot needed')}")
        except Exception as e:
            logger.warning(f"[{tid}] Challenger scan failed: {e}")
            pstate["challenger"] = {"available": False, "reason": str(e)}

        # 5. Add to daily update history
        daily_log = pstate.setdefault("daily_updates", [])
        daily_log.append({
            "date":         datetime.now().strftime("%Y-%m-%d %H:%M"),
            "spx":          snap.get("spx"),
            "vix":          snap.get("vix"),
            "drift_status": drift["status"],
            "drift_score":  drift["drift_score"],
            "current_mark": pstate.get("current_mark"),
        })
        # Keep only last 45 daily entries
        pstate["daily_updates"] = daily_log[-45:]

    save_state(state)
    logger.info("Ledger state saved.")

    write_ledger_md(state, snap, log_dig, positions)
    logger.info("=== Strategy Ledger Run Complete ===")

    return {
        "status":         "ok",
        "positions_processed": len(positions),
        "portfolio_health": "GREEN" if not any(
            state["positions"].get(p.get("id",""), {}).get("drift", {}).get("drift_score", 0) < -2
            for p in positions
        ) else "YELLOW",
        "ledger_path":    LEDGER_MD_PATH,
        "state_path":     STATE_PATH,
        "log_health":     log_dig["health"],
        "n8n_failures":   log_dig["n8n_failures"],
        "timestamp":      datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Alpha V2 Genesis — Strategy Ledger Engine")
    parser.add_argument("--force",  action="store_true", help="Force re-generate all rationale reports")
    args = parser.parse_args()
    result = run_ledger(force_full=args.force)
    print(json.dumps(result, indent=2))
