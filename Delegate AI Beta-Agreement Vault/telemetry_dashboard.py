"""
Antigravity Telemetry Dashboard — Unified system health view.
Aggregates data from: Error Aggregator, Circuit Breaker, Budget Guard, Preflight.
Usage:
    python telemetry_dashboard.py           # Print full dashboard
    python telemetry_dashboard.py --json    # Output as JSON (for UI consumption)
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


import os, sys, json
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _safe_import(module_name):
    """Safely import a module, return None if not available."""
    try:
        sys.path.insert(0, SCRIPT_DIR)
        return __import__(module_name)
    except ImportError:
        return None


def collect_error_summary():
    """Get error aggregator summary."""
    mod = _safe_import("error_aggregator")
    if not mod:
        return {"available": False}
    try:
        summary = mod.ErrorAggregator.get_summary()
        recent = mod.ErrorAggregator.read_recent(5)
        return {
            "available": True,
            "total_entries": summary["total"],
            "by_severity": summary["by_severity"],
            "by_app": summary["by_app"],
            "recent": [
                {"timestamp": e["timestamp"][:19], "app": e["app"],
                 "severity": e["severity"], "message": e["message"]}
                for e in recent
            ],
        }
    except Exception as e:
        return {"available": True, "error": str(e)}


def collect_circuit_breaker_status():
    """Get circuit breaker status for all registered breakers."""
    state_dir = os.path.join(os.path.expanduser("~"), ".antigravity", "circuit_breakers")
    if not os.path.exists(state_dir):
        return {"available": True, "breakers": []}

    mod = _safe_import("circuit_breaker")
    if not mod:
        return {"available": False}

    breakers = []
    try:
        for fname in os.listdir(state_dir):
            if fname.endswith(".json"):
                name = fname[:-5]
                cb = mod.CircuitBreaker(name)
                breakers.append(cb.get_status())
    except Exception as e:
        return {"available": True, "error": str(e)}

    return {"available": True, "breakers": breakers}


def collect_budget_summary():
    """Get N8N budget summary from last check."""
    budget_log = os.path.join(SCRIPT_DIR, "Alpha_Data", "n8n_execution_log.json")
    if not os.path.exists(budget_log):
        return {"available": True, "last_check": None, "message": "No budget data yet — run n8n_budget_guard.py"}

    try:
        with open(budget_log, "r") as f:
            log = json.load(f)
        limit = log.get("monthly_limit", 10000)
        history = log.get("history", [])
        if not history:
            return {"available": True, "last_check": None}

        latest = history[-1]
        pct = round(latest["total_executions"] / max(limit, 1) * 100, 1)

        return {
            "available": True,
            "last_check": latest["timestamp"][:19],
            "total_executions": latest["total_executions"],
            "monthly_limit": limit,
            "usage_pct": pct,
            "failure_rate": latest.get("failure_rate", 0),
            "active_workflows": latest.get("active_workflows", 0),
            "status": "critical" if pct >= 90 else "warning" if pct >= 70 else "ok",
        }
    except Exception as e:
        return {"available": True, "error": str(e)}


def collect_config_snapshots():
    """Get config snapshot summary."""
    manifest_path = os.path.join(SCRIPT_DIR, "Alpha_Data", ".config_snapshots", "manifest.json")
    if not os.path.exists(manifest_path):
        return {"available": True, "total_snapshots": 0, "files": []}

    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        snapshots = manifest.get("snapshots", [])
        files = {}
        for s in snapshots:
            f = s["file"]
            if f not in files:
                files[f] = {"count": 0, "latest": s["timestamp"]}
            files[f]["count"] += 1
            files[f]["latest"] = max(files[f]["latest"], s["timestamp"])

        return {
            "available": True,
            "total_snapshots": len(snapshots),
            "files": [{"file": k, **v} for k, v in files.items()],
        }
    except Exception as e:
        return {"available": True, "error": str(e)}


def collect_all():
    """Collect all telemetry data."""
    return {
        "timestamp": datetime.now().isoformat(),
        "errors": collect_error_summary(),
        "circuit_breakers": collect_circuit_breaker_status(),
        "budget": collect_budget_summary(),
        "config_snapshots": collect_config_snapshots(),
    }


def print_dashboard(data):
    """Print a human-readable dashboard."""
    print(f"\n{'='*60}")
    print(f"  ANTIGRAVITY TELEMETRY DASHBOARD")
    print(f"  {data['timestamp'][:19]}")
    print(f"{'='*60}")

    # ── Budget ──
    b = data["budget"]
    print(f"\n  📊 N8N EXECUTION BUDGET")
    if b.get("last_check"):
        icons = {"ok": "✅", "warning": "⚠️ ", "critical": "🚨"}
        print(f"     {icons.get(b['status'], '❓')} {b['total_executions']} / {b['monthly_limit']} ({b['usage_pct']}%)")
        print(f"     Failure rate: {b['failure_rate']}%  |  Active workflows: {b['active_workflows']}")
        print(f"     Last checked: {b['last_check']}")
    else:
        print(f"     No data yet — run: python n8n_budget_guard.py")

    # ── Circuit Breakers ──
    cb = data["circuit_breakers"]
    print(f"\n  🔌 CIRCUIT BREAKERS")
    if cb.get("breakers"):
        for br in cb["breakers"]:
            icons = {"CLOSED": "🟢", "OPEN": "🔴", "HALF_OPEN": "🟡"}
            icon = icons.get(br["state"], "❓")
            line = f"     {icon} {br['name']}: {br['state']}"
            line += f" (ok: {br['total_successes']} | fail: {br['total_failures']})"
            if br.get("cooldown_remaining_s"):
                line += f" — cooldown: {br['cooldown_remaining_s']}s"
            print(line)
    else:
        print(f"     No circuit breakers registered yet (auto-created on first N8N call).")

    # ── Errors ──
    e = data["errors"]
    print(f"\n  🚨 ERROR LOG")
    if e.get("available") and e.get("total_entries", 0) > 0:
        print(f"     Total entries: {e['total_entries']}")
        for sev, count in e.get("by_severity", {}).items():
            icons = {"error": "❌", "warning": "⚠️ ", "info": "ℹ️ ", "critical": "🚨"}
            print(f"       {icons.get(sev, '❓')} {sev}: {count}")
        if e.get("recent"):
            print(f"     Recent:")
            for r in e["recent"][-3:]:
                print(f"       [{r['timestamp']}] {r['app']}: {r['message']}")
    else:
        print(f"     No errors logged. System is clean.")

    # ── Config Snapshots ──
    cs = data["config_snapshots"]
    print(f"\n  📸 CONFIG SNAPSHOTS")
    if cs.get("total_snapshots", 0) > 0:
        print(f"     {cs['total_snapshots']} snapshots across {len(cs['files'])} files")
        for f in cs["files"]:
            print(f"       {f['file']}: {f['count']} snapshots (latest: {f['latest'][:19]})")
    else:
        print(f"     No snapshots yet (auto-created before config mutations).")

    print(f"\n{'='*60}\n")


# ── CLI ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Antigravity Telemetry Dashboard")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
    except ImportError:
        pass

    data = collect_all()

    if args.json:
        print(json.dumps(data, indent=2, default=str))
    else:
        print_dashboard(data)
# V3 AUTO-HEAL ACTIVE
