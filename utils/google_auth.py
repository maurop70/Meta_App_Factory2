"""
Google OAuth 2.0 — Factory-Level Shared Module
================================================
Reusable Google OAuth class for any Meta App Factory application.
Handles authorization URL generation, code exchange, token storage,
and automatic token refresh via the Fernet vault.

Usage:
    from utils.google_auth import GoogleAuth

    auth = GoogleAuth(
        vault=vault_instance,
        client_id_key="google_client_id",
        client_secret_key="google_client_secret",
        scopes=["https://www.googleapis.com/auth/calendar.events"],
        redirect_uri="http://localhost:5009/api/auth/google/callback",
    )

    # 1. Get auth URL  →  redirect user
    url = auth.get_auth_url(account_id="work")

    # 2. Exchange auth code  →  stores tokens in vault
    await auth.exchange_code(code, account_id="work")

    # 3. Retrieve valid token (auto-refreshes if expired)
    token = await auth.get_valid_token(account_id="work")
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


import logging

logger = logging.getLogger("factory.google_auth")


class GoogleAuth:
    """Reusable Google OAuth 2.0 Web Application flow."""

    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

    def __init__(self, vault, client_id_key: str, client_secret_key: str,
                 scopes: list[str], redirect_uri: str):
        self.vault = vault
        self.client_id_key = client_id_key
        self.client_secret_key = client_secret_key
        self.scopes = scopes
        self.redirect_uri = redirect_uri

    # ── Helpers ──────────────────────────────────────────────────
    @property
    def client_id(self) -> str:
        return self.vault.retrieve(self.client_id_key) or ""

    @property
    def client_secret(self) -> str:
        return self.vault.retrieve(self.client_secret_key) or ""

    def _token_key(self, account_id: str) -> str:
        return f"google_token_{account_id}"

    def _refresh_key(self, account_id: str) -> str:
        return f"google_refresh_{account_id}"

    # ── 1. Generate authorization URL ────────────────────────────
    def get_auth_url(self, account_id: str) -> str:
        """Build the Google OAuth consent screen URL."""
        import urllib.parse
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "offline",
            "prompt": "consent",
            "state": account_id,
        }
        url = f"{self.GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
        logger.info("OAuth: auth URL generated for '%s'", account_id)
        return url

    # ── 2. Exchange authorization code for tokens ────────────────
    async def exchange_code(self, code: str, account_id: str) -> dict:
        """Exchange auth code for access + refresh tokens, store in vault."""
        import httpx

        payload = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }

        logger.info("OAuth: exchanging code for '%s'", account_id)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(self.GOOGLE_TOKEN_URL, data=payload)

        if resp.status_code != 200:
            error_detail = resp.text[:300]
            logger.error("OAuth token exchange failed (HTTP %d): %s",
                         resp.status_code, error_detail)
            raise RuntimeError(f"Token exchange failed: {error_detail}")

        tokens = resp.json()
        self.vault.store(self._token_key(account_id), tokens["access_token"])
        if "refresh_token" in tokens:
            self.vault.store(self._refresh_key(account_id), tokens["refresh_token"])

        logger.info("✅ OAuth: '%s' authorized successfully", account_id)
        return tokens

    # ── 3. Get valid token (auto-refresh) ────────────────────────
    async def get_valid_token(self, account_id: str) -> str | None:
        """Return a valid access token, refreshing if needed."""
        token = self.vault.retrieve(self._token_key(account_id))
        if not token:
            return None

        # Try the token — if it fails with 401, refresh it
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            test = await client.get(
                "https://www.googleapis.com/oauth2/v1/tokeninfo",
                params={"access_token": token},
            )

        if test.status_code == 200:
            return token

        # Token expired → refresh
        return await self._refresh_token(account_id)

    async def _refresh_token(self, account_id: str) -> str | None:
        """Refresh an expired access token using the stored refresh token."""
        refresh = self.vault.retrieve(self._refresh_key(account_id))
        if not refresh:
            logger.warning("No refresh token for '%s' — re-auth required", account_id)
            return None

        import httpx
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(self.GOOGLE_TOKEN_URL, data=payload)

        if resp.status_code != 200:
            logger.error("Token refresh failed for '%s': %s",
                         account_id, resp.text[:200])
            return None

        new_token = resp.json()["access_token"]
        self.vault.store(self._token_key(account_id), new_token)
        logger.info("🔄 Token refreshed for '%s'", account_id)
        return new_token

    # ── 4. Auth status check ─────────────────────────────────────
    def get_status(self, accounts: list[dict]) -> dict:
        """
        Check authorization status for a list of accounts.
        Each account dict should have 'id' and 'email' keys.
        Returns: {"accounts": {id: {email, authorized}}}
        """
        result = {}
        for acc in accounts:
            aid = acc["id"]
            token = self.vault.retrieve(self._token_key(aid))
            result[aid] = {
                "email": acc["email"],
                "authorized": token is not None,
            }
        return {"accounts": result}
# V3 AUTO-HEAL ACTIVE
