from auto_heal import healed_post, auto_heal, diagnose

"""
visual_map_cron.py — Visual Mapping Sunday Daemon
══════════════════════════════════════════════════
Meta App Factory | Aether Protocol | Antigravity-AI

Runs every Sunday (or on-demand via --once). Generates a Mermaid.js
network diagram of the agent ecosystem, highlights Orphaned and
Bottleneck agents, and saves to data/network_maps/.

Usage:
    python visual_map_cron.py              # Run forever (checks daily, acts Sunday)
    python visual_map_cron.py --once       # Generate diagram now and exit
    python visual_map_cron.py --interval 3600  # Custom check interval (seconds)
"""

import os
import sys
import time
import json
import logging
import argparse
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [VisualMap] %(message)s",
)
logger = logging.getLogger("VisualMap")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# Default: check every 6 hours (runs diagram only on Sunday)
DEFAULT_INTERVAL = 6 * 60 * 60  # 21600 seconds


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def is_sunday() -> bool:
    """Check if today is Sunday (weekday 6)."""
    return datetime.now().weekday() == 6


def run_mapping(force: bool = False) -> dict:
    """
    Execute a single Visual Mapping cycle.
    Only generates on Sunday unless force=True.
    """
    if not force and not is_sunday():
        day_name = datetime.now().strftime("%A")
        print(f"[{timestamp()}] Today is {day_name} — skipping (runs on Sunday).")
        return {"status": "skipped", "reason": f"Not Sunday (is {day_name})"}

    print(f"\n{'='*60}")
    print(f"[{timestamp()}] VISUAL MAPPING PROTOCOL — Generation Start")
    print(f"{'='*60}")

    try:
        from network_mapper import NetworkMapper
        mapper = NetworkMapper()
    except ImportError as e:
        logger.error(f"Could not import NetworkMapper: {e}")
        return {"status": "error", "message": str(e)}

    # Phase 1: Scan
    print(f"[{timestamp()}] Phase 1: Scanning agent network...")
    summary = mapper.scan_network()
    print(f"  Apps:        {summary['apps']}")
    print(f"  Agents:      {summary['agents']}")
    print(f"  Connections: {summary['connections']}")
    print(f"  Orphaned:    {summary['orphaned']}")
    print(f"  Bottleneck:  {summary['bottleneck']}")

    # Phase 2: Generate
    print(f"[{timestamp()}] Phase 2: Generating Mermaid diagram...")
    mermaid = mapper.generate_mermaid()
    report = mapper.generate_load_report()

    # Phase 3: Save
    print(f"[{timestamp()}] Phase 3: Saving to data/network_maps/...")
    md_path, json_path = mapper.save_diagram(mermaid, report)
    print(f"  Diagram: {md_path}")
    print(f"  Report:  {json_path}")

    # Phase 4: Notify Command Center
    _notify_command_center(report)

    result = {
        "status": "generated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "diagram_path": md_path,
        "report_path": json_path,
        **summary,
    }
    print(f"\n[{timestamp()}] ✅ Visual map generation complete.")
    return result


def _notify_command_center(report: dict) -> None:
    """Try to push the load report to the Command Center."""
    try:
        url = "http://localhost:5010/api/network-map/ingest"
        _v3_status = healed_post(url, report)

        resp = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
        if resp.status_code == 200:
            print(f"[{timestamp()}] 📡 Command Center updated with network map")
        else:
            print(f"[{timestamp()}] ⚠️ Command Center returned {resp.status_code}")
    except Exception:
        print(f"[{timestamp()}] 📋 Report saved locally (Command Center offline)")


# ── Entry Point ──────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visual Mapping Sunday Daemon")
    parser.add_argument("--once", action="store_true",
                        help="Generate diagram now (regardless of day) and exit")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                        help=f"Check interval in seconds (default: {DEFAULT_INTERVAL})")
    args = parser.parse_args()

    print(f"[{timestamp()}] Visual Map Daemon starting")
    print(f"   Interval : {args.interval}s ({args.interval/3600:.1f}h)")
    print(f"   Schedule : Every Sunday (or --once for immediate)")
    print("-" * 60)

    if args.once:
        result = run_mapping(force=True)
        sys.exit(0 if result.get("status") != "error" else 1)

    while True:
        try:
            run_mapping(force=False)
        except KeyboardInterrupt:
            print(f"\n[{timestamp()}] Visual Map Daemon stopped.")
            sys.exit(0)
        except Exception as e:
            print(f"[{timestamp()}] [ERROR] Unexpected error: {e}")
        print(f"\n[{timestamp()}] Next check in {args.interval}s "
              f"({args.interval/3600:.1f}h)...\n")
        time.sleep(args.interval)

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
