"""
Alpha V2 Genesis — Performance Audit Module
=============================================
Aether-powered profiling for all Alpha Architect core scripts.
Instruments key functions with wall-clock timing, stores results
in Alpha_Data/perf_audit.json, and ranks the top 3 bottlenecks.

Usage:
    python performance_audit.py              # Run full audit
    python performance_audit.py --json       # Output as JSON

Programmatic:
    from performance_audit import run_audit
    report = run_audit()
"""

# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

from auto_heal import healed_post, auto_heal, diagnose

def _v3_preflight():
    """V3: Ping Resonance_Watchdog_V3 before execution."""
    if not _V3_AVAILABLE:
        return True
    try:
        import json as _j
        _cfg_path = _os.path.join(_FACTORY_DIR, "resilience_config.json")
        if not _os.path.exists(_cfg_path):
            return True
        with open(_cfg_path) as _f:
            _cfg = _j.load(_f)
        _url = _cfg.get("cloud_health", {}).get("watchdog_url", "")
        if not _url:
            return True
        import requests as _rq
        _r = _rq.get(_url, timeout=5)
        return _r.status_code == 200
    except Exception:
        return False


import os
import sys
import json
import time
import logging
import functools
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

logger = logging.getLogger("PerformanceAudit")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "Alpha_Data")
os.makedirs(DATA_DIR, exist_ok=True)
PERF_LOG = os.path.join(DATA_DIR, "perf_audit.json")


# ── Timing Registry ─────────────────────────────────────────────
_timing_results: list[dict] = []


