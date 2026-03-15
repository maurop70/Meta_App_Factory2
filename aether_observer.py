from auto_heal import healed_post, auto_heal, diagnose

"""
aether_observer.py — Aether Live Verification Observer
═══════════════════════════════════════════════════════════
Autonomous observer for the Resonance2: Level Up Engine Orchestrator.

Monitors:
  - n8n execution history for the target workflow
  - Tracks failure rate over a rolling window
  - Self-heals by adjusting circuit_breaker.py COOLDOWN_PERIOD if rate > 5%
  - Triggers Soft Pause on Overseer Orchestration if instability persists

Usage:
    python aether_observer.py                    # Monitor 50 executions
    python aether_observer.py --executions 100   # Custom window
    python aether_observer.py --once             # Single snapshot and exit

Part of SWDR v2.1 — Aether Self-Healing Protocol.
"""

import os
import sys
import time
import json
import argparse
import requests
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Config ─────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "Resonance2"))
sys.path.insert(0, SCRIPT_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
except ImportError:
    pass

N8N_API_BASE = "https://humanresource.app.n8n.cloud/api/v1"
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
N8N_HEADERS = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}

# Resonance2: Level Up Engine Orchestrator workflow
TARGET_WORKFLOW_ID = "jKnG1PSiBypgk5Pd"
TARGET_WORKFLOW_NAME = "Resonance2: Level Up Engine Orchestrator"

# Thresholds
FAILURE_RATE_THRESHOLD = 5.0   # percent
COOLDOWN_STEP = 30             # seconds to add per escalation
MAX_COOLDOWN = 600             # 10 minutes maximum cooldown
MIN_COOLDOWN = 30              # 30 seconds minimum cooldown
DEFAULT_EXECUTION_WINDOW = 50
POLL_INTERVAL = 120            # 2 minutes between checks

