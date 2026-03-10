"""
Tunnel Manager — Factory-Level ngrok Coordination
===================================================
Manages ngrok tunnels across all Meta App Factory applications,
preventing port conflicts and providing a single control point.

v2.0 — Added force_reconnect, URL persistence, heartbeat detection.

Usage:
    from utils.tunnel_manager import TunnelManager

    tm = TunnelManager()                   # reads NGROK_AUTH_TOKEN from env
    url = tm.open(port=5009, app_name="Sentinel_Bridge")
    print(url)                             # https://xyz.ngrok-free.dev

    tm.close("Sentinel_Bridge")            # disconnect one
    tm.close_all()                         # shutdown cleanup
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("factory.tunnel_manager")

# Persist tunnel URLs so they survive restarts
_URL_CACHE_FILE = Path(__file__).parent.parent / "data" / "tunnel_urls.json"


class TunnelManager:
    """Coordinates ngrok tunnels across factory apps."""

    def __init__(self, auth_token: str | None = None):
        self._token = auth_token or os.environ.get("NGROK_AUTH_TOKEN", "")
        self._tunnels: dict[str, str] = {}   # app_name → public_url
        self._url_history: dict[str, list[str]] = {}  # app_name → [urls]
        self._initialized = False

    # ── Private helpers ──────────────────────────────────────────

    def _ensure_init(self):
        """Initialize ngrok auth token (once)."""
        if self._initialized:
            return
        if not self._token:
            logger.warning("⚠️ NGROK_AUTH_TOKEN not set — tunnels unavailable")
            return
        try:
            from pyngrok import ngrok
            ngrok.set_auth_token(self._token)
            self._initialized = True
            logger.info("ngrok auth token set")
        except Exception as exc:
            logger.error("ngrok init failed: %s", exc)

    def _kill_port_tunnels(self, port: int):
        """Disconnect any existing tunnel on the given port."""
        try:
            from pyngrok import ngrok
            for tunnel in ngrok.get_tunnels():
                addr = tunnel.config.get("addr", "") if hasattr(tunnel, "config") else ""
                if f"localhost:{port}" in addr or f":{port}" in str(tunnel.public_url):
                    logger.info("Closing existing tunnel for port %d: %s",
                                port, tunnel.public_url)
                    ngrok.disconnect(tunnel.public_url)
        except Exception:
            pass

    def _kill_all_tunnels(self):
        """Kill every ngrok tunnel — nuclear option for stale endpoints."""
        try:
            from pyngrok import ngrok
            tunnels = ngrok.get_tunnels()
            for t in tunnels:
                try:
                    ngrok.disconnect(t.public_url)
                except Exception:
                    pass
            logger.info("Killed %d existing tunnels", len(tunnels))
        except Exception as exc:
            logger.warning("Could not kill tunnels: %s", exc)

    def _save_url(self, app_name: str, url: str):
        """Persist the current URL to disk."""
        try:
            _URL_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            cache = {}
            if _URL_CACHE_FILE.exists():
                cache = json.loads(_URL_CACHE_FILE.read_text())
            cache[app_name] = {
                "url": url,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            _URL_CACHE_FILE.write_text(json.dumps(cache, indent=2))
        except Exception as exc:
            logger.warning("Could not save tunnel URL: %s", exc)

    def _load_url(self, app_name: str) -> str | None:
        """Load last known URL from disk."""
        try:
            if _URL_CACHE_FILE.exists():
                cache = json.loads(_URL_CACHE_FILE.read_text())
                return cache.get(app_name, {}).get("url")
        except Exception:
            pass
        return None

    # ── Public API ───────────────────────────────────────────────

    def open(self, port: int, app_name: str) -> str | None:
        """
        Open an ngrok tunnel for the given app/port.
        Returns the public URL, or None if tunnel failed.
        """
        self._ensure_init()
        if not self._initialized:
            return None

        # Close any existing tunnel on this port
        self._kill_port_tunnels(port)

        try:
            from pyngrok import ngrok
            tunnel = ngrok.connect(port, "http")
            public_url = tunnel.public_url
            self._tunnels[app_name] = public_url
            self._save_url(app_name, public_url)
            logger.info("📱 Tunnel open: %s → localhost:%d (%s)",
                        public_url, port, app_name)
            return public_url
        except Exception as exc:
            logger.warning("⚠️ Tunnel failed for %s (port %d): %s",
                           app_name, port, exc)
            return None

    def force_reconnect(self, port: int, app_name: str) -> str | None:
        """
        Nuclear reconnect: kill ALL tunnels, then open a fresh one.
        Fixes ERR_NGROK_334 'endpoint already online' errors.
        """
        self._ensure_init()
        if not self._initialized:
            return None

        old_url = self._tunnels.get(app_name) or self._load_url(app_name)
        logger.info("🔄 Force-reconnecting tunnel for %s (port %d)…", app_name, port)

        # Kill everything
        self._kill_all_tunnels()

        # Open fresh
        try:
            from pyngrok import ngrok
            tunnel = ngrok.connect(port, "http")
            new_url = tunnel.public_url
            self._tunnels[app_name] = new_url
            self._save_url(app_name, new_url)

            # Track URL change
            if old_url and old_url != new_url:
                self._url_history.setdefault(app_name, []).append(old_url)
                logger.info("📱 URL changed: %s → %s", old_url, new_url)

            logger.info("📱 Tunnel reconnected: %s → localhost:%d (%s)",
                        new_url, port, app_name)
            return new_url
        except Exception as exc:
            logger.error("❌ Force-reconnect failed for %s: %s", app_name, exc)
            return None

    def check_heartbeat(self, app_name: str) -> dict:
        """
        Check if the tunnel is still alive and if the URL has changed.
        Returns { alive, url, changed, old_url }.
        """
        current = self._tunnels.get(app_name)
        saved = self._load_url(app_name)
        alive = current is not None

        # Verify the tunnel is actually alive by checking ngrok API
        if current:
            try:
                from pyngrok import ngrok
                tunnels = ngrok.get_tunnels()
                alive = any(current in t.public_url for t in tunnels)
            except Exception:
                alive = False

        changed = bool(saved and current and saved != current)
        return {
            "alive": alive,
            "url": current,
            "changed": changed,
            "old_url": saved if changed else None,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def close(self, app_name: str):
        """Close the tunnel for a specific app."""
        url = self._tunnels.pop(app_name, None)
        if url:
            try:
                from pyngrok import ngrok
                ngrok.disconnect(url)
                logger.info("Tunnel closed for %s", app_name)
            except Exception:
                pass

    def close_all(self):
        """Close all factory tunnels (shutdown cleanup)."""
        for app_name in list(self._tunnels.keys()):
            self.close(app_name)
        self._kill_all_tunnels()
        logger.info("All tunnels closed")

    def get_url(self, app_name: str) -> str | None:
        """Get the current public URL for an app, or None if no tunnel."""
        url = self._tunnels.get(app_name)
        if not url:
            # Fallback: check persisted URL
            url = self._load_url(app_name)
        return url

    @property
    def active_tunnels(self) -> dict[str, str]:
        """Returns {app_name: public_url} for all active tunnels."""
        return dict(self._tunnels)

    @property
    def available(self) -> bool:
        """Whether ngrok is configured and available."""
        return bool(self._token)
