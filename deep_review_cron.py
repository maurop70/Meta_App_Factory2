from auto_heal import healed_post, auto_heal, diagnose

"""
deep_review_cron.py — Leitner Deep Review Daemon
═════════════════════════════════════════════════
Meta App Factory | Aether Protocol | Antigravity-AI

Runs every 72 hours (or on-demand via --once). Loads Level 4-5 errors
from MASTER_INDEX.md ERROR_REGISTRY, cross-references against current
app builds via the Specialist — Architect, and issues System Warnings
to the Command Center if regression patterns are detected.

Usage:
    python deep_review_cron.py              # Run forever (72h cycle)
    python deep_review_cron.py --once       # Single review and exit
    python deep_review_cron.py --interval 3600  # Custom interval (seconds)
    python deep_review_cron.py --min-level 3    # Include Level 3+ errors
"""

import os
import sys
import time
import json
import logging
import argparse
import re
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DeepReview] %(message)s",
)
logger = logging.getLogger("DeepReview")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

MASTER_INDEX_PATH = os.path.join(SCRIPT_DIR, "MASTER_INDEX.md")
STATE_DIR = os.path.join(SCRIPT_DIR, ".Gemini_state")
REVIEW_LOG_PATH = os.path.join(STATE_DIR, "deep_review_log.json")

# Default: 72 hours in seconds
DEFAULT_INTERVAL = 72 * 60 * 60  # 259200 seconds


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def run_review(min_level: int = 4) -> dict:
    """
    Execute a single Leitner Deep Review cycle.
    Returns a summary dict with results.
    """
    print(f"\n{'='*60}")
    print(f"[{timestamp()}] LEITNER DEEP REVIEW — Cycle Start")
    print(f"{'='*60}")

    try:
        from leitner_architect import LeitnerArchitect
        architect = LeitnerArchitect()
    except ImportError as e:
        logger.error(f"Could not import LeitnerArchitect: {e}")
        return {"status": "error", "message": str(e)}

    # Phase 1: Load high-complexity errors
    high_errors = architect.get_high_complexity_errors(min_level)
    print(f"[{timestamp()}] Phase 1: Found {len(high_errors)} error(s) at Level {min_level}+")

    if not high_errors:
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "clean",
            "errors_reviewed": 0,
            "warnings_issued": 0,
            "message": f"No Level {min_level}+ errors in ERROR_REGISTRY.",
        }
        _log_review(summary)
        print(f"[{timestamp()}] ✅ No high-complexity errors to review.")
        return summary

    # Phase 2: Run deep review (cross-reference against all active apps)
    print(f"[{timestamp()}] Phase 2: Cross-referencing against active app builds...")
    warnings = architect.run_deep_review(min_level)

    # Phase 3: Report results
    print(f"\n[{timestamp()}] Phase 3: Review Complete")
    print(f"  Errors reviewed:  {len(high_errors)}")
    print(f"  Warnings issued:  {len(warnings)}")

    if warnings:
        print(f"\n  ⚠️  SYSTEM WARNINGS:")
        for w in warnings:
            print(f"    [{w.get('severity', '?')}] {w.get('reviewed_app', '?')}: "
                  f"{w.get('recommendation', '')[:100]}")

        # Attempt to notify Command Center
        _notify_command_center(warnings)
    else:
        print(f"  ✅ No regression patterns detected across active builds.")

    # Phase 4: Update last_reviewed timestamps in MASTER_INDEX
    _update_last_reviewed(high_errors)

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "warnings_issued" if warnings else "clean",
        "errors_reviewed": len(high_errors),
        "warnings_issued": len(warnings),
        "warning_details": [
            {
                "app": w.get("reviewed_app"),
                "severity": w.get("severity"),
                "matches": len(w.get("matches", [])),
            }
            for w in warnings
        ],
    }
    _log_review(summary)
    return summary


