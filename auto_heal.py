"""
auto_heal.py — V3.0 Active Self-Repair Engine
═══════════════════════════════════════════════
Turns passive resilience (buffer & retry later) into
active self-repair (retry now, diagnose, escalate).

Usage (child apps):
    from auto_heal import healed_post, diagnose

    status = healed_post(url, payload, project="MyApp")
    # Returns "sent", "healed", "buffered", "escalated"

    # Or wrap any operation:
    from auto_heal import auto_heal
    result = auto_heal(my_function, *args, **kwargs)

Part of System Hardening V3.0 — Meta_App_Factory.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from functools import wraps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger("v3.auto_heal")

# ── Configuration ────────────────────────────────────────
MAX_RETRIES = 3
BACKOFF_BASE = 2          # seconds — exponential: 2, 4, 8
BACKOFF_MAX = 30           # cap at 30s
WATCHDOG_TIMEOUT = 5
HEAL_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_heal_log.json")


# ═══════════════════════════════════════════════════════════
#  DIAGNOSE — Why is the cloud failing?
# ═══════════════════════════════════════════════════════════

def diagnose() -> dict:
    """
    Run a full self-diagnosis of the V3 infrastructure.
    Returns a dict with status of each component.
    """
    import requests
    factory_dir = os.path.dirname(os.path.abspath(__file__))
    report = {
        "timestamp": datetime.now().isoformat(),
        "watchdog": {"status": "unknown"},
        "credentials": {"status": "unknown"},
        "state_manager": {"status": "unknown"},
        "buffer": {"status": "unknown"},
        "verdict": "unknown",
    }

    # 1. Watchdog health
    try:
        cfg_path = os.path.join(factory_dir, "resilience_config.json")
        with open(cfg_path) as f:
            cfg = json.load(f)
        url = cfg.get("cloud_health", {}).get("watchdog_url", "")
        if url:
            start = time.time()
            r = requests.get(url, timeout=WATCHDOG_TIMEOUT)
            ms = (time.time() - start) * 1000
            report["watchdog"] = {
                "status": "green" if r.status_code == 200 and ms < 1000 else
                          "yellow" if r.status_code == 200 else "red",
                "code": r.status_code,
                "latency_ms": round(ms),
            }
    except requests.exceptions.RequestException as e:
        report["watchdog"] = {"status": "red", "error": str(e)}
    except Exception as e:
        report["watchdog"] = {"status": "error", "error": str(e)}

    # 2. Credential check
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(factory_dir, ".env"), override=True)
        key = os.getenv("N8N_API_KEY", "")
        if len(key) > 50:
            # Quick validation — try listing workflows
            headers = {"X-N8N-API-KEY": key}
            r = requests.get(
                "https://humanresource.app.n8n.cloud/api/v1/workflows?limit=1",
                headers=headers, timeout=5
            )
            report["credentials"] = {
                "status": "valid" if r.status_code == 200 else "expired",
                "code": r.status_code,
                "key_length": len(key),
            }
        else:
            report["credentials"] = {"status": "missing", "key_length": len(key)}
    except Exception as e:
        report["credentials"] = {"status": "error", "error": str(e)}

    # 3. StateManager
    try:
        from local_state_manager import StateManager
        sm = StateManager()
        stats = sm.get_stats()
        report["state_manager"] = {
            "status": "operational",
            "safe_buffer_mode": stats.get("safe_buffer_mode", False),
            "pending": stats.get("pending", 0),
            "failed": stats.get("failed", 0),
        }
    except Exception as e:
        report["state_manager"] = {"status": "error", "error": str(e)}

    # 4. Buffer check
    pending_dir = os.path.join(factory_dir, "pending_sync")
    pending_files = []
    if os.path.isdir(pending_dir):
        pending_files = [f for f in os.listdir(pending_dir) if f.endswith(".json")]
    report["buffer"] = {
        "status": "clear" if len(pending_files) == 0 else "has_items",
        "pending_files": len(pending_files),
    }

    # Verdict
    if report["watchdog"]["status"] == "red":
        report["verdict"] = "CLOUD_DOWN"
    elif report["credentials"]["status"] == "expired":
        report["verdict"] = "CREDENTIAL_DECAY"
    elif report["credentials"]["status"] == "missing":
        report["verdict"] = "CREDENTIAL_MISSING"
    elif report["state_manager"].get("safe_buffer_mode"):
        report["verdict"] = "SAFE_BUFFER_ACTIVE"
    elif report["watchdog"]["status"] == "yellow":
        report["verdict"] = "DEGRADED"
    else:
        report["verdict"] = "HEALTHY"

    return report


# ═══════════════════════════════════════════════════════════
#  HEALED POST — safe_post + retry + backoff + diagnosis
# ═══════════════════════════════════════════════════════════

def healed_post(url: str, payload: dict, project: str = "child_app",
                max_retries: int = MAX_RETRIES, timeout: int = 60) -> str:
    """
    Auto-Healing POST — wraps safe_post with active self-repair.

    Flow:
    1. Call safe_post()
    2. If "sent" → done (return "sent")
    3. If "failed" → retry with exponential backoff up to max_retries
       - If retry succeeds → return "healed"
    4. If all retries fail → run diagnose() to determine root cause
       - Log diagnosis to auto_heal_log.json
       - If credential_decay → flag for rotation
       - Data is already buffered by safe_post → return "buffered"
    5. If unrecoverable → return "escalated"

    Returns:
        "sent"      — delivered on first attempt
        "healed"    — failed initially, succeeded on retry
        "buffered"  — cloud unreachable, data queued for Recovery Sync
        "escalated" — persistent failure, diagnosis logged
    """
    from factory import safe_post

    # Attempt 1
    status = safe_post(url, payload, project=project, timeout=timeout)
    if status == "sent":
        return "sent"

    # If buffered (cloud down), diagnose immediately — no point retrying
    if status == "buffered":
        _log_heal_event(project, url, "buffered_on_first", None)
        return "buffered"

    # Status is "failed" (5xx from server) — retry with backoff
    for attempt in range(1, max_retries + 1):
        wait = min(BACKOFF_BASE ** attempt, BACKOFF_MAX)
        logger.info(f"[Auto-Heal] {project}: retry {attempt}/{max_retries} in {wait}s")
        time.sleep(wait)

        status = safe_post(url, payload, project=project, timeout=timeout)
        if status == "sent":
            _log_heal_event(project, url, "healed", attempt)
            return "healed"
        if status == "buffered":
            _log_heal_event(project, url, "buffered_on_retry", attempt)
            return "buffered"

    # All retries exhausted — diagnose
    diag = diagnose()
    _log_heal_event(project, url, "escalated", max_retries, diag)

    # Attempt auto-remediation based on diagnosis
    if diag["verdict"] == "CREDENTIAL_DECAY":
        logger.warning(f"[Auto-Heal] {project}: CREDENTIAL DECAY detected — key rotation needed")
    elif diag["verdict"] == "CLOUD_DOWN":
        logger.warning(f"[Auto-Heal] {project}: Cloud is DOWN — data buffered for Recovery Sync")
    elif diag["verdict"] == "SAFE_BUFFER_ACTIVE":
        logger.info(f"[Auto-Heal] {project}: Safe-Buffer already active — Recovery Sync will handle")

    return "escalated"


# ═══════════════════════════════════════════════════════════
#  N8N-SPECIFIC THROTTLED POST (Resilience Patch v3.0)
#  Backoff: 30s → 60s → 120s → 240s (cap 300s)
# ═══════════════════════════════════════════════════════════

def _load_n8n_backoff_config() -> dict:
    """Load n8n-specific backoff config from resilience_config.json."""
    try:
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resilience_config.json")
        with open(cfg_path) as f:
            cfg = json.load(f)
        return cfg.get("n8n_backoff", {})
    except Exception:
        return {}


def healed_post_n8n(url: str, payload: dict, project: str = "n8n_bridge",
                    timeout: int = 60) -> str:
    """
    N8N-specific auto-healing POST with aggressive exponential backoff.

    Designed to prevent IP rate-limiting on n8n cloud:
      - Base: 30s (vs default 2s)
      - Doubling: 30s → 60s → 120s → 240s
      - Max: 300s (5 minutes)
      - Retries: 5 (vs default 3)

    Reads backoff profile from resilience_config.json for hot-configurability.
    """
    from factory import safe_post

    n8n_cfg = _load_n8n_backoff_config()
    base = n8n_cfg.get("base_seconds", 30)
    cap = n8n_cfg.get("max_seconds", 300)
    retries = n8n_cfg.get("max_retries", 5)

    # Attempt 1
    status = safe_post(url, payload, project=project, timeout=timeout)
    if status == "sent":
        return "sent"
    if status == "buffered":
        _log_heal_event(project, url, "buffered_on_first", None)
        return "buffered"

    # Retry with n8n-throttled backoff: 30, 60, 120, 240, 300
    for attempt in range(1, retries + 1):
        wait = min(base * (2 ** (attempt - 1)), cap)
        logger.info(f"[Auto-Heal/n8n] {project}: retry {attempt}/{retries} in {wait}s")
        time.sleep(wait)

        status = safe_post(url, payload, project=project, timeout=timeout)
        if status == "sent":
            _log_heal_event(project, url, "healed_n8n", attempt)
            return "healed"
        if status == "buffered":
            _log_heal_event(project, url, "buffered_n8n_retry", attempt)
            return "buffered"

    # All retries exhausted
    diag = diagnose()
    _log_heal_event(project, url, "escalated_n8n", retries, diag)
    logger.error(f"[Auto-Heal/n8n] {project}: ESCALATED after {retries} n8n retries. Verdict: {diag['verdict']}")
    return "escalated"


# ═══════════════════════════════════════════════════════════
#  AUTO HEAL DECORATOR — wrap any function with self-repair
# ═══════════════════════════════════════════════════════════

def auto_heal(func=None, *, max_retries=MAX_RETRIES, project="unknown"):
    """
    Decorator that wraps any function with auto-heal retry + diagnosis.

    Usage:
        @auto_heal(project="MyApp")
        def my_critical_function():
            ...

    If the function raises an exception, auto_heal will:
    1. Retry with exponential backoff
    2. On persistent failure, run diagnose() and log
    3. Never crash — always returns None on failure
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        wait = min(BACKOFF_BASE ** (attempt + 1), BACKOFF_MAX)
                        logger.warning(
                            f"[Auto-Heal] {project}.{fn.__name__}: "
                            f"attempt {attempt+1}/{max_retries} failed ({e}), "
                            f"retrying in {wait}s"
                        )
                        time.sleep(wait)

            # All retries exhausted
            diag = diagnose()
            _log_heal_event(
                project, f"func:{fn.__name__}", "escalated",
                max_retries, diag, str(last_error)
            )
            logger.error(
                f"[Auto-Heal] {project}.{fn.__name__}: ESCALATED after "
                f"{max_retries} retries. Verdict: {diag['verdict']}"
            )
            return None
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


