"""
kill_switch.py — Emergency API Key Kill-Switch (Global Core)
═══════════════════════════════════════════════════════════════
.system_core | Antigravity V3.0 | Venture Studio Inheritance Engine

"Panic" function that temporarily disables all Antigravity API keys
if spending exceeds a configurable $X/hour threshold. Integrates
with n8n_budget_guard.py for automated cost protection.

Usage:
    python kill_switch.py --status           # Check current state
    python kill_switch.py --limit 500        # Check rate & panic if exceeded
    python kill_switch.py --panic            # Force trip the kill-switch
    python kill_switch.py --restore          # Restore keys from backup
"""

import os
import sys
import json
import shutil
import logging
import re
from datetime import datetime
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, FACTORY_DIR)

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

logger = logging.getLogger("system_core.kill_switch")

# Paths
KILL_LOG = os.path.join(FACTORY_DIR, "kill_switch_log.json")
RESILIENCE_CONFIG = os.path.join(FACTORY_DIR, "resilience_config.json")

# Key pattern for .env files
KEY_PATTERN = re.compile(
    r"^(\s*[A-Z][A-Z0-9_]*(?:_KEY|_TOKEN|_SECRET|_PASSWORD|_API_KEY)\s*=\s*)(.+)$",
    re.MULTILINE,
)

# Default hourly execution limit before panic triggers
DEFAULT_HOURLY_LIMIT = 500