# Observer log
OBSERVER_LOG = os.path.join(
    os.path.expanduser("~"), ".antigravity", "aether_observer.jsonl"
)
os.makedirs(os.path.dirname(OBSERVER_LOG), exist_ok=True)


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def log_event(event: dict):
    """Append event to observer JSONL log."""
    event["timestamp"] = datetime.now().isoformat()
    try:
        with open(OBSERVER_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")
    except Exception:
        pass


# ── N8N Execution Monitor ─────────────────────────────────
def fetch_executions(limit: int = 50) -> list:
    """Fetch recent executions for the target workflow from n8n API.
    Falls back to global executions if the target workflow has none."""
    if not N8N_API_KEY:
        print(f"[{timestamp()}] ❌ N8N_API_KEY not set — cannot monitor executions")
        return []

    try:
        # First try target workflow specifically
        url = f"{N8N_API_BASE}/executions?workflowId={TARGET_WORKFLOW_ID}&limit={limit}"
        r = requests.get(url, headers=N8N_HEADERS, timeout=15)

        if r.status_code == 401:
            print(f"[{timestamp()}] ❌ N8N API: 401 Unauthorized — Token Decay detected")
            log_event({"event": "token_decay", "status": 401})
            return []

        if r.status_code != 200:
            print(f"[{timestamp()}] ⚠️ N8N API: {r.status_code}")
            return []

        data = r.json().get("data", [])

        if data:
            print(f"[{timestamp()}]    📡 {len(data)} executions from target workflow")
            return data

        # Fallback: fetch all executions (target may have no recent runs)
        print(f"[{timestamp()}]    ℹ️ No executions for target workflow — using global feed")
        url_global = f"{N8N_API_BASE}/executions?limit={limit}"
        r2 = requests.get(url_global, headers=N8N_HEADERS, timeout=15)
        if r2.status_code == 200:
            global_data = r2.json().get("data", [])
            print(f"[{timestamp()}]    📡 {len(global_data)} global executions retrieved")
            return global_data
        return []

    except Exception as e:
        print(f"[{timestamp()}] ❌ N8N API error: {e}")
        return []


def compute_failure_rate(executions: list) -> dict:
    """Compute failure rate from execution history."""
    total = len(executions)
    if total == 0:
        return {"total": 0, "successes": 0, "failures": 0, "rate": 0.0}

    successes = sum(1 for e in executions if e.get("status") == "success"
                    or e.get("finished") is not None and e.get("status") != "error")
    # n8n uses various status values; be broad about what constitutes failure
    failures = sum(1 for e in executions if e.get("status") in ("error", "crashed", "failed"))
    # Some may be "waiting" or "running" — ignore those
    counted = successes + failures

    rate = (failures / counted * 100) if counted > 0 else 0.0

    return {
        "total": total,
        "counted": counted,
        "successes": successes,
        "failures": failures,
        "rate": round(rate, 2),
    }


# ── Self-Healing: Circuit Breaker Cooldown Adjustment ──────
def get_current_cooldown() -> int:
    """Read the current cooldown from the circuit breaker state file."""
    try:
        from circuit_breaker import CircuitBreaker
        cb = CircuitBreaker("resonance2-gemini")
        return cb.cooldown_seconds
    except Exception:
        return 60  # default


def adjust_cooldown(new_cooldown: int):
    """
    Adjust the circuit breaker cooldown by modifying the state.
    Since CircuitBreaker reads from its constructor, we write a sentinel
    config that the next instantiation will pick up.
    """
    config_path = os.path.join(
        os.path.expanduser("~"), ".antigravity", "swdr_tuning.json"
    )
    tuning = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                tuning = json.load(f)
        except Exception:
            pass

    tuning["resonance2_gemini_cooldown"] = new_cooldown
    tuning["resonance2_webhook_cooldown"] = new_cooldown
    tuning["last_adjusted"] = datetime.now().isoformat()

    with open(config_path, "w") as f:
        json.dump(tuning, f, indent=2)

    print(f"[{timestamp()}] 🔧 Cooldown adjusted to {new_cooldown}s (written to swdr_tuning.json)")
    log_event({"event": "cooldown_adjusted", "new_cooldown": new_cooldown})


def soft_pause_overseer():
    """Trigger a Soft Pause on Resonance2: Overseer Orchestration."""
    try:
        from error_aggregator import ErrorAggregator
        ErrorAggregator("Aether").log_critical(
            "SOFT PAUSE: Aether observer triggered Overseer pause — failure rate above threshold",
            context={
                "workflow": TARGET_WORKFLOW_NAME,
                "workflow_id": TARGET_WORKFLOW_ID,
                "action": "overseer_soft_pause",
            }
        )
    except ImportError:
        pass

    # Deactivate the workflow via n8n API (POST /deactivate endpoint)
    try:
        url = f"{N8N_API_BASE}/workflows/{TARGET_WORKFLOW_ID}/deactivate"
        r = requests.post(url, headers=N8N_HEADERS, timeout=10)
        if r.status_code in (200, 204):
            print(f"[{timestamp()}] 🛑 SOFT PAUSE: Workflow {TARGET_WORKFLOW_ID} DEACTIVATED via n8n API")
            log_event({"event": "soft_pause", "workflow_id": TARGET_WORKFLOW_ID, "deactivated": True})
        else:
            print(f"[{timestamp()}] ⚠️ Soft Pause API response: {r.status_code}")
            log_event({"event": "soft_pause", "workflow_id": TARGET_WORKFLOW_ID, "deactivated": False, "status": r.status_code})
    except Exception as e:
        print(f"[{timestamp()}] ⚠️ Soft Pause failed: {e}")
        log_event({"event": "soft_pause_error", "error": str(e)})


# ── Core Observation Loop ─────────────────────────────────
_escalation_level = 0  # 0 = normal, 1 = cooldown bumped, 2 = soft paused


def observe(execution_window: int = 50) -> dict:
    """Run a single observation cycle."""
    global _escalation_level

    print(f"\n[{timestamp()}] 🔭 Aether Observer — checking {TARGET_WORKFLOW_NAME}")
    print(f"[{timestamp()}]    Window: last {execution_window} executions")

    executions = fetch_executions(limit=execution_window)
    if not executions:
        print(f"[{timestamp()}]    ⚠️ No executions retrieved")
        return {"status": "no_data"}

    stats = compute_failure_rate(executions)
    rate = stats["rate"]

    rate_icon = "🟢" if rate < 5 else "🟡" if rate < 15 else "🔴"
    print(f"[{timestamp()}]    {rate_icon} Failure Rate: {rate}% "
          f"({stats['failures']}/{stats['counted']} failed, "
          f"{stats['successes']} ok)")

    log_event({
        "event": "observation",
        "failure_rate": rate,
        "stats": stats,
        "escalation_level": _escalation_level,
    })

    # Self-Healing Logic
    if rate <= FAILURE_RATE_THRESHOLD:
        if _escalation_level > 0:
            print(f"[{timestamp()}]    ✅ Failure rate within threshold — de-escalating")
            _escalation_level = 0
        return {"status": "stable", "rate": rate, "stats": stats}

    # Rate exceeds threshold — escalate
    if _escalation_level == 0:
        # Level 1: Bump cooldown
        current_cd = get_current_cooldown()
        new_cd = min(current_cd + COOLDOWN_STEP, MAX_COOLDOWN)
        print(f"[{timestamp()}]    ⚠️ Rate {rate}% > {FAILURE_RATE_THRESHOLD}% — "
              f"escalating: bump cooldown {current_cd}s → {new_cd}s")
        adjust_cooldown(new_cd)
        _escalation_level = 1
        return {"status": "escalated_cooldown", "rate": rate, "new_cooldown": new_cd}

    elif _escalation_level == 1:
        # Level 2: If still failing after cooldown bump, Soft Pause
        print(f"[{timestamp()}]    🛑 Rate still {rate}% — triggering SOFT PAUSE on Overseer")
        soft_pause_overseer()
        _escalation_level = 2
        return {"status": "soft_paused", "rate": rate}

    else:
        # Already paused — just report
        print(f"[{timestamp()}]    🛑 Overseer already paused — rate: {rate}%")
        return {"status": "paused_monitoring", "rate": rate}


# ── Document File Watcher ─────────────────────────────────
# Monitors project folders for new documents and auto-routes
# them through DocumentParserService.

WATCH_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".csv"}
WATCH_POLL_INTERVAL = 30  # seconds

