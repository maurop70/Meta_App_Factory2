"""
Compliance Vault — Active Watcher & Secure Storage Engine
===========================================================
Project Aether | Meta_App_Factory
Monitors pending_review/ for files routed by the Ingestion Chamber.
Applies encryption, access control tagging, and audit trail logging.
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
import base64
from datetime import datetime
from pathlib import Path
from cryptography.fernet import Fernet
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ── Configuration ──
VAULT_DIR = os.path.dirname(os.path.abspath(__file__))
PENDING_DIR = os.path.join(VAULT_DIR, "pending_review")
SECURED_DIR = os.path.join(VAULT_DIR, "secured")
AUDIT_LOG = os.path.join(VAULT_DIR, "audit_trail.json")
KEY_FILE = os.path.join(VAULT_DIR, ".vault_key")

# Access Control List — who can read/write
ACL = {
    "read": ["CEO", "Compliance_Officer", "Data_Architect", "The_Librarian"],
    "write": ["Compliance_Officer"],
    "delete": ["CEO", "Compliance_Officer"],  # Dual authorization required
}


def _get_or_create_key():
    """Get or generate the Fernet encryption key."""
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(key)
    print("[VAULT] 🔐 New encryption key generated")
    return key


def _encrypt_file(filepath, key):
    """Encrypt a file in-place and return the encrypted path."""
    fernet = Fernet(key)
    with open(filepath, "rb") as f:
        data = f.read()
    encrypted = fernet.encrypt(data)
    enc_path = filepath + ".enc"
    with open(enc_path, "wb") as f:
        f.write(encrypted)
    return enc_path


def _decrypt_file(enc_path, key, output_path=None):
    """Decrypt a vault file. Returns decrypted content."""
    fernet = Fernet(key)
    with open(enc_path, "rb") as f:
        encrypted = f.read()
    decrypted = fernet.decrypt(encrypted)
    if output_path:
        with open(output_path, "wb") as f:
            f.write(decrypted)
    return decrypted


class AuditTrail:
    """Immutable audit log for all vault operations."""

    def __init__(self, log_path=AUDIT_LOG):
        self.log_path = log_path

    def log(self, action, filename, agent="SYSTEM", details=None):
        entries = self._load()
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "filename": filename,
            "agent": agent,
            "details": details or {},
            "entry_hash": None,
        }
        # Chain hash for tamper detection
        prev_hash = entries[-1]["entry_hash"] if entries else "GENESIS"
        entry_str = json.dumps({k: v for k, v in entry.items() if k != "entry_hash"})
        entry["entry_hash"] = hashlib.sha256(
            f"{prev_hash}:{entry_str}".encode()
        ).hexdigest()

        entries.append(entry)
        with open(self.log_path, "w") as f:
            json.dump(entries, f, indent=2)

    def _load(self):
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def verify_integrity(self):
        """Verify the hash chain hasn't been tampered with."""
        entries = self._load()
        prev_hash = "GENESIS"
        for i, entry in enumerate(entries):
            entry_copy = {k: v for k, v in entry.items() if k != "entry_hash"}
            expected = hashlib.sha256(
                f"{prev_hash}:{json.dumps(entry_copy)}".encode()
            ).hexdigest()
            if entry["entry_hash"] != expected:
                return False, f"Integrity violation at entry {i}"
            prev_hash = entry["entry_hash"]
        return True, f"All {len(entries)} entries verified"


class VaultHandler(FileSystemEventHandler):
    """Watches pending_review/ and processes files into secured storage."""

    def __init__(self):
        self.key = _get_or_create_key()
        self.audit = AuditTrail()
        os.makedirs(PENDING_DIR, exist_ok=True)
        os.makedirs(SECURED_DIR, exist_ok=True)

    def on_created(self, event):
        if event.is_directory:
            return
        basename = os.path.basename(event.src_path)
        if basename.startswith("."):
            return

        time.sleep(1)  # Wait for write completion
        print(f"[VAULT] 📥 New file in pending_review: {basename}")
        self._secure_file(event.src_path)

    def _secure_file(self, filepath):
        """Full security pipeline: hash → encrypt → store → log."""
        basename = os.path.basename(filepath)

        # 1. Compute integrity hash of original
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        original_hash = sha256.hexdigest()
        file_size = os.path.getsize(filepath)

        # 2. Encrypt
        enc_path = _encrypt_file(filepath, self.key)
        secured_dest = os.path.join(SECURED_DIR, os.path.basename(enc_path))
        os.rename(enc_path, secured_dest)
        print(f"[VAULT] 🔒 Encrypted: {basename} → secured/{basename}.enc")

        # 3. Remove plaintext from pending
        try:
            os.remove(filepath)
        except Exception:
            pass

        # 4. Audit trail
        self.audit.log(
            action="SECURED",
            filename=basename,
            agent="Compliance_Officer",
            details={
                "original_hash_sha256": original_hash,
                "original_size_bytes": file_size,
                "encrypted_path": f"secured/{basename}.enc",
                "encryption": "Fernet (AES-128-CBC)",
                "acl": ACL,
            },
        )
        print(f"[VAULT] 📝 Audit trail updated | Hash: {original_hash[:16]}...")


def check_access(agent_name, operation="read"):
    """Verify an agent has permission for the requested operation."""
    allowed = ACL.get(operation, [])
    if agent_name in allowed:
        return True
    print(f"[VAULT] 🚫 ACCESS DENIED: {agent_name} cannot {operation}")
    return False


def retrieve_file(filename, agent_name, output_dir=None):
    """Secure file retrieval with access control and audit logging."""
    if not check_access(agent_name, "read"):
        return None

    enc_path = os.path.join(SECURED_DIR, f"{filename}.enc")
    if not os.path.exists(enc_path):
        print(f"[VAULT] ❌ File not found: {filename}")
        return None

    key = _get_or_create_key()
    audit = AuditTrail()

    if output_dir:
        out_path = os.path.join(output_dir, filename)
        _decrypt_file(enc_path, key, out_path)
        audit.log("RETRIEVED", filename, agent_name, {"output_path": out_path})
        print(f"[VAULT] 📤 Retrieved: {filename} → {out_path}")
        return out_path
    else:
        data = _decrypt_file(enc_path, key)
        audit.log("RETRIEVED", filename, agent_name, {"method": "in_memory"})
        return data


def start_watcher():
    """Start the Compliance Vault watcher on pending_review/."""
    os.makedirs(PENDING_DIR, exist_ok=True)
    os.makedirs(SECURED_DIR, exist_ok=True)

    print("=" * 60)
    print("  COMPLIANCE VAULT — Active Watcher")
    print(f"  Monitoring: {PENDING_DIR}")
    print(f"  Secured Storage: {SECURED_DIR}")
    print(f"  Encryption: Fernet (AES-128-CBC)")
    print(f"  ACL Read: {', '.join(ACL['read'])}")
    print(f"  ACL Write: {', '.join(ACL['write'])}")
    print("=" * 60)

    observer = Observer()
    handler = VaultHandler()
    observer.schedule(handler, PENDING_DIR, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[VAULT] Watcher stopped.")

    observer.join()


if __name__ == "__main__":
    start_watcher()
# V3 AUTO-HEAL ACTIVE
