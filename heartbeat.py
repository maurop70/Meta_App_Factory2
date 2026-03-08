"""
heartbeat.py — System Heartbeat Monitor
=========================================
Meta App Factory | Project Aether | Antigravity-AI

Pings the Factory API and UI every 5 minutes.
If either goes offline, sends a HIGH PRIORITY ntfy alert immediately.

Usage:
    python heartbeat.py              # Run forever (background service)
    python heartbeat.py --once       # Single check and exit
    python heartbeat.py --interval 60  # Custom interval in seconds
"""

import os
import sys
import time
import argparse
import httpx
from datetime import datetime

# ── Config ─────────────────────────────────────────────
MF_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(MF_ROOT, "Project_Aether"))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(MF_ROOT, ".env"))
except ImportError:
    pass

NTFY_TOPIC   = os.getenv("NTFY_TOPIC", "antigravity-security")
NTFY_SERVER  = os.getenv("NTFY_SERVER", "https://ntfy.sh")
FACTORY_URL  = os.getenv("FACTORY_URL", "http://localhost:8000")
UI_URL       = os.getenv("FACTORY_UI_URL", "http://localhost:5173")
CHECK_INTERVAL = 300   # 5 minutes
TIMEOUT        = 8.0   # seconds per request

ENDPOINTS = {
    "Meta App Factory (API)": f"{FACTORY_URL}/api/ip/status",
    "Factory UI (Frontend)":  UI_URL,
}

# ── Helpers ─────────────────────────────────────────────

def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

def check_endpoint(name: str, url: str) -> tuple[bool, int | None]:
    """Returns (is_online, http_status_or_None)."""
    try:
        r = httpx.get(url, timeout=TIMEOUT, follow_redirects=True)
        return r.status_code < 500, r.status_code
    except (httpx.ConnectError, httpx.TimeoutException):
        return False, None
    except Exception:
        return False, None

def send_alert(name: str, url: str):
    """Send HIGH PRIORITY ntfy push for offline service."""
    sop_url = f"{UI_URL}/?view=sop&app=Heartbeat&score=0"
    try:
        httpx.post(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            content=f"SYSTEM CRITICAL: {name} is OFFLINE. URL: {url}".encode("utf-8"),
            headers={
                "Title": f"SYSTEM CRITICAL: {name} OFFLINE",
                "Priority": "5",
                "Tags": "warning,rotating_light",
                "Click": sop_url,
            },
            timeout=10.0,
        )
        print(f"[{timestamp()}] [ALERT SENT] {name} offline → ntfy push fired")
    except Exception as e:
        print(f"[{timestamp()}] [WARN] Could not send ntfy alert: {e}")

# ── Core Check Loop ─────────────────────────────────────

# Track which services were already alerted (don't spam)
_alerted: dict = {}

def run_check():
    """Run one full health check across all endpoints."""
    all_ok = True
    for name, url in ENDPOINTS.items():
        online, code = check_endpoint(name, url)
        status = f"ONLINE (HTTP {code})" if online else "OFFLINE"
        print(f"[{timestamp()}] {name:.<40} {status}")

        if not online:
            all_ok = False
            if not _alerted.get(name):
                send_alert(name, url)
                _alerted[name] = True
        else:
            # Clear alert flag once service recovers
            if _alerted.get(name):
                print(f"[{timestamp()}] [RECOVERY] {name} is back online")
                _alerted[name] = False

    return all_ok

# ── Entry Point ─────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aether Heartbeat Monitor")
    parser.add_argument("--once", action="store_true",
                        help="Run a single check and exit")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL,
                        help=f"Check interval in seconds (default: {CHECK_INTERVAL})")
    args = parser.parse_args()

    print(f"[{timestamp()}] Heartbeat Monitor starting")
    print(f"   Factory API : {FACTORY_URL}")
    print(f"   Factory UI  : {UI_URL}")
    print(f"   ntfy topic  : {NTFY_TOPIC}")
    print(f"   Interval    : {args.interval}s")
    print("-" * 55)

    if args.once:
        ok = run_check()
        sys.exit(0 if ok else 1)

    while True:
        try:
            run_check()
        except KeyboardInterrupt:
            print(f"\n[{timestamp()}] Heartbeat Monitor stopped.")
            sys.exit(0)
        except Exception as e:
            print(f"[{timestamp()}] [ERROR] Unexpected error: {e}")
        print(f"[{timestamp()}] Next check in {args.interval}s...\n")
        time.sleep(args.interval)
