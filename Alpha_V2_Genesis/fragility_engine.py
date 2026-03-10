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

# ── Fetch Tracking (for confidence scoring) ──────────────────────
_fetch_tracker = {"total": 0, "success": 0, "failed": 0, "stale": 0}

def _reset_fetch_tracker():
    _fetch_tracker["total"] = 0
    _fetch_tracker["success"] = 0
    _fetch_tracker["failed"] = 0
    _fetch_tracker["stale"] = 0

def _fetch_history(ticker, period="3mo"):
    """Safe yfinance history fetch with fallback. Tracks success/failure."""
    _fetch_tracker["total"] += 1
    try:
        t = yf.Ticker(ticker)
        h = t.history(period=period)
        if h.empty:
            _fetch_tracker["failed"] += 1
            return None
        # Check data freshness — stale if last datapoint > 30 min old
        if len(h) > 0:
            last_ts = h.index[-1]
            try:
                import pandas as pd
                now = pd.Timestamp.now(tz=last_ts.tzinfo) if last_ts.tzinfo else pd.Timestamp.now()
                age_minutes = (now - last_ts).total_seconds() / 60
                if age_minutes > 30:
                    _fetch_tracker["stale"] += 1
            except Exception:
                pass
        _fetch_tracker["success"] += 1
        return h
    except Exception as e:
        _fetch_tracker["failed"] += 1
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
# 4a. NARRATIVE INTELLIGENCE — Glossary & Regime Synthesis
# ══════════════════════════════════════════════════════════════════

