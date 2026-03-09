"""
Tunnel Manager — Factory-Level ngrok Coordination
===================================================
Manages ngrok tunnels across all Meta App Factory applications,
preventing port conflicts and providing a single control point.

Usage:
    from utils.tunnel_manager import TunnelManager

    tm = TunnelManager()                   # reads NGROK_AUTH_TOKEN from env
    url = tm.open(port=5009, app_name="Sentinel_Bridge")
    print(url)                             # https://xyz.ngrok-free.dev

    tm.close("Sentinel_Bridge")            # disconnect one
    tm.close_all()                         # shutdown cleanup
"""

import os
import logging

logger = logging.getLogger("factory.tunnel_manager")


class TunnelManager:
    """Coordinates ngrok tunnels across factory apps."""

    def __init__(self, auth_token: str | None = None):
        self._token = auth_token or os.environ.get("NGROK_AUTH_TOKEN", "")
        self._tunnels: dict[str, str] = {}   # app_name → public_url
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
                if f"localhost:{port}" in tunnel.config.get("addr", ""):
                    logger.info("Closing existing tunnel for port %d: %s",
                                port, tunnel.public_url)
                    ngrok.disconnect(tunnel.public_url)
        except Exception:
            pass

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
            logger.info("📱 Tunnel open: %s → localhost:%d (%s)",
                        public_url, port, app_name)
            return public_url
        except Exception as exc:
            logger.warning("⚠️ Tunnel failed for %s (port %d): %s",
                           app_name, port, exc)
            return None

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
        # Kill any orphaned ngrok processes
        try:
            from pyngrok import ngrok
            for tunnel in ngrok.get_tunnels():
                ngrok.disconnect(tunnel.public_url)
        except Exception:
            pass
        logger.info("All tunnels closed")

    def get_url(self, app_name: str) -> str | None:
        """Get the current public URL for an app, or None if no tunnel."""
        return self._tunnels.get(app_name)

    @property
    def active_tunnels(self) -> dict[str, str]:
        """Returns {app_name: public_url} for all active tunnels."""
        return dict(self._tunnels)

    @property
    def available(self) -> bool:
        """Whether ngrok is configured and available."""
        return bool(self._token)
