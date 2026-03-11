"""
fiscal_oversight.py — Budget Monitor & Threshold Alerting
==========================================================
Project Aether | CFO Agent Module

Monitors resource usage on Sentry and GitHub Actions against the
$10 "Developer" budget threshold. Pings the Aether Master Dashboard
(via Boardroom log) when costs exceed limits.

Architecture:
    CHECK  → Poll Sentry/GitHub APIs for billing data
    EVAL   → Compare against $10 Developer threshold
    ALERT  → Write alert to Boardroom feed + log file
    REPORT → Return status for dashboard consumption

Usage:
    python fiscal_oversight.py check       # One-shot check
    python fiscal_oversight.py status      # Current budget status
    python fiscal_oversight.py daemon 600  # Check every 10 min
"""

import os
import sys
import json
import time
import requests
import logging
from datetime import datetime
from typing import Dict, Optional, List

# Force UTF-8 on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

logger = logging.getLogger("FiscalOversight")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AETHER_DIR = SCRIPT_DIR
BOARDROOM_DIR = os.path.join(AETHER_DIR, "Boardroom")
ALERT_LOG = os.path.join(AETHER_DIR, "fiscal_alerts.json")
STATE_FILE = os.path.join(
    os.path.expanduser("~"), ".antigravity", "fiscal_state.json"
)
os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
os.makedirs(BOARDROOM_DIR, exist_ok=True)

# ── Budget Configuration ──────────────────────────────────

BUDGET_CONFIG = {
    "developer_threshold_usd": 10.00,
    "warning_pct": 0.75,       # Alert at 75% of threshold
    "critical_pct": 0.90,      # Critical alert at 90%
    "services": {
        "sentry": {
            "name": "Sentry (Error Tracking)",
            "free_tier_events": 5000,    # Free tier: 5K events/month
            "cost_per_extra_event": 0.000265,  # ~$26.50/100K events
        },
        "github_actions": {
            "name": "GitHub Actions",
            "free_tier_minutes": 2000,   # Free tier: 2K min/month
            "cost_per_extra_minute": 0.008,    # $0.008/min (Linux)
        },
        "n8n_cloud": {
            "name": "n8n Cloud (Pro)",
            "fixed_monthly": 20.00,
        },
    },
}


# ── API Polling ───────────────────────────────────────────

def _get_env_key(key: str) -> str:
    """Get API key from env or .env file."""
    val = os.getenv(key, "")
    if val:
        return val
    # Try .env files
    for env_path in [
        os.path.join(AETHER_DIR, ".env"),
        os.path.join(AETHER_DIR, "..", ".env"),
    ]:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith(f"{key}="):
                        return line.strip().split("=", 1)[1]
    return ""


def check_sentry_usage() -> Dict:
    """
    Poll Sentry API for current event counts.
    Returns: {events_used, events_limit, estimated_cost, status}
    """
    token = _get_env_key("SENTRY_AUTH_TOKEN")
    org_slug = _get_env_key("SENTRY_ORG") or "antigravity"

    if not token:
        # Return stub data when no API token is available
        return {
            "service": "sentry",
            "name": "Sentry (Error Tracking)",
            "events_used": 0,
            "events_limit": BUDGET_CONFIG["services"]["sentry"]["free_tier_events"],
            "estimated_cost": 0.00,
            "status": "no_token",
            "message": "SENTRY_AUTH_TOKEN not configured — using stub data",
        }

    try:
        # Sentry Stats API (v0)
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://sentry.io/api/0/organizations/{org_slug}/stats_v2/"
        params = {
            "field": "sum(quantity)",
            "category": "error",
            "interval": "1d",
            "statsPeriod": "30d",
        }
        resp = requests.get(url, headers=headers, params=params, timeout=15)

        if resp.status_code == 200:
            data = resp.json()
            # Sum all intervals
            total_events = 0
            for group in data.get("groups", []):
                for series_vals in group.get("series", {}).values():
                    total_events += sum(series_vals)

            free_tier = BUDGET_CONFIG["services"]["sentry"]["free_tier_events"]
            extra = max(0, total_events - free_tier)
            cost = extra * BUDGET_CONFIG["services"]["sentry"]["cost_per_extra_event"]

            return {
                "service": "sentry",
                "name": "Sentry (Error Tracking)",
                "events_used": total_events,
                "events_limit": free_tier,
                "estimated_cost": round(cost, 2),
                "status": "ok",
            }
        else:
            return {
                "service": "sentry",
                "name": "Sentry (Error Tracking)",
                "events_used": 0,
                "estimated_cost": 0.00,
                "status": "api_error",
                "message": f"HTTP {resp.status_code}",
            }
    except Exception as e:
        return {
            "service": "sentry",
            "name": "Sentry (Error Tracking)",
            "events_used": 0,
            "estimated_cost": 0.00,
            "status": "error",
            "message": str(e),
        }