def _build_narrative_logic(vol, corr, credit, fragility_index, regime):
    """
    Builds the Narrative Intelligence layer:
    - glossary: plain-English definitions for each indicator with live values
    - regime_narrative: a 2-3 sentence market weather report with posture advice
    """

    # ── GLOSSARY ──────────────────────────────────────────────────
    vix_ratio = vol.get("vix_ratio")
    vix_ratio_status = vol.get("term_structure", "UNKNOWN")

    hyg_zscore = credit.get("hyg_iei_zscore")
    hyg_status = credit.get("hyg_iei_trend", "UNKNOWN")

    spy_tlt = corr.get("spy_tlt_corr_20d")
    spy_tlt_status = (
        "BROKEN" if corr.get("spy_tlt_flip") else
        "WARNING" if spy_tlt is not None and spy_tlt > 0.1 else
        "HEALTHY" if spy_tlt is not None and spy_tlt < -0.1 else
        "NEUTRAL"
    )

    skew_val = vol.get("skew")
    skew_status = (
        "CRITICAL" if skew_val is not None and skew_val > 145 else
        "ELEVATED" if skew_val is not None and skew_val > 135 else
        "LOW" if skew_val is not None and skew_val < 120 else
        "NORMAL"
    )

    liq_status = credit.get("liquidity_status", "NORMAL")

    glossary = [
        {
            "id": "vix_ratio",
            "name": "VIX / VIX3M Ratio",
            "icon": "📊",
            "value": vix_ratio if vix_ratio is not None else "N/A",
            "status": vix_ratio_status,
            "meaning": (
                "Measures fear urgency. When VIX exceeds VIX3M (ratio > 1), "
                "traders are paying more for near-term protection — markets "
                "expect turbulence NOW, not later. Contango (ratio < 1) is "
                "normal and signals complacency."
            ),
        },
        {
            "id": "hyg_iei",
            "name": "HYG / IEI Credit Ratio",
            "icon": "💳",
            "value": credit.get("hyg_iei_ratio", "N/A"),
            "status": hyg_status,
            "meaning": (
                "Compares junk bonds (HYG) to intermediate treasuries (IEI). "
                "A falling ratio means investors are dumping risky debt for "
                "safe havens — an early warning of credit stress before it "
                "hits equities."
            ),
        },
        {
            "id": "spy_tlt_corr",
            "name": "SPY / TLT Correlation",
            "icon": "🔗",
            "value": spy_tlt if spy_tlt is not None else "N/A",
            "status": spy_tlt_status,
            "meaning": (
                "Stocks and bonds normally move in opposite directions "
                "(negative correlation). When both fall together (positive "
                "correlation), portfolio diversification breaks down and "
                "total risk spikes — the 'nowhere to hide' scenario."
            ),
        },
        {
            "id": "cboe_skew",
            "name": "CBOE Skew Index",
            "icon": "📐",
            "value": skew_val if skew_val is not None else "N/A",
            "status": skew_status,
            "meaning": (
                "Measures how much institutional money is buying tail-risk "
                "hedges (deep OTM puts). Above 145 means smart money is "
                "quietly insuring against a crash, even if the surface looks "
                "calm."
            ),
        },
        {
            "id": "liquidity",
            "name": "Market Liquidity",
            "icon": "💧",
            "value": liq_status,
            "status": liq_status,
            "meaning": (
                "Based on SPY volume relative to its 30-day average. Thin "
                "liquidity means wider bid-ask spreads, worse fills, and "
                "higher slippage risk on entries and exits."
            ),
        },
    ]

    # ── REGIME NARRATIVE ─────────────────────────────────────────
    # Dynamic weather report that combines all signals
    parts = []

    # Opening sentence based on regime
    if regime == "CRITICAL":
        parts.append(
            f"Market fragility is at CRITICAL levels ({fragility_index}/100). "
            "Multiple structural stress indicators are flashing simultaneously."
        )
    elif regime == "HIGH STRESS":
        parts.append(
            f"The market environment shows HIGH STRESS ({fragility_index}/100). "
            "Structural cracks are visible beneath the surface."
        )
    elif regime == "ELEVATED":
        parts.append(
            f"Fragility is ELEVATED ({fragility_index}/100). "
            "Conditions are not yet dangerous, but warrant heightened vigilance."
        )
    elif regime == "NORMAL":
        parts.append(
            f"Market structure is NORMAL ({fragility_index}/100). "
            "No significant systemic risk detected across monitored indicators."
        )
    else:  # LOW RISK
        parts.append(
            f"Conditions are LOW RISK ({fragility_index}/100). "
            "All systemic indicators signal a stable, liquid environment."
        )

    # Condition-specific sentences
    conditions = []
    if vix_ratio_status == "BACKWARDATION":
        conditions.append(
            "The VIX term structure is inverted, meaning near-term implied "
            "volatility exceeds medium-term — traders are paying a premium "
            "for immediate protection."
        )
    if hyg_status in ("BREAKDOWN", "WEAKENING"):
        severity = "aggressively widening" if hyg_status == "BREAKDOWN" else "beginning to widen"
        conditions.append(
            f"Credit spreads are {severity}. High-yield bonds are "
            "underperforming treasuries, suggesting institutional risk "
            "aversion is rising."
        )
    if corr.get("spy_tlt_flip"):
        conditions.append(
            "Stocks and bonds are falling together — the traditional "
            "diversification hedge has broken down, leaving portfolios "
            "fully exposed."
        )
    elif spy_tlt is not None and spy_tlt > 0.2:
        conditions.append(
            "SPY/TLT correlation is trending positive, which reduces the "
            "effectiveness of bond hedges in a selloff."
        )
    if skew_status in ("CRITICAL", "ELEVATED"):
        conditions.append(
            "Institutional tail-risk hedging activity is elevated, suggesting "
            "smart money sees downside risk that surface-level metrics may "
            "not reflect."
        )
    if liq_status == "THIN":
        conditions.append(
            "Liquidity depth is below normal — position sizing should be "
            "reduced and limit orders preferred over market orders."
        )

    if conditions:
        parts.append(" ".join(conditions))
    elif regime in ("NORMAL", "LOW RISK"):
        parts.append(
            "Volatility is well-contained, credit markets are stable, "
            "and cross-asset correlations are behaving normally. "
            "Conditions are favorable for premium-selling strategies."
        )

    # Posture recommendation
    if fragility_index >= 80:
        parts.append(
            "Recommended posture: DEFENSIVE. Halt new entries, tighten stops "
            "to 2x credit, and consider adding volatility longs as portfolio "
            "insurance."
        )
    elif fragility_index >= 60:
        parts.append(
            "Recommended posture: CAUTIOUS. Reduce position sizing by 50%, "
            "widen strike selection, and avoid short-dated trades until "
            "conditions stabilize."
        )
    elif fragility_index >= 40:
        parts.append(
            "Recommended posture: VIGILANT. Standard position sizing is "
            "acceptable, but monitor credit and correlation signals for "
            "deterioration."
        )
    else:
        parts.append(
            "Recommended posture: FULL DEPLOYMENT. Environment supports "
            "standard premium-selling with normal position sizing and "
            "strike selection."
        )

    return {
        "glossary": glossary,
        "regime_narrative": " ".join(parts),
    }