# ═══════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════

def _log_heal_event(project: str, target: str, outcome: str,
                    attempts: int = None, diagnosis: dict = None,
                    error: str = None):
    """Append a heal event to auto_heal_log.json."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "project": project,
        "target": target,
        "outcome": outcome,
        "attempts": attempts,
    }
    if diagnosis:
        entry["diagnosis"] = {
            "verdict": diagnosis.get("verdict"),
            "watchdog": diagnosis.get("watchdog", {}).get("status"),
            "credentials": diagnosis.get("credentials", {}).get("status"),
            "buffer_pending": diagnosis.get("buffer", {}).get("pending_files", 0),
        }
    if error:
        entry["error"] = error[:200]

    try:
        log = []
        if os.path.exists(HEAL_LOG):
            with open(HEAL_LOG, "r", encoding="utf-8") as f:
                log = json.load(f)
        log.append(entry)
        # Keep last 500 entries
        if len(log) > 500:
            log = log[-500:]
        with open(HEAL_LOG, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2, default=str)
    except Exception:
        pass  # Never crash on logging


# ═══════════════════════════════════════════════════════════
#  CLI — Direct diagnosis
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  V3.0 Auto-Heal — System Diagnosis")
    print(f"{'='*60}\n")

    report = diagnose()

    icons = {"green": "🟢", "yellow": "🟡", "red": "🔴",
             "valid": "🟢", "expired": "🔴", "missing": "🔴",
             "operational": "🟢", "clear": "🟢", "has_items": "🟡",
             "error": "🔴", "unknown": "⚪"}

    wd = report["watchdog"]
    cr = report["credentials"]
    sm = report["state_manager"]
    bf = report["buffer"]

    print(f"  Watchdog:     {icons.get(wd['status'], '⚪')} {wd['status'].upper()}"
          f" ({wd.get('latency_ms', '?')}ms)" if 'latency_ms' in wd else f"  Watchdog:     {icons.get(wd['status'], '⚪')} {wd['status'].upper()}")
    print(f"  Credentials:  {icons.get(cr['status'], '⚪')} {cr['status'].upper()}")
    print(f"  StateManager: {icons.get(sm['status'], '⚪')} {sm['status'].upper()}"
          f" (buffer={'ON' if sm.get('safe_buffer_mode') else 'OFF'}, pending={sm.get('pending', '?')})")
    print(f"  Buffer:       {icons.get(bf['status'], '⚪')} {bf.get('pending_files', 0)} files")

    print(f"\n  VERDICT: {report['verdict']}")

    # Show recent heal events
    if os.path.exists(HEAL_LOG):
        with open(HEAL_LOG) as f:
            events = json.load(f)
        if events:
            print(f"\n  Recent heal events ({len(events)} total):")
            for e in events[-5:]:
                print(f"    {e['timestamp'][:19]} | {e['project']} | {e['outcome']} | attempts={e.get('attempts', '?')}")

    print(f"\n{'='*60}\n")