def check_github_actions_usage() -> Dict:
    """
    Poll GitHub Actions API for billing minutes.
    Returns: {minutes_used, minutes_limit, estimated_cost, status}
    """
    token = _get_env_key("GITHUB_TOKEN")

    if not token:
        return {
            "service": "github_actions",
            "name": "GitHub Actions",
            "minutes_used": 0,
            "minutes_limit": BUDGET_CONFIG["services"]["github_actions"]["free_tier_minutes"],
            "estimated_cost": 0.00,
            "status": "no_token",
            "message": "GITHUB_TOKEN not configured — using stub data",
        }

    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        # Get authenticated user's billing
        url = "https://api.github.com/user"
        user_resp = requests.get(url, headers=headers, timeout=10)

        if user_resp.status_code != 200:
            return {
                "service": "github_actions",
                "name": "GitHub Actions",
                "minutes_used": 0,
                "estimated_cost": 0.00,
                "status": "api_error",
                "message": f"User API: HTTP {user_resp.status_code}",
            }

        username = user_resp.json().get("login", "")

        # Get billing data
        billing_url = f"https://api.github.com/users/{username}/settings/billing/actions"
        bill_resp = requests.get(billing_url, headers=headers, timeout=10)

        if bill_resp.status_code == 200:
            data = bill_resp.json()
            total_min = data.get("total_minutes_used", 0)
            included_min = data.get("included_minutes", 2000)
            extra = max(0, total_min - included_min)
            cost = extra * BUDGET_CONFIG["services"]["github_actions"]["cost_per_extra_minute"]

            return {
                "service": "github_actions",
                "name": "GitHub Actions",
                "minutes_used": total_min,
                "minutes_limit": included_min,
                "estimated_cost": round(cost, 2),
                "status": "ok",
            }
        else:
            return {
                "service": "github_actions",
                "name": "GitHub Actions",
                "minutes_used": 0,
                "estimated_cost": 0.00,
                "status": "api_error",
                "message": f"Billing API: HTTP {bill_resp.status_code}",
            }
    except Exception as e:
        return {
            "service": "github_actions",
            "name": "GitHub Actions",
            "minutes_used": 0,
            "estimated_cost": 0.00,
            "status": "error",
            "message": str(e),
        }


# ── Budget Evaluation ─────────────────────────────────────

