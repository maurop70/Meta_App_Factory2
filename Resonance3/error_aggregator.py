"""
Antigravity Error Aggregator — Centralized error logging across all apps.
Usage:
    from error_aggregator import ErrorAggregator
    logger = ErrorAggregator("AlphaV2")
    logger.log_error("N8N timeout", context={"workflow": "Genesis v3"})
    logger.log_warning("High latency detected")
    
    # View recent errors
    python error_aggregator.py                # Show last 20 errors
    python error_aggregator.py --app AlphaV2  # Filter by app
    python error_aggregator.py --severity error  # Filter by severity
"""
import os, sys, json, traceback
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Shared log file — all apps write here
DEFAULT_LOG_DIR = os.path.join(os.path.expanduser("~"), ".antigravity")
ERROR_LOG_PATH = os.path.join(DEFAULT_LOG_DIR, "error_log.jsonl")
MAX_LOG_SIZE_MB = 10  # Rotate at 10MB


class ErrorAggregator:
    """Centralized error logger for Antigravity apps."""

    def __init__(self, app_name="Unknown", log_path=None):
        self.app_name = app_name
        self.log_path = log_path or ERROR_LOG_PATH
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def _write_entry(self, severity, message, context=None, exc_info=None):
        """Write a single log entry as JSONL."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "app": self.app_name,
            "severity": severity,
            "message": message,
        }
        if context:
            entry["context"] = context
        if exc_info:
            entry["traceback"] = traceback.format_exception(
                type(exc_info), exc_info, exc_info.__traceback__
            )

        # Rotate if file too large
        try:
            if os.path.exists(self.log_path):
                size_mb = os.path.getsize(self.log_path) / (1024 * 1024)
                if size_mb > MAX_LOG_SIZE_MB:
                    rotated = self.log_path + ".old"
                    if os.path.exists(rotated):
                        os.remove(rotated)
                    os.rename(self.log_path, rotated)
        except Exception:
            pass

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception:
            pass  # Never crash the app due to logging

    def log_error(self, message, context=None, exc=None):
        """Log an error."""
        self._write_entry("error", message, context, exc)

    def log_warning(self, message, context=None):
        """Log a warning."""
        self._write_entry("warning", message, context)

    def log_info(self, message, context=None):
        """Log an info message."""
        self._write_entry("info", message, context)

    def log_critical(self, message, context=None, exc=None):
        """Log a critical error."""
        self._write_entry("critical", message, context, exc)

    @staticmethod
    def read_recent(n=20, app_filter=None, severity_filter=None, log_path=None):
        """Read the most recent N entries from the log."""
        path = log_path or ERROR_LOG_PATH
        if not os.path.exists(path):
            return []

        entries = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if app_filter and entry.get("app") != app_filter:
                            continue
                        if severity_filter and entry.get("severity") != severity_filter:
                            continue
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        return entries[-n:]  # Return last N

    @staticmethod
    def get_summary(log_path=None):
        """Get error count summary by app and severity."""
        path = log_path or ERROR_LOG_PATH
        if not os.path.exists(path):
            return {"total": 0, "by_app": {}, "by_severity": {}}

        by_app = {}
        by_severity = {}
        total = 0

        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        total += 1
                        app = entry.get("app", "Unknown")
                        sev = entry.get("severity", "unknown")
                        by_app[app] = by_app.get(app, 0) + 1
                        by_severity[sev] = by_severity.get(sev, 0) + 1
                    except Exception:
                        continue
        except Exception:
            pass

        return {"total": total, "by_app": by_app, "by_severity": by_severity}


def print_recent(entries):
    """Pretty-print recent error entries."""
    icons = {"error": "❌", "warning": "⚠️ ", "info": "ℹ️ ", "critical": "🚨"}

    if not entries:
        print("  No entries found.")
        return

    for e in entries:
        ts = e.get("timestamp", "")[:19]
        app = e.get("app", "?")
        sev = e.get("severity", "?")
        msg = e.get("message", "")
        icon = icons.get(sev, "❓")
        print(f"  {icon} [{ts}] {app}: {msg}")
        if e.get("context"):
            print(f"       Context: {json.dumps(e['context'])}")


# ── CLI ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Antigravity Error Aggregator")
    parser.add_argument("--app", default=None, help="Filter by app name")
    parser.add_argument("--severity", default=None, choices=["error", "warning", "info", "critical"])
    parser.add_argument("-n", type=int, default=20, help="Number of entries to show")
    parser.add_argument("--summary", action="store_true", help="Show summary only")
    args = parser.parse_args()

    print(f"\n{'='*55}")
    print(f"  ANTIGRAVITY ERROR LOG")
    print(f"{'='*55}\n")

    if args.summary:
        s = ErrorAggregator.get_summary()
        print(f"  Total entries: {s['total']}")
        print(f"  By app: {json.dumps(s['by_app'], indent=4)}")
        print(f"  By severity: {json.dumps(s['by_severity'], indent=4)}")
    else:
        entries = ErrorAggregator.read_recent(args.n, args.app, args.severity)
        print_recent(entries)

    print(f"\n{'='*55}\n")