class KillSwitch:
    """
    Emergency shutdown for API keys when spending exceeds safe thresholds.

    States:
        ARMED    — Monitoring, ready to trip if threshold exceeded
        TRIPPED  — Keys disabled, .env backed up to .env.panic_backup
        RESTORED — Keys restored from backup, system operational

    Usage:
        from system_core import KillSwitch
        ks = KillSwitch()
        ks.check_and_panic(hourly_limit=500)
        ks.restore()
    """

    DISABLED_MARKER = "DISABLED_BY_KILLSWITCH"

    def __init__(self, env_paths: Optional[list] = None):
        """
        Args:
            env_paths: List of .env file paths to protect.
                       Defaults to Factory root .env + Alpha_V2_Genesis .env.
        """
        if env_paths is None:
            self.env_paths = []
            # Factory root
            root_env = os.path.join(FACTORY_DIR, ".env")
            if os.path.exists(root_env):
                self.env_paths.append(root_env)
            # Alpha_V2_Genesis
            alpha_env = os.path.join(FACTORY_DIR, "Alpha_V2_Genesis", ".env")
            if os.path.exists(alpha_env):
                self.env_paths.append(alpha_env)
        else:
            self.env_paths = env_paths

        self._load_config()

    # ── Public API ───────────────────────────────────────

    def status(self) -> dict:
        """
        Return current kill-switch state.
        Checks if any .env.panic_backup files exist (indicating TRIPPED state).
        """
        tripped_any = False
        env_states = []

        for env_path in self.env_paths:
            backup_path = env_path + ".panic_backup"
            has_backup = os.path.exists(backup_path)
            if has_backup:
                tripped_any = True

            # Check if keys are currently disabled
            keys_disabled = False
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    keys_disabled = self.DISABLED_MARKER in content
                except Exception:
                    pass

            env_states.append({
                "path": env_path,
                "backup_exists": has_backup,
                "keys_disabled": keys_disabled,
            })

        if tripped_any:
            state = "TRIPPED"
        else:
            state = "ARMED"

        return {
            "state": state,
            "checked_at": datetime.now().isoformat(),
            "env_files": env_states,
            "hourly_limit": self.hourly_limit,
        }

    def check_and_panic(self, hourly_limit: Optional[int] = None) -> dict:
        """
        Check execution rate against the hourly limit.
        If exceeded, triggers panic() automatically.

        Args:
            hourly_limit: Max executions per hour. Defaults to config or 500.

        Returns:
            Dict with check results and whether panic was triggered.
        """
        limit = hourly_limit or self.hourly_limit

        # Read the budget guard's execution log
        rate_info = self._calculate_hourly_rate()

        result = {
            "checked_at": datetime.now().isoformat(),
            "hourly_limit": limit,
            "estimated_hourly_rate": rate_info.get("rate", 0),
            "panic_triggered": False,
        }

        if rate_info["rate"] >= limit:
            logger.warning(
                "🚨 Kill-Switch: hourly rate %d >= limit %d — TRIGGERING PANIC",
                rate_info["rate"],
                limit,
            )
            panic_result = self.panic(
                reason=f"Hourly execution rate ({rate_info['rate']}) exceeded limit ({limit})"
            )
            result["panic_triggered"] = True
            result["panic_result"] = panic_result
        else:
            logger.info(
                "Kill-Switch: hourly rate %d / %d — within limits",
                rate_info["rate"],
                limit,
            )

        return result

    def panic(self, reason: str = "Manual panic trigger") -> dict:
        """
        EMERGENCY: Disable all API keys in all monitored .env files.

        1. Backs up each .env to .env.panic_backup
        2. Rewrites all API key values to DISABLED_BY_KILLSWITCH
        3. Logs the event
        """
        results = []
        for env_path in self.env_paths:
            r = self._disable_env_keys(env_path)
            results.append(r)

        event = {
            "event": "PANIC",
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "env_results": results,
        }

        self._log_event(event)
        logger.critical("🚨 KILL-SWITCH TRIPPED: %s", reason)

        return event

    def restore(self) -> dict:
        """
        Restore all .env files from their .panic_backup copies.
        """
        results = []
        for env_path in self.env_paths:
            backup_path = env_path + ".panic_backup"
            if os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, env_path)
                    os.remove(backup_path)
                    results.append({
                        "path": env_path,
                        "status": "restored",
                    })
                    logger.info("Restored: %s", env_path)
                except Exception as e:
                    results.append({
                        "path": env_path,
                        "status": "error",
                        "error": str(e),
                    })
            else:
                results.append({
                    "path": env_path,
                    "status": "no_backup_found",
                })

        event = {
            "event": "RESTORE",
            "timestamp": datetime.now().isoformat(),
            "results": results,
        }

        self._log_event(event)
        logger.info("✅ Kill-Switch restored — keys re-enabled")

        return event

    # ── Internal ─────────────────────────────────────────

    def _load_config(self):
        """Load hourly limit from resilience_config.json if available."""
        self.hourly_limit = DEFAULT_HOURLY_LIMIT
        try:
            if os.path.exists(RESILIENCE_CONFIG):
                with open(RESILIENCE_CONFIG, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                ks_cfg = cfg.get("kill_switch", {})
                self.hourly_limit = ks_cfg.get("hourly_limit", DEFAULT_HOURLY_LIMIT)
        except Exception:
            pass

    def _disable_env_keys(self, env_path: str) -> dict:
        """Back up .env and rewrite all API key values to DISABLED."""
        if not os.path.exists(env_path):
            return {"path": env_path, "status": "not_found"}

        backup_path = env_path + ".panic_backup"

        try:
            # Backup (only if no existing backup — don't overwrite a clean backup)
            if not os.path.exists(backup_path):
                shutil.copy2(env_path, backup_path)

            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()

            disabled_count = 0

            def _replace(m):
                nonlocal disabled_count
                disabled_count += 1
                return m.group(1) + self.DISABLED_MARKER

            new_content = KEY_PATTERN.sub(_replace, content)

            with open(env_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return {
                "path": env_path,
                "status": "disabled",
                "keys_disabled": disabled_count,
                "backup": backup_path,
            }

        except Exception as e:
            return {"path": env_path, "status": "error", "error": str(e)}

    def _calculate_hourly_rate(self) -> dict:
        """
        Estimate hourly execution rate from the budget guard's log.
        Reads Alpha_V2_Genesis/Alpha_Data/n8n_execution_log.json.
        """
        log_path = os.path.join(
            FACTORY_DIR, "Alpha_V2_Genesis", "Alpha_Data", "n8n_execution_log.json"
        )

        if not os.path.exists(log_path):
            return {"rate": 0, "source": "no_log_found"}

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                log = json.load(f)

            history = log.get("history", [])
            if len(history) < 2:
                latest = history[-1] if history else {}
                return {
                    "rate": latest.get("total_executions", 0),
                    "source": "single_snapshot",
                }

            # Compare last two snapshots to estimate rate
            latest = history[-1]
            previous = history[-2]

            delta_execs = latest.get("total_executions", 0) - previous.get("total_executions", 0)
            # Assume snapshots are roughly 1 hour apart (budget guard runs during preflight)
            return {
                "rate": max(0, delta_execs),
                "source": "delta_calculation",
                "latest_total": latest.get("total_executions", 0),
                "previous_total": previous.get("total_executions", 0),
            }

        except Exception as e:
            return {"rate": 0, "source": "error", "error": str(e)}

    def _log_event(self, event: dict):
        """Append event to kill_switch_log.json."""
        try:
            existing = []
            if os.path.exists(KILL_LOG):
                try:
                    with open(KILL_LOG, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    existing = []

            existing.append(event)

            # Keep last 100 events
            if len(existing) > 100:
                existing = existing[-100:]

            with open(KILL_LOG, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, default=str)

        except Exception as e:
            logger.error("Failed to log kill-switch event: %s", e)


# ── Module-level singleton ───────────────────────────────
_kill_switch = KillSwitch()


def get_kill_switch() -> KillSwitch:
    """Get the module-level KillSwitch instance."""
    return _kill_switch


# ── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Kill-Switch — Emergency API Key Protection"
    )
    parser.add_argument("--status", action="store_true", help="Check current kill-switch state")
    parser.add_argument("--limit", type=int, default=None, help="Check rate with hourly limit, panic if exceeded")
    parser.add_argument("--panic", action="store_true", help="Force-trip the kill-switch (disables all keys)")
    parser.add_argument("--restore", action="store_true", help="Restore keys from backup")
    args = parser.parse_args()

    ks = KillSwitch()

    print(f"\n{'='*60}")
    print(f"  ⚡ Kill-Switch — Emergency API Key Protection")
    print(f"{'='*60}\n")

    if args.status:
        s = ks.status()
        icon = "🟢" if s["state"] == "ARMED" else "🔴"
        print(f"  {icon} State: {s['state']}")
        print(f"  ⏱️  Hourly Limit: {s['hourly_limit']} executions/hour")
        for ef in s["env_files"]:
            status_icon = "🔒" if ef["keys_disabled"] else "✅"
            print(f"  {status_icon} {ef['path']}")
            if ef["backup_exists"]:
                print(f"     ↳ Panic backup exists")

    elif args.limit is not None:
        result = ks.check_and_panic(args.limit)
        if result["panic_triggered"]:
            print(f"  🚨 PANIC TRIGGERED!")
            print(f"  Hourly rate: {result['estimated_hourly_rate']} >= limit: {result['hourly_limit']}")
            print(f"  All API keys have been DISABLED.")
            print(f"  Run: python kill_switch.py --restore  to re-enable.")
        else:
            print(f"  ✅ Within limits")
            print(f"  Hourly rate: {result['estimated_hourly_rate']} / {result['hourly_limit']}")

    elif args.panic:
        print(f"  🚨 FORCE PANIC — Disabling all API keys...")
        result = ks.panic(reason="Manual CLI panic trigger")
        for r in result.get("env_results", []):
            print(f"  {r['path']}: {r['status']} ({r.get('keys_disabled', 0)} keys disabled)")
        print(f"\n  Run: python kill_switch.py --restore  to re-enable.")

    elif args.restore:
        print(f"  🔄 Restoring API keys from backup...")
        result = ks.restore()
        for r in result.get("results", []):
            icon = "✅" if r["status"] == "restored" else "⚠️"
            print(f"  {icon} {r['path']}: {r['status']}")

    else:
        parser.print_help()

    print(f"\n{'='*60}\n")
