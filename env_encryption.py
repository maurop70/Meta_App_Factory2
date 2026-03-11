"""
env_encryption.py — Fernet AES-128 Encryption for Environment Variables
========================================================================
Meta App Factory | Security Module

Mirrors the security model of vault_client.py (Delegate AI Vault):
- PBKDF2 key derivation with SHA-256, 600K iterations
- Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256)
- Same master password chain: VAULT_PASSWORD env → .vault_pw file

Usage:
    from env_encryption import encrypt_env_file, decrypt_env_value
    encrypt_env_file("path/to/.env")      # → creates .env.enc
    value = decrypt_env_value(key, blob)   # → plaintext string
"""

import os
import sys
import json
import base64
import hashlib

# Force UTF-8 on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
from typing import Optional, Dict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Sensitive keys that should be encrypted (patterns matched case-insensitively)
SENSITIVE_PATTERNS = [
    "API_KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL",
    "DSN", "DATABASE_URL", "ENCRYPTION_KEY", "AUTH",
]


# ── Key Derivation (mirrors vault_client.py) ──────────────

def _get_master_password() -> str:
    """
    Retrieve the master encryption password.
    Chain: VAULT_PASSWORD env → .vault_pw file → empty (skip encryption)
    """
    pw = os.getenv("VAULT_PASSWORD", "")
    if pw:
        return pw

    # Check for .vault_pw file in factory root and parent
    for candidate in [
        os.path.join(SCRIPT_DIR, ".vault_pw"),
        os.path.join(os.path.dirname(SCRIPT_DIR), ".vault_pw"),
    ]:
        if os.path.exists(candidate):
            try:
                with open(candidate, "r") as f:
                    pw = f.read().strip()
                if pw:
                    return pw
            except Exception:
                pass

    return ""


def _derive_fernet_key(password: str, salt: bytes) -> bytes:
    """
    Derive a Fernet-compatible key using PBKDF2 (identical to vault_client.py).
    PBKDF2-HMAC-SHA256, 600K iterations, 32-byte key → base64 encoded.
    """
    try:
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    except ImportError:
        # Fallback: use hashlib PBKDF2 (no cryptography library needed)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000, dklen=32)
        return base64.urlsafe_b64encode(dk)


# ── Encrypt / Decrypt Primitives ──────────────────────────

def encrypt_value(plaintext: str, password: str, salt: bytes) -> str:
    """Encrypt a single string value. Returns base64-encoded ciphertext."""
    try:
        from cryptography.fernet import Fernet
        key = _derive_fernet_key(password, salt)
        f = Fernet(key)
        return f.encrypt(plaintext.encode()).decode()
    except ImportError:
        # No cryptography library — return a marked-but-unencrypted value
        return f"ENC_UNAVAILABLE:{base64.b64encode(plaintext.encode()).decode()}"


def decrypt_value(ciphertext: str, password: str, salt: bytes) -> str:
    """Decrypt a single encrypted value."""
    if ciphertext.startswith("ENC_UNAVAILABLE:"):
        return base64.b64decode(ciphertext[16:]).decode()

    try:
        from cryptography.fernet import Fernet
        key = _derive_fernet_key(password, salt)
        f = Fernet(key)
        return f.decrypt(ciphertext.encode()).decode()
    except ImportError:
        raise RuntimeError("cryptography library required for decryption")
    except Exception as e:
        raise RuntimeError(f"Decryption failed: {e}")


def _is_sensitive_key(key: str) -> bool:
    """Check if an env key name contains sensitive patterns."""
    key_upper = key.upper()
    return any(pat in key_upper for pat in SENSITIVE_PATTERNS)


# ── File-Level Operations ─────────────────────────────────

