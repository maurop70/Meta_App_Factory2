"""
Auto Trigger
------------
Watches telemetry.jsonl for critical errors every 30 seconds.
When critical errors are detected, calls the Claude architect
to diagnose and post a fix proposal to Builder Chat via
/api/claudeay/diagnose — which the operator approves or dismisses.

This runs as a background thread started by loop_ui.py.
"""

import json
import time
import logging
import threading
import httpx
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("AutoTrigger")

TELEMETRY_LOG  = Path(__file__).parent / "logs" / "telemetry.jsonl"
DIAGNOSE_URL   = "http://localhost:5000/api/claudeay/diagnose"
CHECK_INTERVAL = 30  # seconds
SEEN_LOG       = Path(__file__).parent / "logs" / "seen_errors.jsonl"
SEEN_TTL_SECS  = 7 * 24 * 3600  # dedup expires after 7 days so a genuine
                                # regression of a previously-fixed error re-alerts


def _load_seen() -> dict:
    """
    Load signature → last-seen epoch, dropping entries older than the TTL.
    Accepts both the new JSON format and legacy plain-signature lines
    (legacy entries are stamped 'now' so they age out 7 days post-upgrade).
    """
    if not SEEN_LOG.exists():
        return {}
    seen: dict[str, float] = {}
    now = time.time()
    try:
        for line in SEEN_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                sig, ts = entry["sig"], float(entry["ts"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                sig, ts = line, now  # legacy format
            if now - ts < SEEN_TTL_SECS:
                seen[sig] = ts
    except Exception:
        pass
    return seen


def _mark_seen(signature: str):
    """Mark an error signature as processed (timestamped for TTL)."""
    SEEN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"sig": signature, "ts": time.time()}) + "\n")


def _error_signature(event: dict) -> str:
    """Create a dedup key from an error event."""
    return f"{event.get('type')}::{event.get('message','')[:80]}::{event.get('url','')}"


def _is_local_url(url: str) -> bool:
    """Return True for localhost/loopback URLs or events with no URL (pure JS errors)."""
    return not url or "localhost" in url or "127.0.0.1" in url or "::1" in url


def _read_recent_critical(n: int = 20) -> list:
    """Read the most recent N critical telemetry events from local origins only."""
    if not TELEMETRY_LOG.exists():
        return []
    try:
        lines = TELEMETRY_LOG.read_text(encoding="utf-8").strip().splitlines()
        events = [json.loads(l) for l in lines[-n:] if l.strip()]
        return [e for e in events if e.get("type") in
                ("console_error", "page_error", "request_failed")
                and _is_local_url(e.get("url", ""))]
    except Exception:
        return []


def _post_diagnose(errors: list):
    """Send critical errors to the diagnose endpoint for Claude to analyze."""
    try:
        payload = {
            "errors": errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "auto_trigger"
        }
        response = httpx.post(DIAGNOSE_URL, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"[AUTO-TRIGGER] Diagnosis posted for {len(errors)} errors")
        else:
            logger.warning(f"[AUTO-TRIGGER] Diagnose endpoint returned {response.status_code}")
    except Exception as e:
        logger.warning(f"[AUTO-TRIGGER] Could not post diagnose: {e}")


def watch_loop():
    """Main watch loop — runs every 30 seconds."""
    logger.info("[AUTO-TRIGGER] Watching telemetry for critical errors...")
    seen = _load_seen()

    while True:
        try:
            critical = _read_recent_critical()
            new_errors = []

            for error in critical:
                sig = _error_signature(error)
                if sig not in seen:
                    new_errors.append(error)
                    seen[sig] = time.time()
                    _mark_seen(sig)

            if new_errors:
                logger.info(f"[AUTO-TRIGGER] {len(new_errors)} new critical errors detected")
                _post_diagnose(new_errors)
            else:
                logger.debug("[AUTO-TRIGGER] No new critical errors")

        except Exception as e:
            logger.error(f"[AUTO-TRIGGER] Watch loop error: {e}")

        time.sleep(CHECK_INTERVAL)


def start_background():
    """Start the auto-trigger as a daemon background thread."""
    t = threading.Thread(target=watch_loop, daemon=True, name="AutoTrigger")
    t.start()
    logger.info("[AUTO-TRIGGER] Background watcher started (30s interval)")
    return t


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    watch_loop()
