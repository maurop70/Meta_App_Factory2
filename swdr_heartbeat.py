"""
swdr_heartbeat.py — SWDR Credential Sentinel Heartbeat
═══════════════════════════════════════════════════════════
Runs `factory.py swdr` diagnostics every 15 minutes as a live
heartbeat monitor. On failure, fires an ntfy HIGH PRIORITY alert.

Usage:
    python swdr_heartbeat.py              # Run forever (15-min interval)
    python swdr_heartbeat.py --once       # Single check and exit
    python swdr_heartbeat.py --interval 60  # Custom interval in seconds

Part of SWDR v2.1 — Aether Self-Healing Protocol.
"""

import os
import sys
import time
import json
import argparse
import subprocess
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Config ─────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_PY = os.path.join(SCRIPT_DIR, "factory.py")
CHECK_INTERVAL = 60  # 60 seconds (Hardening V3 Sealed)

# Stability modules
sys.path.insert(0, os.path.join(SCRIPT_DIR, "Resonance2"))
sys.path.insert(0, SCRIPT_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
except ImportError:
    pass

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "antigravity-security")
NTFY_SERVER = os.getenv("NTFY_SERVER", "https://ntfy.sh")

# Log file for heartbeat results
HEARTBEAT_LOG = os.path.join(
    os.path.expanduser("~"), ".antigravity", "swdr_heartbeat.jsonl"
)
os.makedirs(os.path.dirname(HEARTBEAT_LOG), exist_ok=True)


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def run_swdr_check() -> dict:
    """Run `python factory.py swdr` and capture output."""
    result = {
        "timestamp": datetime.now().isoformat(),
        "status": "unknown",
        "output": "",
        "has_open_circuits": False,
        "credential_status": "unknown",
    }

    try:
        proc = subprocess.run(
            [sys.executable, FACTORY_PY, "swdr"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=30, cwd=SCRIPT_DIR,
        )
        result["output"] = proc.stdout
        result["exit_code"] = proc.returncode

        # Parse output for key indicators
        output = proc.stdout

        if "VALID" in output:
            result["credential_status"] = "VALID"
        elif "EXPIRED" in output or "NOT SET" in output:
            result["credential_status"] = "FAILED"
        elif "Connection Failed" in output:
            result["credential_status"] = "UNREACHABLE"

        if "OPEN" in output and "Circuit" in output.split("OPEN")[0][-50:]:
            result["has_open_circuits"] = True

        result["status"] = "healthy" if proc.returncode == 0 else "degraded"

    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
        result["output"] = "SWDR check timed out after 30s"
    except Exception as e:
        result["status"] = "error"
        result["output"] = str(e)

    return result


def log_result(result: dict):
    """Append result to JSONL log."""
    try:
        with open(HEARTBEAT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, default=str) + "\n")
    except Exception:
        pass


def send_alert(message: str, priority: str = "4"):
    """Send ntfy push notification."""
    try:
        import httpx
        httpx.post(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            content=message.encode("utf-8"),
            headers={
                "Title": "SWDR HEARTBEAT ALERT",
                "Priority": priority,
                "Tags": "warning,rotating_light",
            },
            timeout=10.0,
        )
        print(f"[{timestamp()}] [ALERT SENT] {message[:80]}")
    except ImportError:
        # httpx not installed — try requests
        try:
            import requests
            requests.post(
                f"{NTFY_SERVER}/{NTFY_TOPIC}",
                data=message.encode("utf-8"),
                headers={
                    "Title": "SWDR HEARTBEAT ALERT",
                    "Priority": priority,
                    "Tags": "warning,rotating_light",
                },
                timeout=10.0,
            )
            print(f"[{timestamp()}] [ALERT SENT] {message[:80]}")
        except Exception as e:
            print(f"[{timestamp()}] [WARN] Alert send failed: {e}")
    except Exception as e:
        print(f"[{timestamp()}] [WARN] Alert send failed: {e}")


# Track alert state to prevent spam
_last_alert_status = None


