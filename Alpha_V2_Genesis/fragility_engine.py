"""
╔══════════════════════════════════════════════════════════════╗
║  ALPHA V2 GENESIS — FRAGILITY ENGINE                        ║
║  Systemic Risk & Regime-Shift Detection Module              ║
║                                                              ║
║  Modules:                                                    ║
║  1. Volatility Term Structure & Skew Engine                  ║
║  2. Intermarket Correlation & Regime Filter                  ║
║  3. Credit Stress & Liquidity Module                         ║
║  4. Synthesis & Risk Overlay (Fragility Index 0–100)         ║
╚══════════════════════════════════════════════════════════════╝
"""
import time
import logging
import numpy as np
import yfinance as yf
from datetime import datetime

logger = logging.getLogger("FragilityEngine")

# ── TTL Cache ────────────────────────────────────────────────────
_cache = {"data": None, "ts": 0}
CACHE_TTL = 60  # seconds


def _fetch_history(ticker, period="3mo"):
    """Safe yfinance history fetch with fallback."""
    try:
        t = yf.Ticker(ticker)
        h = t.history(period=period)
        if h.empty:
            return None
        return h
    except Exception as e:
        logger.warning(f"[Fragility] Failed to fetch {ticker}: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
# 1. VOLATILITY TERM STRUCTURE & SKEW ENGINE
# ══════════════════════════════════════════════════════════════════

def _compute_volatility_structure():
    """
    VIX term structure (VIX vs VIX3M) and CBOE Skew.
    Backwardation = front-month vol > back-month = High Fragility.
    """
    result = {
        "vix": None,
        "vix3m": None,
        "vix_ratio": None,
        "term_structure": "UNKNOWN",
        "skew": None,
        "skew_alert": None,
        "alerts": [],
        "score": 50,  # neutral starting point (0-100 sub-score)
    }

    # VIX
    vix_hist = _fetch_history("^VIX", "3mo")
    if vix_hist is not None and len(vix_hist) > 0:
        result["vix"] = round(float(vix_hist["Close"].iloc[-1]), 2)

        # VIX percentile (52-week context)
        vix_1y = _fetch_history("^VIX", "1y")
        if vix_1y is not None and len(vix_1y) > 20:
            vix_now = result["vix"]
            pctile = float((vix_1y["Close"] < vix_now).mean() * 100)
            result["vix_percentile"] = round(pctile, 1)

    # VIX3M (3-month VIX)
    vix3m_hist = _fetch_history("^VIX3M", "3mo")
    if vix3m_hist is not None and len(vix3m_hist) > 0:
        result["vix3m"] = round(float(vix3m_hist["Close"].iloc[-1]), 2)

    # Term Structure Ratio
    if result["vix"] and result["vix3m"] and result["vix3m"] > 0:
        ratio = result["vix"] / result["vix3m"]
        result["vix_ratio"] = round(ratio, 3)

        if ratio > 1.0:
            result["term_structure"] = "BACKWARDATION"
            result["alerts"].append("⚠️ Term structure in BACKWARDATION — front-month vol exceeds back-month")
            # Score: higher ratio = more fragile (score 60-100)
            result["score"] = min(100, int(50 + (ratio - 1.0) * 200))
        elif ratio > 0.95:
            result["term_structure"] = "FLAT"
            result["score"] = 50
        else:
            result["term_structure"] = "CONTANGO"
            # Score: deeper contango = more stable (score 10-50)
            result["score"] = max(10, int(50 - (1.0 - ratio) * 150))
    elif result["vix"]:
        # Fallback: use VIX percentile as proxy
        pctile = result.get("vix_percentile", 50)
        result["score"] = min(100, max(10, int(pctile)))
        if pctile > 70:
            result["term_structure"] = "ELEVATED"
            result["alerts"].append(f"⚠️ VIX at {pctile:.0f}th percentile — elevated regime")
        elif pctile < 30:
            result["term_structure"] = "COMPLACENT"
        else:
            result["term_structure"] = "NORMAL"

    # CBOE Skew Index
    skew_hist = _fetch_history("^SKEW", "3mo")
    if skew_hist is not None and len(skew_hist) > 0:
        skew_val = round(float(skew_hist["Close"].iloc[-1]), 1)
        result["skew"] = skew_val

        if skew_val > 145:
            result["skew_alert"] = "🔴 TAIL RISK HEDGING ACCUMULATION"
            result["alerts"].append(f"Skew at {skew_val} — heavy tail-risk hedging detected")
            result["score"] = min(100, result["score"] + 15)
        elif skew_val > 135:
            result["skew_alert"] = "🟡 ELEVATED SKEW"
            result["score"] = min(100, result["score"] + 8)
        elif skew_val < 120:
            result["skew_alert"] = "🟢 LOW SKEW"
            result["score"] = max(10, result["score"] - 5)

    return result


# ══════════════════════════════════════════════════════════════════
# 2. INTERMARKET CORRELATION & REGIME FILTER
# ══════════════════════════════════════════════════════════════════

CORRELATION_TICKERS = ["SPY", "TLT", "GLD", "USO", "UUP"]

def _compute_correlations():
    """
    20-day and 60-day rolling correlations between SPY, TLT, GLD, USO, UUP.
    Detects correlation breaks (e.g. SPY/TLT flipping from negative to positive).
    """
    result = {
        "tickers": CORRELATION_TICKERS,
        "matrix_20d": None,
        "matrix_60d": None,
        "delta_matrix": None,
        "spy_tlt_corr_20d": None,
        "spy_tlt_corr_60d": None,
        "spy_tlt_flip": False,
        "alerts": [],
        "score": 30,  # default low-stress
    }

    # Fetch all histories
    closes = {}
    for ticker in CORRELATION_TICKERS:
        hist = _fetch_history(ticker, "6mo")
        if hist is not None and len(hist) > 60:
            closes[ticker] = hist["Close"]

    if len(closes) < 2:
        result["alerts"].append("Insufficient data for correlation analysis")
        return result

    # Build DataFrame
    import pandas as pd
    df = pd.DataFrame(closes).dropna()
    if len(df) < 60:
        result["alerts"].append("Not enough overlapping data for 60d correlations")
        return result

    returns = df.pct_change().dropna()

    # 20-day and 60-day correlation matrices
    corr_20d = returns.iloc[-20:].corr()
    corr_60d = returns.iloc[-60:].corr()
    delta = corr_20d - corr_60d

    # Convert to serializable nested dicts (rounded)
    def corr_to_dict(c):
        d = {}
        for t1 in c.index:
            d[t1] = {}
            for t2 in c.columns:
                d[t1][t2] = round(float(c.loc[t1, t2]), 3)
        return d

    result["matrix_20d"] = corr_to_dict(corr_20d)
    result["matrix_60d"] = corr_to_dict(corr_60d)
    result["delta_matrix"] = corr_to_dict(delta)

    # SPY/TLT analysis (the most important one)
    if "SPY" in corr_20d.index and "TLT" in corr_20d.index:
        spy_tlt_20 = float(corr_20d.loc["SPY", "TLT"])
        spy_tlt_60 = float(corr_60d.loc["SPY", "TLT"])
        result["spy_tlt_corr_20d"] = round(spy_tlt_20, 3)
        result["spy_tlt_corr_60d"] = round(spy_tlt_60, 3)

        # Correlation flip detection
        if spy_tlt_60 < -0.1 and spy_tlt_20 > 0.1:
            result["spy_tlt_flip"] = True
            result["alerts"].append(
                f"🔴 CORRELATION BREAK: SPY/TLT flipped from {spy_tlt_60:.2f} (60d) to {spy_tlt_20:.2f} (20d) — stocks and bonds falling together"
            )
            result["score"] = 80
        elif spy_tlt_20 > 0.3:
            result["alerts"].append(
                f"⚠️ SPY/TLT positive correlation ({spy_tlt_20:.2f}) — risk-off diversification failing"
            )
            result["score"] = 65
        elif spy_tlt_20 < -0.3:
            result["score"] = 20  # healthy negative correlation

    # Check for large delta-changes across the matrix
    large_shifts = []
    tickers = list(corr_20d.index)
    for i, t1 in enumerate(tickers):
        for t2 in tickers[i+1:]:
            if t1 in delta.index and t2 in delta.columns:
                d = float(delta.loc[t1, t2])
                if abs(d) > 0.3:
                    large_shifts.append(f"{t1}/{t2}: Δ{d:+.2f}")
    if large_shifts:
        result["alerts"].append(f"Correlation shifts detected: {', '.join(large_shifts)}")
        result["score"] = min(100, result["score"] + len(large_shifts) * 10)

    return result


# ══════════════════════════════════════════════════════════════════
# 3. CREDIT STRESS & LIQUIDITY MODULE
# ══════════════════════════════════════════════════════════════════

def _compute_credit_stress():
    """
    Tracks HYG/IEI ratio (credit spread proxy) and liquidity via volume analysis.
    HYG breakdown = credit stress = soft-stop for long equity.
    """
    result = {
        "hyg_iei_ratio": None,
        "hyg_iei_ratio_30d_avg": None,
        "hyg_iei_zscore": None,
        "hyg_iei_trend": "UNKNOWN",
        "liquidity_status": "NORMAL",
        "volume_zscore": None,
        "alerts": [],
        "score": 30,  # default low-stress
    }

    # HYG (High Yield Corporate Bonds)
    hyg = _fetch_history("HYG", "6mo")
    # IEI (3-7 Year Treasuries)
    iei = _fetch_history("IEI", "6mo")

    if hyg is not None and iei is not None and len(hyg) > 30 and len(iei) > 30:
        import pandas as pd
        # Align dates
        combined = pd.DataFrame({"HYG": hyg["Close"], "IEI": iei["Close"]}).dropna()
        if len(combined) > 30:
            ratio = combined["HYG"] / combined["IEI"]
            current = float(ratio.iloc[-1])
            avg_30d = float(ratio.iloc[-30:].mean())
            std_30d = float(ratio.iloc[-30:].std())

            result["hyg_iei_ratio"] = round(current, 4)
            result["hyg_iei_ratio_30d_avg"] = round(avg_30d, 4)

            if std_30d > 0:
                zscore = (current - avg_30d) / std_30d
                result["hyg_iei_zscore"] = round(zscore, 2)

                if zscore < -2.0:
                    result["hyg_iei_trend"] = "BREAKDOWN"
                    result["alerts"].append(
                        f"🔴 CREDIT BREAKDOWN: HYG/IEI ratio z-score {zscore:.2f} — credit spreads widening aggressively"
                    )
                    result["alerts"].append("⚠️ SOFT-STOP recommended for long equity positions")
                    result["score"] = 90
                elif zscore < -1.0:
                    result["hyg_iei_trend"] = "WEAKENING"
                    result["alerts"].append(
                        f"⚠️ Credit stress rising: HYG/IEI z-score {zscore:.2f}"
                    )
                    result["score"] = 65
                elif zscore > 1.0:
                    result["hyg_iei_trend"] = "STRENGTHENING"
                    result["score"] = 15
                else:
                    result["hyg_iei_trend"] = "STABLE"
                    result["score"] = 30

    # Liquidity proxy via SPY volume analysis
    spy = _fetch_history("SPY", "3mo")
    if spy is not None and len(spy) > 30:
        vol = spy["Volume"]
        avg_vol = float(vol.iloc[-30:].mean())
        std_vol = float(vol.iloc[-30:].std())
        current_vol = float(vol.iloc[-1])

        if std_vol > 0 and avg_vol > 0:
            vol_zscore = (current_vol - avg_vol) / std_vol
            result["volume_zscore"] = round(vol_zscore, 2)

            # Low volume = potential liquidity concern
            if vol_zscore < -2.0:
                result["liquidity_status"] = "THIN"
                result["alerts"].append(
                    f"⚠️ LIQUIDITY WARNING: SPY volume {vol_zscore:.1f}σ below mean — spreads likely widened"
                )
                result["score"] = min(100, result["score"] + 20)
            elif vol_zscore > 2.0:
                result["liquidity_status"] = "ELEVATED"
                result["alerts"].append("📊 Elevated volume — possible capitulation or institutional activity")
                result["score"] = min(100, result["score"] + 10)
            else:
                result["liquidity_status"] = "NORMAL"

    return result


# ══════════════════════════════════════════════════════════════════
# 4. SYNTHESIS & RISK OVERLAY (Fragility Index 0–100)
# ══════════════════════════════════════════════════════════════════

def _synthesize(vol, corr, credit):
    """
    Weighted Fragility Index:
      30% Volatility Structure
      30% Credit Spreads
      20% Correlation Stability
      20% Liquidity Depth

    Produces a 0-100 score, regime label, and actionable output.
    """
    # Extract sub-scores
    vol_score = vol.get("score", 50)
    credit_score = credit.get("score", 30)
    corr_score = corr.get("score", 30)

    # Liquidity is embedded in credit module
    liq_score = credit_score  # base from credit
    if credit.get("liquidity_status") == "THIN":
        liq_score = min(100, liq_score + 25)
    elif credit.get("liquidity_status") == "ELEVATED":
        liq_score = min(100, liq_score + 10)

    # Weighted composite
    fragility_index = int(
        0.30 * vol_score +
        0.30 * credit_score +
        0.20 * corr_score +
        0.20 * liq_score
    )
    fragility_index = max(0, min(100, fragility_index))

    # Regime classification
    if fragility_index >= 80:
        regime = "CRITICAL"
        regime_color = "#ef4444"
        max_leverage = 25
        stop_trading = True
    elif fragility_index >= 60:
        regime = "HIGH STRESS"
        regime_color = "#f97316"
        max_leverage = 50
        stop_trading = False
    elif fragility_index >= 40:
        regime = "ELEVATED"
        regime_color = "#eab308"
        max_leverage = 75
        stop_trading = False
    elif fragility_index >= 20:
        regime = "NORMAL"
        regime_color = "#22c55e"
        max_leverage = 100
        stop_trading = False
    else:
        regime = "LOW RISK"
        regime_color = "#10b981"
        max_leverage = 100
        stop_trading = False

    # Collect all alerts
    all_alerts = vol.get("alerts", []) + corr.get("alerts", []) + credit.get("alerts", [])

    # Build health report narrative
    report_parts = []
    report_parts.append(f"Fragility Index: {fragility_index}/100 ({regime})")

    if vol.get("term_structure") == "BACKWARDATION":
        report_parts.append("Volatility term structure is inverted — market pricing near-term risk above medium-term.")
    if corr.get("spy_tlt_flip"):
        report_parts.append("Cross-asset correlations have broken down — stocks and bonds are moving together, eliminating diversification benefits.")
    if credit.get("hyg_iei_trend") == "BREAKDOWN":
        report_parts.append("Credit spreads are widening aggressively — high yield bonds are under-performing treasuries.")
    if credit.get("liquidity_status") == "THIN":
        report_parts.append("Market liquidity is thin — execution slippage risk is elevated. Position sizing should be reduced by 50%.")

    if not report_parts[1:]:
        report_parts.append("All systemic indicators are within normal parameters. No structural fragility detected.")

    return {
        "fragility_index": fragility_index,
        "regime": regime,
        "regime_color": regime_color,
        "max_leverage_pct": max_leverage,
        "stop_trading": stop_trading,
        "health_report": " ".join(report_parts),
        "all_alerts": all_alerts,
        "component_scores": {
            "volatility": vol_score,
            "credit": credit_score,
            "correlation": corr_score,
            "liquidity": liq_score,
        },
        "weights": {
            "volatility": 0.30,
            "credit": 0.30,
            "correlation": 0.20,
            "liquidity": 0.20,
        },
    }


# ══════════════════════════════════════════════════════════════════
# PUBLIC API — compute_fragility()
# ══════════════════════════════════════════════════════════════════

def compute_fragility():
    """
    Main entry point. Returns the full fragility payload.
    Cached for 60 seconds to avoid hammering yfinance.
    """
    now = time.time()
    if _cache["data"] and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["data"]

    logger.info("[Fragility] Computing fragility indicators...")

    vol = _compute_volatility_structure()
    corr = _compute_correlations()
    credit = _compute_credit_stress()
    synthesis = _synthesize(vol, corr, credit)

    payload = {
        "timestamp": datetime.now().isoformat(),
        "fragility_index": synthesis["fragility_index"],
        "volatility": vol,
        "correlations": corr,
        "credit": credit,
        "synthesis": synthesis,
    }

    _cache["data"] = payload
    _cache["ts"] = now

    logger.info(
        f"[Fragility] Index: {synthesis['fragility_index']}/100 "
        f"| Regime: {synthesis['regime']} "
        f"| Stop: {synthesis['stop_trading']}"
    )

    return payload