# Directories to watch (all first-level subdirectories of the Factory)
_WATCH_ROOT = SCRIPT_DIR


def _start_file_watcher():
    """Start a background thread that watches for new documents."""
    import threading

    def _watcher_loop():
        try:
            from document_parser_service import DocumentParserService
            from document_router import DocumentRouter
        except ImportError:
            print(f"[{timestamp()}] ⚠️ FileWatcher: DocumentParserService not found — watcher disabled")
            return

        parser = DocumentParserService()
        router = DocumentRouter()
        seen_files = set()

        print(f"[{timestamp()}] 📂 FileWatcher: Active — monitoring {_WATCH_ROOT}")

        while True:
            try:
                # Walk all project subdirectories
                for dirpath, dirnames, filenames in os.walk(_WATCH_ROOT):
                    # Skip hidden dirs, node_modules, __pycache__, .git
                    dirnames[:] = [d for d in dirnames if not d.startswith('.')
                                   and d not in ('node_modules', '__pycache__', 'dist', '.git')]
                    for fname in filenames:
                        ext = os.path.splitext(fname)[1].lower()
                        if ext not in WATCH_EXTENSIONS:
                            continue
                        full = os.path.join(dirpath, fname)
                        if full in seen_files:
                            continue
                        seen_files.add(full)

                        # Determine source app from directory
                        rel = os.path.relpath(dirpath, _WATCH_ROOT)
                        source_app = rel.split(os.sep)[0] if rel != '.' else 'Meta_App_Factory'

                        print(f"[{timestamp()}] 📄 FileWatcher: New document detected → {fname} ({source_app})")
                        log_event({"event": "file_detected", "file": fname, "source_app": source_app})

                        result = parser.parse(full, source_app=source_app)
                        if result.get("status") == "parsed":
                            result = router.route(result)
                            parser.log_to_master_index(result)
                            print(f"[{timestamp()}]    ✅ Parsed → {result['category']} → {result['routing'].get('destination', 'index')}")
                        elif result.get("status") == "skipped":
                            pass  # Already parsed (dedup)
                        else:
                            print(f"[{timestamp()}]    ⚠️ Parse issue: {result.get('error', 'unknown')}")

            except Exception as e:
                print(f"[{timestamp()}] [FileWatcher ERROR] {e}")

            time.sleep(WATCH_POLL_INTERVAL)

    t = threading.Thread(target=_watcher_loop, daemon=True, name="DocumentFileWatcher")
    t.start()
    print(f"[{timestamp()}] 📂 FileWatcher thread started (poll every {WATCH_POLL_INTERVAL}s)")
    return t


# ── Entry Point ─────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aether Live Verification Observer")
    parser.add_argument("--executions", type=int, default=DEFAULT_EXECUTION_WINDOW,
                        help=f"Execution window to monitor (default: {DEFAULT_EXECUTION_WINDOW})")
    parser.add_argument("--once", action="store_true", help="Run a single observation and exit")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL,
                        help=f"Poll interval in seconds (default: {POLL_INTERVAL}s)")
    parser.add_argument("--watch", action="store_true",
                        help="Enable document file watcher for all project folders")
    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print(f"  🔭 AETHER LIVE VERIFICATION OBSERVER v2.2")
    print(f"  Target: {TARGET_WORKFLOW_NAME}")
    print(f"  Window: {args.executions} executions")
    print(f"  Threshold: {FAILURE_RATE_THRESHOLD}% failure rate")
    print(f"  Self-Heal: Auto-adjust cooldown → Soft Pause")
    print(f"  File Watcher: {'ENABLED' if args.watch else 'DISABLED'}")
    print(f"  Log: {OBSERVER_LOG}")
    print(f"{'=' * 60}")

    # ── Start Document File Watcher (if enabled) ──────────
    _file_watcher_thread = None
    if args.watch:
        _file_watcher_thread = _start_file_watcher()

    if args.once:
        result = observe(args.executions)
        print(f"\n  Final: {json.dumps(result, indent=2)}")
        sys.exit(0 if result.get("status") == "stable" else 1)

    cycle = 0
    while True:
        cycle += 1
        try:
            print(f"\n[{timestamp()}] ─── Observation Cycle {cycle} ───")
            result = observe(args.executions)

            if result.get("status") == "soft_paused":
                print(f"\n[{timestamp()}] 🛑 Overseer PAUSED — observer going to extended sleep (5 min)")
                time.sleep(300)

        except KeyboardInterrupt:
            print(f"\n[{timestamp()}] Aether Observer stopped.")
            if _file_watcher_thread:
                _file_watcher_thread.join(timeout=2)
            sys.exit(0)
        except Exception as e:
            print(f"[{timestamp()}] [ERROR] {e}")

        print(f"[{timestamp()}] Next observation in {args.interval}s...")
        time.sleep(args.interval)

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
# V2.2: + DocumentFileWatcher integration
