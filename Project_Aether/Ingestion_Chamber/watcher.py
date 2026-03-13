"""
Ingestion Chamber — Active Watcher
====================================
Project Aether | Meta_App_Factory
Triggers processing when files are dropped into the watch directory.

Data Flow: File Drop → Validation → Classification → Compliance Review → Vault
"""

# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

from auto_heal import healed_post, auto_heal, diagnose

def _v3_preflight():
    """V3: Ping Resonance_Watchdog_V3 before execution."""
    if not _V3_AVAILABLE:
        return True
    try:
        import json as _j
        _cfg_path = _os.path.join(_FACTORY_DIR, "resilience_config.json")
        if not _os.path.exists(_cfg_path):
            return True
        with open(_cfg_path) as _f:
            _cfg = _j.load(_f)
        _url = _cfg.get("cloud_health", {}).get("watchdog_url", "")
        if not _url:
            return True
        import requests as _rq
        _r = _rq.get(_url, timeout=5)
        return _r.status_code == 200
    except Exception:
        return False


import os
import sys
import json
import time
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ── Configuration ──
CHAMBER_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = os.path.abspath(os.path.join(CHAMBER_DIR, "..", "Compliance_Vault"))
INTAKE_LOG = os.path.join(CHAMBER_DIR, "intake_log.json")
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".json", ".csv", ".txt", ".xlsx"}

# Sensitivity classification rules
SENSITIVITY_RULES = {
    "clinical": {"keywords": ["diagnosis", "medical", "psychological", "developmental", "therapy", "assessment"], "level": "CRITICAL"},
    "educational": {"keywords": ["iep", "school", "evaluation", "teacher", "grade", "academic"], "level": "HIGH"},
    "behavioral": {"keywords": ["aba", "behavior", "intervention", "bip", "functional"], "level": "CRITICAL"},
    "financial": {"keywords": ["invoice", "budget", "cost", "payment", "insurance"], "level": "HIGH"},
    "general": {"keywords": [], "level": "MEDIUM"},
}


class IntakeRecord:
    """Structured intake record for every file processed."""

    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.extension = Path(filepath).suffix.lower()
        self.file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        self.ingested_at = datetime.now().isoformat()
        self.file_hash = self._compute_hash()
        self.sensitivity = "MEDIUM"
        self.category = "general"
        self.compliance_status = "PENDING_REVIEW"
        self.vault_path = None

    def _compute_hash(self):
        """SHA-256 hash for integrity verification."""
        if not os.path.exists(self.filepath):
            return None
        sha256 = hashlib.sha256()
        with open(self.filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def classify(self):
        """Auto-classify based on filename and extension."""
        name_lower = self.filename.lower()
        for category, rules in SENSITIVITY_RULES.items():
            if any(kw in name_lower for kw in rules["keywords"]):
                self.category = category
                self.sensitivity = rules["level"]
                return
        self.category = "general"
        self.sensitivity = "MEDIUM"

    def to_dict(self):
        return {
            "filename": self.filename,
            "extension": self.extension,
            "file_size_bytes": self.file_size,
            "file_hash_sha256": self.file_hash,
            "ingested_at": self.ingested_at,
            "category": self.category,
            "sensitivity": self.sensitivity,
            "compliance_status": self.compliance_status,
            "vault_path": self.vault_path,
        }


class IngestionHandler(FileSystemEventHandler):
    """Watches for new files and triggers the intake pipeline."""

    def on_created(self, event):
        if event.is_directory:
            return
        # Ignore system files and the log itself
        basename = os.path.basename(event.src_path)
        if basename.startswith(".") or basename == "intake_log.json" or basename == "README.md" or basename == "watcher.py":
            return

        filepath = event.src_path
        ext = Path(filepath).suffix.lower()

        if ext not in SUPPORTED_EXTENSIONS:
            print(f"[INGESTION] ⚠️ Unsupported file type: {basename} ({ext})")
            return

        # Brief delay for file write completion
        time.sleep(1)

        print(f"[INGESTION] 📥 New file detected: {basename}")
        self._process_intake(filepath)

    def _process_intake(self, filepath):
        """Stage 1: Validate, classify, and route to Compliance."""
        record = IntakeRecord(filepath)
        record.classify()

        print(f"[INGESTION] 📋 Classification: {record.category} | Sensitivity: {record.sensitivity}")

        # Route CRITICAL and HIGH sensitivity to Compliance Vault
        if record.sensitivity in ("CRITICAL", "HIGH"):
            vault_subdir = os.path.join(VAULT_DIR, "pending_review")
            os.makedirs(vault_subdir, exist_ok=True)
            dest = os.path.join(vault_subdir, record.filename)
            shutil.copy2(filepath, dest)
            record.vault_path = dest
            record.compliance_status = "IN_VAULT_PENDING_REVIEW"
            print(f"[INGESTION] 🔒 Routed to Compliance Vault: pending_review/{record.filename}")
        else:
            record.compliance_status = "CLEARED_LOW_SENSITIVITY"
            print(f"[INGESTION] ✅ Low sensitivity — cleared without vault routing")

        # Log the intake
        self._log_intake(record)

        # Remove from chamber after processing
        try:
            os.remove(filepath)
            print(f"[INGESTION] 🗑️ Cleaned: {record.filename} removed from chamber")
        except Exception as e:
            print(f"[INGESTION] ⚠️ Cleanup warning: {e}")

    def _log_intake(self, record):
        """Append to intake log with full audit trail."""
        log = []
        if os.path.exists(INTAKE_LOG):
            try:
                with open(INTAKE_LOG, "r") as f:
                    log = json.load(f)
            except (json.JSONDecodeError, IOError):
                log = []

        log.append(record.to_dict())

        with open(INTAKE_LOG, "w") as f:
            json.dump(log, f, indent=2)

        print(f"[INGESTION] 📝 Logged to intake_log.json (total records: {len(log)})")


def start_watcher():
    """Start the file system watcher on the Ingestion Chamber directory."""
    # Ensure we don't watch Python/system files
    watch_path = CHAMBER_DIR

    print("=" * 60)
    print("  INGESTION CHAMBER — Active Watcher")
    print(f"  Monitoring: {watch_path}")
    print(f"  Supported: {', '.join(SUPPORTED_EXTENSIONS)}")
    print(f"  Vault: {VAULT_DIR}")
    print("=" * 60)

    observer = Observer()
    handler = IngestionHandler()
    observer.schedule(handler, watch_path, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[INGESTION] Watcher stopped.")

    observer.join()


if __name__ == "__main__":
    start_watcher()
# V3 AUTO-HEAL ACTIVE