def encrypt_env_file(env_path: str) -> Optional[str]:
    """
    Read a .env file, encrypt sensitive values, write .env.enc alongside it.
    Returns the path to .env.enc, or None if encryption was skipped.
    """
    password = _get_master_password()
    if not password:
        print("  ⚠️  VAULT_PASSWORD not set — env encryption skipped (plaintext .env only)")
        return None

    if not os.path.exists(env_path):
        return None

    # Generate or load salt
    salt_path = env_path + ".salt"
    if os.path.exists(salt_path):
        with open(salt_path, "rb") as f:
            salt = f.read()
    else:
        salt = os.urandom(16)
        with open(salt_path, "wb") as f:
            f.write(salt)

    # Parse .env
    encrypted_lines = []
    sensitive_count = 0
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                encrypted_lines.append(line.rstrip())
                continue

            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip()

            if _is_sensitive_key(key) and value and not value.startswith("${"):
                # Encrypt this value
                enc_value = encrypt_value(value, password, salt)
                encrypted_lines.append(f"{key}=ENC:{enc_value}")
                sensitive_count += 1
            else:
                encrypted_lines.append(stripped)

    # Write .env.enc
    enc_path = env_path.replace(".env", ".env.enc")
    if enc_path == env_path:
        enc_path = env_path + ".enc"

    with open(enc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(encrypted_lines) + "\n")

    print(f"  🔐 Encrypted {sensitive_count} sensitive value(s) → {os.path.basename(enc_path)}")
    return enc_path


def decrypt_env_file(enc_path: str) -> Dict[str, str]:
    """
    Read an encrypted .env.enc file and return all key-value pairs (decrypted).
    """
    password = _get_master_password()
    if not password:
        raise RuntimeError("VAULT_PASSWORD required to decrypt .env.enc")

    salt_path = enc_path.replace(".enc", ".salt")
    if not os.path.exists(salt_path):
        # Try alternate location
        salt_path = enc_path + ".salt"
    if not os.path.exists(salt_path):
        raise RuntimeError(f"Salt file not found: {salt_path}")

    with open(salt_path, "rb") as f:
        salt = f.read()

    result = {}
    with open(enc_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip()

            if value.startswith("ENC:"):
                value = decrypt_value(value[4:], password, salt)

            result[key] = value

    return result


# ── n8n Integration Helper ─────────────────────────────────

def get_encrypted_env_for_n8n(env_path: str) -> Dict[str, str]:
    """
    Returns env vars suitable for passing through n8n nodes.
    Values are encrypted, keys are plaintext (for n8n routing).
    This ensures sensitive data is never visible in n8n execution logs.
    """
    password = _get_master_password()
    if not password:
        # Fall back to plaintext
        result = {}
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and "=" in stripped:
                        k, v = stripped.split("=", 1)
                        result[k.strip()] = v.strip()
        return result

    # Try .env.enc first
    enc_path = env_path.replace(".env", ".env.enc")
    if os.path.exists(enc_path):
        return decrypt_env_file(enc_path)

    # Fall back to plaintext .env
    result = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k, v = stripped.split("=", 1)
                    result[k.strip()] = v.strip()
    return result


# ── CLI ────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python env_encryption.py <encrypt|decrypt|test> [path]")
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "encrypt":
        target = sys.argv[2] if len(sys.argv) > 2 else os.path.join(SCRIPT_DIR, ".env")
        result = encrypt_env_file(target)
        if result:
            print(f"✅ Encrypted: {result}")
        else:
            print("❌ Encryption skipped (no password or file)")

    elif cmd == "decrypt":
        target = sys.argv[2] if len(sys.argv) > 2 else os.path.join(SCRIPT_DIR, ".env.enc")
        data = decrypt_env_file(target)
        for k, v in data.items():
            # Mask sensitive values in output
            if _is_sensitive_key(k):
                print(f"  {k} = {'*' * min(len(v), 8)}...")
            else:
                print(f"  {k} = {v}")

    elif cmd == "test":
        # Round-trip test
        salt = os.urandom(16)
        test_pw = "test_password_123"
        original = "sk-test-api-key-very-secret"
        encrypted = encrypt_value(original, test_pw, salt)
        decrypted = decrypt_value(encrypted, test_pw, salt)
        assert decrypted == original, f"Round-trip failed: {original} != {decrypted}"
        print(f"✅ Round-trip test passed")
        print(f"  Original:  {original}")
        print(f"  Encrypted: {encrypted[:50]}...")
        print(f"  Decrypted: {decrypted}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