# ══════════════════════════════════════════════════════════════════
# 4b. SYNTHESIS & RISK OVERLAY (Fragility Index 0–100)
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

    # Build Narrative Intelligence layer
    narrative = _build_narrative_logic(vol, corr, credit, fragility_index, regime)

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
        "narrative_logic": narrative,
    }


# ══════════════════════════════════════════════════════════════════
# PUBLIC API — compute_fragility()
# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
# 5. DATA CONFIDENCE SCORE (Aether-integrated)
# ══════════════════════════════════════════════════════════════════

def _compute_data_confidence() -> dict:
    """
    Evaluates the quality and freshness of data feeds.
    Returns a confidence_score (0-100) indicating how reliable
    the current fragility reading is.

    Factors:
    - Fetch success rate (failed fetches = big penalty)
    - Data freshness (stale feeds = moderate penalty)
    - Total coverage (more successful fetches = higher base confidence)
    """
    total = _fetch_tracker.get("total", 0)
    success = _fetch_tracker.get("success", 0)
    failed = _fetch_tracker.get("failed", 0)
    stale = _fetch_tracker.get("stale", 0)

    if total == 0:
        return {
            "confidence_score": 0,
            "confidence_status": "UNKNOWN",
            "confidence_details": {
                "total_fetches": 0,
                "successful": 0,
                "failed": 0,
                "stale": 0,
                "success_rate": 0,
            },
        }

    # Base confidence from success rate
    success_rate = success / total
    base_score = success_rate * 100

    # Penalize stale data (each stale feed reduces score by 8 points)
    stale_penalty = min(stale * 8, 40)

    # Penalize failed fetches harder (each failure reduces by 12 points)
    fail_penalty = min(failed * 12, 60)

    # Bonus for good coverage (> 8 successful fetches)
    coverage_bonus = min((success - 5) * 3, 15) if success > 5 else 0

    confidence_score = max(0, min(100, int(
        base_score - stale_penalty - fail_penalty + coverage_bonus
    )))

    # Status classification
    if confidence_score >= 70:
        status = "HIGH"
    elif confidence_score >= 40:
        status = "MEDIUM"
    else:
        status = "LOW"

    return {
        "confidence_score": confidence_score,
        "confidence_status": status,
        "confidence_details": {
            "total_fetches": total,
            "successful": success,
            "failed": failed,
            "stale": stale,
            "success_rate": round(success_rate, 2),
        },
    }


def compute_fragility():
    """
    Main entry point. Returns the full fragility payload.
    Cached for 60 seconds to avoid hammering yfinance.
    """
    now = time.time()
    if _cache["data"] and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["data"]

    logger.info("[Fragility] Computing fragility indicators...")

    # Reset fetch tracker for this computation cycle
    _reset_fetch_tracker()

    vol = _compute_volatility_structure()
    corr = _compute_correlations()
    credit = _compute_credit_stress()
    synthesis = _synthesize(vol, corr, credit)

    # Compute data confidence based on fetch results
    confidence = _compute_data_confidence()

    payload = {
        "timestamp": datetime.now().isoformat(),
        "fragility_index": synthesis["fragility_index"],
        "confidence_score": confidence["confidence_score"],
        "confidence_status": confidence["confidence_status"],
        "confidence_details": confidence["confidence_details"],
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
        f"| Confidence: {confidence['confidence_score']}/100 ({confidence['confidence_status']}) "
        f"| Stop: {synthesis['stop_trading']}"
    )

    return payload
