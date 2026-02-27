"""
Antigravity Vault Client — Programmatic API for Alpha V2 Genesis
================================================================
Provides get_secret() and get_secrets() for Alpha Python modules to
retrieve keys from the encrypted vault instead of plaintext .env.

Usage:
    from vault_client import get_secret
    api_key = get_secret("N8N_API_KEY")

Fallback chain:
    1. Vault (vault.enc) — preferred, encrypted
    2. Environment variable — for backward compatibility
    3. .env file parse — legacy fallback

The master password is read from VAULT_PASSWORD env var or prompted once.
"""
import os, sys, json, base64, hashlib

# ── Vault location (same as vault.py) ──
VAULT_PATH = os.path.join(
    os.path.expanduser("~"),
    "My Drive (maurotgs@gmail.com)",
    "Antigravity-AI Agents",
    ".system_core",
    "vault.enc",
)
SALT_PATH = VAULT_PATH + ".salt"

# Cache for decrypted vault data (loaded once per process)
_vault_cache = None
_vault_loaded = False


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a Fernet key from a password using PBKDF2."""
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def _load_vault_data(password: str) -> dict:
    """Load and decrypt the vault. Returns dict of secrets."""
    global _vault_cache, _vault_loaded

    if _vault_loaded:
        return _vault_cache or {}

    if not os.path.exists(VAULT_PATH) or not os.path.exists(SALT_PATH):
        _vault_loaded = True
        _vault_cache = {}
        return {}

    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ImportError:
        # cryptography not installed — fall through to env vars
        _vault_loaded = True
        _vault_cache = {}
        return {}

    with open(SALT_PATH, "rb") as f:
        salt = f.read()

    key = _derive_key(password, salt)
    fernet = Fernet(key)

    with open(VAULT_PATH, "rb") as f:
        encrypted = f.read()

    try:
        decrypted = fernet.decrypt(encrypted)
        _vault_cache = json.loads(decrypted.decode())
    except (InvalidToken, json.JSONDecodeError):
        _vault_cache = {}

    _vault_loaded = True
    return _vault_cache


def _get_vault_password() -> str:
    """Get the vault master password from env or prompt."""
    pw = os.getenv("VAULT_PASSWORD", "")
    if not pw:
        # Try to read from a local .vault_pw file (gitignored)
        pw_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".vault_pw")
        if os.path.exists(pw_file):
            with open(pw_file, "r") as f:
                pw = f.read().strip()
    return pw


def _parse_env_file(env_path: str) -> dict:
    """Parse a .env file into a dict (legacy fallback)."""
    result = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    result[k.strip()] = v.strip()
    return result


def get_secret(key: str, default: str = "", env_path: str = None) -> str:
    """
    Retrieve a secret with vault-first fallback chain.

    Priority:
        1. Encrypted vault (vault.enc)
        2. Environment variable
        3. .env file (legacy)
        4. Default value

    Args:
        key: The secret key name (e.g., "N8N_API_KEY")
        default: Default value if key not found anywhere
        env_path: Optional path to .env file for legacy fallback
    """
    # 1. Try vault
    pw = _get_vault_password()
    if pw:
        vault_data = _load_vault_data(pw)
        if key in vault_data:
            entry = vault_data[key]
            if isinstance(entry, dict):
                return entry.get("value", default)
            return str(entry)

    # 2. Try environment variable
    env_val = os.getenv(key)
    if env_val:
        return env_val

    # 3. Try .env file (legacy fallback)
    if env_path:
        env_data = _parse_env_file(env_path)
        if key in env_data:
            return env_data[key]

    # 4. Auto-detect .env in common locations
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for candidate in [
        os.path.join(script_dir, ".env"),
        os.path.join(script_dir, "..", ".env"),
    ]:
        if os.path.exists(candidate):
            env_data = _parse_env_file(candidate)
            if key in env_data:
                return env_data[key]

    return default


def get_secrets(*keys: str, env_path: str = None) -> dict:
    """Retrieve multiple secrets at once. Returns {key: value} dict."""
    return {k: get_secret(k, env_path=env_path) for k in keys}