def _notify_command_center(warnings: list) -> None:
    """Try to POST warnings to the Command Center API."""
    try:
        url = "http://localhost:5010/api/warnings/ingest"
        _v3_status = healed_post(url, {"warnings": warnings})

        resp = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
        if resp.status_code == 200:
            print(f"[{timestamp()}] 📡 Command Center notified ({len(warnings)} warnings)")
        else:
            print(f"[{timestamp()}] ⚠️ Command Center returned {resp.status_code}")
    except Exception:
        # Command Center may not be running — that's fine
        print(f"[{timestamp()}] 📋 Warnings saved to .Gemini_state (Command Center offline)")


def _update_last_reviewed(errors: list) -> None:
    """Update the last_reviewed timestamps in MASTER_INDEX for reviewed errors."""
    if not os.path.isfile(MASTER_INDEX_PATH):
        return

    try:
        with open(MASTER_INDEX_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # Find all ERROR_ENTRY blocks and update last_reviewed
        for error in errors:
            ts = error.get("timestamp", "")
            if ts and ts in content:
                # Update or add last_reviewed line near this error's timestamp
                pattern = (
                    rf"(### ERROR_ENTRY\s*\n(?:.*?\n)*?"
                    rf"- \*\*Timestamp:\*\* {re.escape(ts)}"
                    rf"(?:.*?\n)*?)"
                    rf"(- \*\*Last_Reviewed:\*\*.*?\n|(?=### ERROR_ENTRY|\n## |$))"
                )
                replacement_line = f"- **Last_Reviewed:** {now}\n"
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    # Check if last_reviewed already exists
                    if "Last_Reviewed:" in match.group(2):
                        content = content.replace(match.group(2), replacement_line)
                    else:
                        # Insert before the next entry
                        insert_point = match.end(1)
                        content = content[:insert_point] + replacement_line + content[insert_point:]

        with open(MASTER_INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

    except Exception as e:
        logger.warning(f"Could not update last_reviewed in MASTER_INDEX: {e}")


def _log_review(summary: dict) -> None:
    """Append the review summary to the deep review log."""
    os.makedirs(STATE_DIR, exist_ok=True)
    log = []
    if os.path.isfile(REVIEW_LOG_PATH):
        try:
            with open(REVIEW_LOG_PATH, "r", encoding="utf-8") as f:
                log = json.load(f)
        except (json.JSONDecodeError, Exception):
            log = []

    log.append(summary)

    # Keep last 100 entries
    log = log[-100:]

    try:
        with open(REVIEW_LOG_PATH, "w", encoding="utf-8", newline="\n") as f:
            json.dump(log, f, indent=2)
    except Exception as e:
        logger.error(f"Could not write review log: {e}")


# ── Entry Point ──────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Leitner Deep Review Daemon")
    parser.add_argument("--once", action="store_true",
                        help="Run a single review cycle and exit")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                        help=f"Review interval in seconds (default: {DEFAULT_INTERVAL} = 72h)")
    parser.add_argument("--min-level", type=int, default=4,
                        help="Minimum error complexity level to review (default: 4)")
    args = parser.parse_args()

    print(f"[{timestamp()}] Leitner Deep Review Daemon starting")
    print(f"   Interval    : {args.interval}s ({args.interval/3600:.1f}h)")
    print(f"   Min Level   : {args.min_level}")
    print(f"   Master Index: {MASTER_INDEX_PATH}")
    print("-" * 60)

    if args.once:
        result = run_review(args.min_level)
        status = result.get("status", "unknown")
        sys.exit(0 if status in ("clean", "warnings_issued") else 1)

    while True:
        try:
            run_review(args.min_level)
        except KeyboardInterrupt:
            print(f"\n[{timestamp()}] Deep Review Daemon stopped.")
            sys.exit(0)
        except Exception as e:
            print(f"[{timestamp()}] [ERROR] Unexpected error: {e}")
        print(f"\n[{timestamp()}] Next deep review in {args.interval}s "
              f"({args.interval/3600:.1f}h)...\n")
        time.sleep(args.interval)

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