def run_check():
    """Execute a full SWDR heartbeat check."""
    global _last_alert_status

    # ── Primary Health Check: Watchdog Ping (Hardening V3 Sealed) ──
    _watchdog_ok = False
    try:
        import requests as _req
        _rc_path = os.path.join(SCRIPT_DIR, "resilience_config.json")
        if os.path.exists(_rc_path):
            with open(_rc_path) as _f:
                _rc = json.load(_f)
            _wdog_url = _rc.get("cloud_health", {}).get("watchdog_url", "")
            if _wdog_url:
                _start = time.time()
                try:
                    _r = _req.get(_wdog_url, timeout=5)
                    _ms = (time.time() - _start) * 1000
                    _watchdog_ok = _r.status_code == 200
                    print(f"[{timestamp()}] Watchdog Ping:       {'🟢' if _watchdog_ok else '🟡'} {_r.status_code} ({_ms:.0f}ms)")
                    if _ms > 3000:
                        _watchdog_ok = False
                        print(f"[{timestamp()}] ⚠️ Cloud latency {_ms:.0f}ms > 3000ms threshold")
                except Exception as _e:
                    print(f"[{timestamp()}] Watchdog Ping:       🔴 UNREACHABLE ({_e})")
    except Exception:
        pass

    # ── Safe-Buffer Mode Toggle ──────────────────────────────
    try:
        sys.path.insert(0, SCRIPT_DIR)
        from local_state_manager import StateManager
        _sm = StateManager()
        if not _watchdog_ok and not _sm.is_safe_buffer_mode():
            _sm.set_safe_buffer_mode(True)
            print(f"[{timestamp()}] 🛡️ SAFE-BUFFER MODE: ENABLED (watchdog unreachable)")
            send_alert("Safe-Buffer mode ENABLED — cloud unreachable, factory.py writing locally", priority="5")
        elif _watchdog_ok and _sm.is_safe_buffer_mode():
            _sm.set_safe_buffer_mode(False)
            print(f"[{timestamp()}] ✅ SAFE-BUFFER MODE: DISABLED (cloud recovered)")
    except ImportError:
        pass
    # ── End Watchdog / Safe-Buffer ────────────────────────────

    print(f"[{timestamp()}] Running SWDR diagnostic...")
    result = run_swdr_check()
    log_result(result)

    # Display summary
    cred_icon = {"VALID": "🟢", "FAILED": "🔴", "UNREACHABLE": "🔴"}.get(
        result["credential_status"], "🟡"
    )
    circuit_icon = "🔴" if result["has_open_circuits"] else "🟢"

    print(f"[{timestamp()}] Credential Sentinel: {cred_icon} {result['credential_status']}")
    print(f"[{timestamp()}] Circuit Breakers:    {circuit_icon} {'OPEN detected' if result['has_open_circuits'] else 'All CLOSED'}")
    print(f"[{timestamp()}] Overall Status:      {result['status']}")

    # Alert logic — only fire on state change to prevent spam
    needs_alert = (
        result["credential_status"] == "FAILED"
        or result["has_open_circuits"]
        or result["status"] in ("error", "timeout")
    )

    if needs_alert and _last_alert_status != "alerted":
        msg = (
            f"SWDR Heartbeat CRITICAL: "
            f"Credentials={result['credential_status']}, "
            f"OpenCircuits={result['has_open_circuits']}, "
            f"Status={result['status']}"
        )
        send_alert(msg, priority="5")
        _last_alert_status = "alerted"
    elif not needs_alert:
        if _last_alert_status == "alerted":
            print(f"[{timestamp()}] [RECOVERY] System has recovered")
        _last_alert_status = "ok"

    return result


# ── Entry Point ─────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SWDR Credential Sentinel Heartbeat")
    parser.add_argument("--once", action="store_true", help="Run a single check and exit")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL,
                        help=f"Check interval in seconds (default: {CHECK_INTERVAL}s = 15 min)")
    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print(f"  🫀 SWDR Heartbeat Monitor v2.1")
    print(f"  Interval: {args.interval}s ({args.interval // 60}min)")
    print(f"  ntfy topic: {NTFY_TOPIC}")
    print(f"  Log: {HEARTBEAT_LOG}")
    print(f"{'=' * 60}\n")

    if args.once:
        result = run_check()
        sys.exit(0 if result["status"] == "healthy" else 1)

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
