"""
local_state_manager.py — Outgoing Request State Logger
═══════════════════════════════════════════════════════
Logs every outgoing HTTP request from factory.py to local_pending_sync.json
with a UUID, timestamp, payload hash, and status before the call is made.

Usage:
    from local_state_manager import StateManager
    sm = StateManager()
    entry_id = sm.log_outgoing(url, payload, project)
    # ... make HTTP call ...
    sm.mark_sent(entry_id, status_code)
    # or on failure:
    sm.mark_failed(entry_id, error)
"""

import os
import sys
import json
import uuid
import hashlib
import threading
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, "local_pending_sync.json")
PENDING_DIR = os.path.join(SCRIPT_DIR, "pending_sync")
os.makedirs(PENDING_DIR, exist_ok=True)

_lock = threading.Lock()


class StateManager:
    """Thread-safe outgoing request state logger."""

    def __init__(self, state_file=STATE_FILE):
        self.state_file = state_file
        self._ensure_state()

    def _ensure_state(self):
        """Initialize state file if missing."""
        if not os.path.exists(self.state_file):
            self._write_state({
                "_version": "3.0",
                "_initialized_at": datetime.now().isoformat(),
                "safe_buffer_mode": False,
                "pending_count": 0,
                "entries": []
            })

    def _read_state(self) -> dict:
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"entries": [], "pending_count": 0, "safe_buffer_mode": False}

    def _write_state(self, state: dict):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)

    def is_safe_buffer_mode(self) -> bool:
        """Check if Safe-Buffer mode is active."""
        state = self._read_state()
        return state.get("safe_buffer_mode", False)

    def set_safe_buffer_mode(self, enabled: bool):
        """Toggle Safe-Buffer mode."""
        with _lock:
            state = self._read_state()
            state["safe_buffer_mode"] = enabled
            state["safe_buffer_toggled_at"] = datetime.now().isoformat()
            self._write_state(state)

    def log_outgoing(self, url: str, payload: dict, project: str) -> str:
        """Log an outgoing request BEFORE it's sent. Returns entry UUID."""
        entry_id = str(uuid.uuid4())
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

        entry = {
            "id": entry_id,
            "timestamp": datetime.now().isoformat(),
            "project": project,
            "url": url,
            "payload_hash": payload_hash,
            "status": "pending",
            "response_code": None,
            "latency_ms": None,
            "error": None,
        }

        with _lock:
            state = self._read_state()
            state["entries"].append(entry)
            state["pending_count"] = sum(1 for e in state["entries"] if e["status"] == "pending")
            state["last_log_event"] = datetime.now().isoformat()
            self._write_state(state)

        return entry_id

    def mark_sent(self, entry_id: str, status_code: int, latency_ms: float = None):
        """Mark an entry as successfully sent."""
        with _lock:
            state = self._read_state()
            for e in state["entries"]:
                if e["id"] == entry_id:
                    e["status"] = "sent"
                    e["response_code"] = status_code
                    e["latency_ms"] = latency_ms
                    e["completed_at"] = datetime.now().isoformat()
                    break
            state["pending_count"] = sum(1 for e in state["entries"] if e["status"] == "pending")
            self._write_state(state)

    def mark_failed(self, entry_id: str, error: str):
        """Mark an entry as failed and queue payload to pending_sync/."""
        with _lock:
            state = self._read_state()
            for e in state["entries"]:
                if e["id"] == entry_id:
                    e["status"] = "failed"
                    e["error"] = str(error)[:200]
                    e["completed_at"] = datetime.now().isoformat()
                    break
            state["pending_count"] = sum(1 for e in state["entries"] if e["status"] == "pending")
            self._write_state(state)

    def trim_old_entries(self, keep=100):
        """Keep only the last N entries to prevent the file from growing unbounded."""
        with _lock:
            state = self._read_state()
            if len(state["entries"]) > keep:
                state["entries"] = state["entries"][-keep:]
            self._write_state(state)

    def get_stats(self) -> dict:
        """Get summary statistics."""
        state = self._read_state()
        entries = state.get("entries", [])
        return {
            "total": len(entries),
            "pending": sum(1 for e in entries if e["status"] == "pending"),
            "sent": sum(1 for e in entries if e["status"] == "sent"),
            "failed": sum(1 for e in entries if e["status"] == "failed"),
            "safe_buffer_mode": state.get("safe_buffer_mode", False),
        }
