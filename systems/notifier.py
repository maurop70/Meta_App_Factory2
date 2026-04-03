"""
notifier.py — System Memos & Sentinel Alerts
══════════════════════════════════════════════════
Replaces the Legacy n8n Cloud webhooks for sub-100ms routing.
"""
import os
import json
import logging
import threading
from datetime import datetime

logger = logging.getLogger("SystemNotifier")

class SystemNotifier:
    def __init__(self):
        self.log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge_logs.json")
        self._lock = threading.Lock()
        self._init_logs()

    def _init_logs(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump({"sentinel": [], "hr": []}, f, indent=4)

    def _read_logs(self):
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read bridge logs: {e}")
            return {"sentinel": [], "hr": []}

    def _write_logs(self, data):
        try:
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to write bridge logs: {e}")

    def trigger_sentinel(self, severity: str, message: str, source: str = "System"):
        """Formats and stores a Sentinel system alert."""
        with self._lock:
            logs = self._read_logs()
            
            # Format expected by OmniDashboard.jsx
            alert = {
                "timestamp": datetime.now().isoformat(),
                "severity": severity.lower(),
                "message": f"[{source}] {message}"
            }
            logs["sentinel"].insert(0, alert)
            logs["sentinel"] = logs["sentinel"][:50]  # Cap at 50 logs
            
            self._write_logs(logs)

        # Sentinel Hardening Hook outside the file lock
        if severity.lower() == "critical":
            logger.warning(f"CRITICAL SENTINEL ALERT from {source}. Firing Auto Heal Watchdog.")
            self._trigger_heal_event(source, message)
            
        return alert

    def trigger_hr_memo(self, agent_id: str, memo: str):
        """Formats and stores an HR Agent deployment/status memo."""
        with self._lock:
            logs = self._read_logs()
            
            entry = {
                "timestamp": datetime.now().isoformat(),
                "agent_id": agent_id,
                "memo": memo
            }
            logs["hr"].insert(0, entry)
            logs["hr"] = logs["hr"][:50]
            
            self._write_logs(logs)
            
        return entry

    def get_sentinel_logs(self):
        with self._lock:
            return self._read_logs().get("sentinel", [])

    def get_hr_logs(self):
        with self._lock:
            return self._read_logs().get("hr", [])

    def _trigger_heal_event(self, source: str, message: str):
        try:
            import sys
            factory_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if factory_root not in sys.path:
                sys.path.insert(0, factory_root)
                
            from auto_heal import _log_heal_event
            _log_heal_event("SystemNotifier", f"Critical Alert Triggered: {message}", {"source": source}, "SYSTEM_ALERT")
            logger.info("Auto Heal log injection complete.")
        except Exception as e:
            logger.error(f"Failed to fire Watchdog heal event: {e}")