def timed(label: str = ""):
    """Decorator that records wall-clock execution time of a function."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = label or f"{func.__module__}.{func.__qualname__}"
            start = time.perf_counter()
            error = None
            result = None
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error = str(e)
                raise
            finally:
                elapsed = time.perf_counter() - start
                entry = {
                    "name": name,
                    "duration_s": round(elapsed, 3),
                    "status": "error" if error else "ok",
                    "error": error,
                    "timestamp": datetime.now().isoformat(),
                }
                _timing_results.append(entry)
                logger.info(
                    "⏱️  %s: %.3fs [%s]", name, elapsed,
                    "OK" if not error else f"ERROR: {error}"
                )
        return wrapper
    return decorator


def get_timing_results() -> list[dict]:
    """Return all collected timing entries."""
    return list(_timing_results)


def get_top_bottlenecks(n: int = 3) -> list[dict]:
    """Return the top N slowest successful executions."""
    ok_runs = [r for r in _timing_results if r["status"] == "ok"]
    ranked = sorted(ok_runs, key=lambda r: r["duration_s"], reverse=True)
    return ranked[:n]


def clear_results():
    """Reset the timing registry."""
    _timing_results.clear()


# ── Full Audit Runner ────────────────────────────────────────────

def run_audit() -> dict:
    """
    Execute the core Alpha Architect functions under profiling
    and return a structured bottleneck report.
    """
    clear_results()
    report = {
        "audit_timestamp": datetime.now().isoformat(),
        "suite": "Alpha_V2_Genesis",
        "measurements": [],
        "top_bottlenecks": [],
        "errors": [],
    }

    # ── 1. Fragility Engine ──────────────────────────────────
    try:
        sys.path.insert(0, SCRIPT_DIR)
        from fragility_engine import (
            _fetch_history,
            _compute_volatility_structure,
            _compute_correlations,
            _compute_credit_stress,
            compute_fragility,
        )

        # Profile individual sub-functions
        for label, func in [
            ("fragility._fetch_history(^GSPC)", lambda: _fetch_history("^GSPC", "3mo")),
            ("fragility._compute_volatility_structure", _compute_volatility_structure),
            ("fragility._compute_correlations", _compute_correlations),
            ("fragility._compute_credit_stress", _compute_credit_stress),
        ]:
            _run_timed(label, func, report)

        # Profile the full compute — clear cache first
        from fragility_engine import _cache
        _cache["data"] = None
        _cache["ts"] = 0
        _run_timed("fragility.compute_fragility (full)", compute_fragility, report)

    except ImportError as e:
        report["errors"].append(f"Fragility Engine import failed: {e}")

    # ── 2. Strategy Ledger ───────────────────────────────────
    try:
        from strategy_ledger import run_ledger, load_state
        _run_timed("strategy_ledger.load_state", load_state, report)
        # run_ledger does yfinance calls so it's a significant bottleneck candidate
        _run_timed("strategy_ledger.run_ledger", lambda: run_ledger(force_full=False), report)
    except ImportError as e:
        report["errors"].append(f"Strategy Ledger import failed: {e}")

    # ── 3. Loki Engine ───────────────────────────────────────
    try:
        from skills.loki.loki import Loki
        portfolio_path = os.path.join(DATA_DIR, "portfolio.json")
        if os.path.exists(portfolio_path):
            loki = Loki(portfolio_path=portfolio_path)
            _run_timed("loki.run_strategy", lambda: loki.run_strategy(availability=2000), report)
    except (ImportError, Exception) as e:
        report["errors"].append(f"Loki Engine: {e}")

    # ── 4. Telemetry Dashboard ───────────────────────────────
    try:
        from telemetry_dashboard import collect_all
        _run_timed("telemetry_dashboard.collect_all", collect_all, report)
    except ImportError as e:
        report["errors"].append(f"Telemetry Dashboard import failed: {e}")

    # ── Compile Results ──────────────────────────────────────
    report["measurements"] = get_timing_results()
    report["top_bottlenecks"] = get_top_bottlenecks(3)
    report["total_scripts_profiled"] = len(report["measurements"])
    report["total_duration_s"] = round(
        sum(m["duration_s"] for m in report["measurements"]), 3
    )

    # Persist
    _save_report(report)

    return report


def _run_timed(label: str, func, report: dict):
    """Run a function with timing, catch errors gracefully."""
    start = time.perf_counter()
    error = None
    try:
        func()
    except Exception as e:
        error = str(e)
        report["errors"].append(f"{label}: {e}")
    elapsed = time.perf_counter() - start
    _timing_results.append({
        "name": label,
        "duration_s": round(elapsed, 3),
        "status": "error" if error else "ok",
        "error": error,
        "timestamp": datetime.now().isoformat(),
    })
    logger.info("⏱️  %s: %.3fs [%s]", label, elapsed, "OK" if not error else "ERROR")


def _save_report(report: dict):
    """Persist the audit report to JSON."""
    try:
        # Keep history of last 20 audits
        history = []
        if os.path.exists(PERF_LOG):
            try:
                with open(PERF_LOG, "r", encoding="utf-8") as f:
                    history = json.load(f)
                if not isinstance(history, list):
                    history = [history]
            except Exception:
                history = []
        history.append(report)
        history = history[-20:]
        with open(PERF_LOG, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, default=str)
    except Exception as e:
        logger.error("Failed to save perf audit: %s", e)


def load_latest_report() -> dict | None:
    """Load the most recent audit report from disk."""
    if not os.path.exists(PERF_LOG):
        return None
    try:
        with open(PERF_LOG, "r", encoding="utf-8") as f:
            history = json.load(f)
        if isinstance(history, list) and history:
            return history[-1]
        return history
    except Exception:
        return None


# ── CLI ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Alpha Architect Performance Audit")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
    except ImportError:
        pass

    report = run_audit()

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"\n{'='*60}")
        print(f"  ALPHA ARCHITECT — PERFORMANCE AUDIT")
        print(f"  {report['audit_timestamp'][:19]}")
        print(f"{'='*60}")
        print(f"\n  Total scripts profiled: {report['total_scripts_profiled']}")
        print(f"  Total duration: {report['total_duration_s']}s")

        if report["top_bottlenecks"]:
            print(f"\n  🏆 TOP 3 BOTTLENECKS:")
            for i, b in enumerate(report["top_bottlenecks"], 1):
                print(f"    {i}. {b['name']}: {b['duration_s']}s")

        if report["errors"]:
            print(f"\n  ⚠️  ERRORS ({len(report['errors'])}):")
            for err in report["errors"]:
                print(f"    ❌ {err}")

        print(f"\n{'='*60}\n")
# V3 AUTO-HEAL ACTIVE