class FiscalOversight:
    """
    Budget monitor that checks resource costs against the $10 Developer threshold.
    Alerts the Aether Master Dashboard when limits are approached or exceeded.
    """

    def __init__(self):
        self.threshold = BUDGET_CONFIG["developer_threshold_usd"]
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "last_check": None,
            "total_checks": 0,
            "alerts_sent": 0,
            "current_total_cost": 0.0,
            "service_costs": {},
        }

    def _save_state(self):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save fiscal state: {e}")

    def evaluate_threshold(self, service_name: str, cost: float) -> Dict:
        """
        Evaluate a service's cost against the budget threshold.
        Returns: {level, message, pct_of_budget}
        """
        pct = (cost / self.threshold * 100) if self.threshold > 0 else 0

        if cost >= self.threshold:
            return {
                "level": "CRITICAL",
                "message": f"🔴 {service_name}: ${cost:.2f} EXCEEDS ${self.threshold:.2f} threshold!",
                "pct_of_budget": round(pct, 1),
            }
        elif cost >= self.threshold * BUDGET_CONFIG["critical_pct"]:
            return {
                "level": "WARNING",
                "message": f"🟡 {service_name}: ${cost:.2f} at {pct:.0f}% of ${self.threshold:.2f} threshold",
                "pct_of_budget": round(pct, 1),
            }
        elif cost >= self.threshold * BUDGET_CONFIG["warning_pct"]:
            return {
                "level": "CAUTION",
                "message": f"🟠 {service_name}: ${cost:.2f} approaching ${self.threshold:.2f} threshold ({pct:.0f}%)",
                "pct_of_budget": round(pct, 1),
            }
        else:
            return {
                "level": "OK",
                "message": f"🟢 {service_name}: ${cost:.2f} ({pct:.0f}% of budget)",
                "pct_of_budget": round(pct, 1),
            }

    def alert_dashboard(self, alerts: List[Dict]):
        """
        Write budget alerts to the Boardroom feed.
        The dashboard_generator.gs autoRefresh() picks these up.
        """
        if not alerts:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Write to Boardroom alert file
        alert_file = os.path.join(BOARDROOM_DIR, "fiscal_alerts.md")
        alert_lines = [
            f"\n## FISCAL ALERT — {timestamp}",
            f"- **Threshold:** ${self.threshold:.2f} (Developer Plan)",
        ]
        for alert in alerts:
            alert_lines.append(f"- {alert['message']}")
        alert_lines.append("")

        try:
            with open(alert_file, "a", encoding="utf-8") as f:
                f.write("\n".join(alert_lines))
            logger.info(f"Budget alert written to Boardroom: {len(alerts)} alert(s)")
        except Exception as e:
            logger.error(f"Failed to write Boardroom alert: {e}")

        # Also append to JSON log
        try:
            existing = []
            if os.path.exists(ALERT_LOG):
                with open(ALERT_LOG, "r", encoding="utf-8") as f:
                    existing = json.load(f)

            existing.append({
                "timestamp": timestamp,
                "threshold": self.threshold,
                "alerts": alerts,
            })
            # Keep last 100 entries
            existing = existing[-100:]

            with open(ALERT_LOG, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to write alert log: {e}")

        self.state["alerts_sent"] = self.state.get("alerts_sent", 0) + len(alerts)

    def run_check(self) -> Dict:
        """
        Full fiscal check cycle: CHECK → EVALUATE → ALERT → REPORT.
        """
        print(f"\n{'═'*55}")
        print(f"  💰 FISCAL OVERSIGHT — Budget Check")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Threshold: ${self.threshold:.2f} (Developer Plan)")
        print(f"{'═'*55}\n")

        # CHECK: Poll all services
        service_reports = []
        service_reports.append(check_sentry_usage())
        service_reports.append(check_github_actions_usage())

        # Add fixed costs
        n8n_cost = BUDGET_CONFIG["services"]["n8n_cloud"]["fixed_monthly"]
        service_reports.append({
            "service": "n8n_cloud",
            "name": "n8n Cloud (Pro)",
            "estimated_cost": n8n_cost,
            "status": "fixed",
            "message": f"Fixed monthly: ${n8n_cost:.2f}",
        })

        # EVALUATE: Check each service against threshold
        total_cost = 0.0
        alerts = []
        evaluations = []

        for report in service_reports:
            cost = report.get("estimated_cost", 0.0)
            total_cost += cost
            name = report.get("name", report.get("service", "Unknown"))

            evaluation = self.evaluate_threshold(name, cost)
            evaluations.append({**report, **evaluation})

            print(f"  {evaluation['message']}")
            if report.get("status") in ("no_token", "api_error", "error"):
                print(f"    ℹ️  {report.get('message', '')}")

            if evaluation["level"] in ("CRITICAL", "WARNING"):
                alerts.append(evaluation)

        # Evaluate total
        total_eval = self.evaluate_threshold("TOTAL ALL SERVICES", total_cost)
        print(f"\n  {'─'*45}")
        print(f"  {total_eval['message']}")

        if total_eval["level"] in ("CRITICAL", "WARNING"):
            alerts.append(total_eval)

        # ALERT: Write to dashboard if thresholds exceeded
        if alerts:
            print(f"\n  ⚠️  {len(alerts)} budget alert(s) — writing to Boardroom...")
            self.alert_dashboard(alerts)
        else:
            print(f"\n  ✅ All costs within budget.")

        # Update state
        self.state["last_check"] = datetime.now().isoformat()
        self.state["total_checks"] = self.state.get("total_checks", 0) + 1
        self.state["current_total_cost"] = round(total_cost, 2)
        self.state["service_costs"] = {
            r["service"]: r.get("estimated_cost", 0.0) for r in service_reports
        }
        self._save_state()

        print(f"\n{'═'*55}\n")

        return {
            "timestamp": datetime.now().isoformat(),
            "threshold": self.threshold,
            "total_cost": round(total_cost, 2),
            "budget_remaining": round(self.threshold - total_cost, 2),
            "budget_pct_used": round(total_cost / self.threshold * 100, 1) if self.threshold > 0 else 0,
            "services": evaluations,
            "alerts": alerts,
            "alert_count": len(alerts),
            "status": total_eval["level"],
        }

    def get_status(self) -> Dict:
        """Return current fiscal status for dashboard API."""
        return {
            "engine": "Fiscal Oversight v1.0",
            "threshold": self.threshold,
            "last_check": self.state.get("last_check"),
            "total_checks": self.state.get("total_checks", 0),
            "alerts_sent": self.state.get("alerts_sent", 0),
            "current_total_cost": self.state.get("current_total_cost", 0.0),
            "service_costs": self.state.get("service_costs", {}),
            "budget_remaining": round(
                self.threshold - self.state.get("current_total_cost", 0.0), 2
            ),
        }

    def run_daemon(self, interval_seconds: int = 600):
        """Run fiscal checks on a schedule (default: every 10 min)."""
        print(f"  💰 Fiscal Oversight Daemon starting (interval: {interval_seconds}s)")
        try:
            while True:
                self.run_check()
                print(f"  💤 Next check in {interval_seconds}s...\n")
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n  🛑 Fiscal Oversight stopped by user.")


# ── CLI Entry Point ───────────────────────────────────────

if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(AETHER_DIR, "..", ".env"))
    except ImportError:
        pass

    if len(sys.argv) < 2:
        print("Usage: python fiscal_oversight.py <check|status|daemon>")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    fo = FiscalOversight()

    if cmd == "check":
        report = fo.run_check()
        print(json.dumps(report, indent=2, default=str))

    elif cmd == "status":
        status = fo.get_status()
        print(f"\n{'='*50}")
        print(f"  💰 FISCAL OVERSIGHT STATUS")
        print(f"{'='*50}")
        print(f"  Engine:       {status['engine']}")
        print(f"  Threshold:    ${status['threshold']:.2f}")
        print(f"  Total Cost:   ${status['current_total_cost']:.2f}")
        print(f"  Remaining:    ${status['budget_remaining']:.2f}")
        print(f"  Last Check:   {status['last_check'] or 'Never'}")
        print(f"  Total Checks: {status['total_checks']}")
        print(f"  Alerts Sent:  {status['alerts_sent']}")
        print(f"\n  Service Breakdown:")
        for svc, cost in status.get("service_costs", {}).items():
            print(f"    ${cost:.2f} — {svc}")
        print(f"\n{'='*50}\n")

    elif cmd == "daemon":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 600
        fo.run_daemon(interval)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
