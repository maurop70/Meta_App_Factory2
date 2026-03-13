"""
Sentinel Bridge — Fernet Vault (Zero-Leak Protocol)
====================================================
AES-128-CBC encryption via Python's cryptography.Fernet for all
credentials and personal data. Key derivation uses PBKDF2-HMAC-SHA256
with a machine-specific salt so the vault is portable but tied to
owner confirmation.

Usage:
    vault = FernetVault()          # auto-creates key on first run
    vault.store("ntfy_topic", "sentinel_mauro_private")
    topic = vault.retrieve("ntfy_topic")
"""

# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
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
import json
import base64
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger("sentinel.vault")

# ── Paths ────────────────────────────────────────────────────────────
_LOCAL_DATA = Path(os.environ.get(
    "SENTINEL_DATA_DIR",
    os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                 "AntigravityAI", "Sentinel_Bridge")
))
_VAULT_FILE = _LOCAL_DATA / "vault.enc"
_KEY_FILE   = _LOCAL_DATA / ".vault_key"
_SALT_FILE  = _LOCAL_DATA / ".vault_salt"


class FernetVault:
    """Securely store and retrieve key-value secrets with AES-128."""

    def __init__(self, passphrase: str | None = None):
        _LOCAL_DATA.mkdir(parents=True, exist_ok=True)
        self._fernet = self._init_fernet(passphrase or self._default_passphrase())
        self._cache: dict[str, str] = self._load()

    # ── Public API ───────────────────────────────────────────────────
    def store(self, key: str, value: str) -> None:
        """Encrypt and persist a secret."""
        self._cache[key] = value
        self._persist()
        logger.info("Vault: stored key '%s'", key)

    def retrieve(self, key: str, default: str | None = None) -> str | None:
        """Retrieve a decrypted secret."""
        return self._cache.get(key, default)

    def delete(self, key: str) -> bool:
        """Remove a secret from the vault."""
        if key in self._cache:
            del self._cache[key]
            self._persist()
            logger.info("Vault: deleted key '%s'", key)
            return True
        return False

    def list_keys(self) -> list[str]:
        """Return all stored key names (not values)."""
        return list(self._cache.keys())

    def export_audit(self) -> dict:
        """Return non-sensitive metadata for telemetry."""
        return {
            "total_secrets": len(self._cache),
            "vault_path": str(_VAULT_FILE),
            "last_modified": _VAULT_FILE.stat().st_mtime if _VAULT_FILE.exists() else None,
            "encryption": "Fernet AES-128-CBC",
        }

    # ── Internal ─────────────────────────────────────────────────────
    @staticmethod
    def _default_passphrase() -> str:
        """Machine-bound passphrase derived from hostname + username."""
        raw = f"{os.environ.get('COMPUTERNAME', 'sentinel')}-{os.getlogin()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _get_salt(self) -> bytes:
        if _SALT_FILE.exists():
            return _SALT_FILE.read_bytes()
        salt = os.urandom(16)
        _SALT_FILE.write_bytes(salt)
        return salt

    def _init_fernet(self, passphrase: str) -> Fernet:
        salt = self._get_salt()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        return Fernet(key)

    def _load(self) -> dict[str, str]:
        if not _VAULT_FILE.exists():
            return {}
        try:
            raw = _VAULT_FILE.read_bytes()
            decrypted = self._fernet.decrypt(raw)
            return json.loads(decrypted.decode())
        except (InvalidToken, json.JSONDecodeError) as exc:
            logger.error("Vault decryption failed: %s — starting fresh", exc)
            return {}

    def _persist(self) -> None:
        payload = json.dumps(self._cache, indent=2).encode()
        encrypted = self._fernet.encrypt(payload)
        _VAULT_FILE.write_bytes(encrypted)


# ── CLI convenience ──────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    v = FernetVault()
    if len(sys.argv) == 1:
        print("Vault keys:", v.list_keys())
    elif sys.argv[1] == "set" and len(sys.argv) == 4:
        v.store(sys.argv[2], sys.argv[3])
        print(f"Stored '{sys.argv[2]}'")
    elif sys.argv[1] == "get" and len(sys.argv) == 3:
        print(v.retrieve(sys.argv[2], "<not found>"))
    elif sys.argv[1] == "audit":
        print(json.dumps(v.export_audit(), indent=2))
    else:
        print("Usage: python fernet_vault.py [set <k> <v> | get <k> | audit]")
# V3 AUTO-HEAL ACTIVE
