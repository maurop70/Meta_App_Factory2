"""
Sentinel Bridge — First-Run Configuration Wizard
==================================================
Interactive setup for:
1. Google Calendar OAuth tokens
2. ntfy topic/server configuration
3. Fernet vault initialization
4. Test notification

Run: python sentinel_config.py
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


import sys
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fernet_vault import FernetVault
from notification_dispatcher import NotificationDispatcher

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("sentinel.config")


def banner():
    print("""
╔══════════════════════════════════════════════════════════╗
║           🛡️  SENTINEL BRIDGE — SETUP WIZARD  🛡️         ║
║                                                          ║
║  Autonomous Reminder System                              ║
║  Meta App Factory · Aether Layer                         ║
╚══════════════════════════════════════════════════════════╝
""")


def setup_ntfy(vault: FernetVault):
    print("\n── 📲 ntfy Configuration ──────────────────────────────")
    print("  Sentinel pushes notifications via ntfy.sh.")
    print("  Default server: https://ntfy.sh")
    print("  Default topic:  sentinel_mauro_private\n")

    server = input("  ntfy server URL [https://ntfy.sh]: ").strip()
    if not server:
        server = "https://ntfy.sh"
    vault.store("ntfy_server", server)

    topic = input("  ntfy topic [sentinel_mauro_private]: ").strip()
    if not topic:
        topic = "sentinel_mauro_private"
    vault.store("ntfy_topic", topic)

    print(f"  ✅ ntfy configured: {server}/{topic}")


def setup_google_calendar(vault: FernetVault):
    print("\n── 📅 Google Calendar Configuration ──────────────────")
    print("  To sync calendars, you need a Google OAuth token.")
    print("  Accounts:")
    print("    1. mpetrini@heinleinfoodsusa.com (Work)")
    print("    2. mauro@gelatopetrini.com (Personal)")
    print("")
    print("  📝 For now, Sentinel will use demo events.")
    print("  To enable real calendar sync:")
    print("    1. Create a Google Cloud project with Calendar API")
    print("    2. Generate OAuth 2.0 credentials")
    print("    3. Store tokens via: POST /api/vault/store")
    print("")

    proceed = input("  Set up Google Calendar now? [y/N]: ").strip().lower()
    if proceed == "y":
        print("\n  Paste your OAuth access token for Work account:")
        work_token = input("  Token (or Enter to skip): ").strip()
        if work_token:
            vault.store("google_token_work", work_token)
            print("  ✅ Work token stored.")

        print("\n  Paste your OAuth access token for Personal account:")
        personal_token = input("  Token (or Enter to skip): ").strip()
        if personal_token:
            vault.store("google_token_personal", personal_token)
            print("  ✅ Personal token stored.")
    else:
        print("  ⏭️  Skipped. Demo events will be used.")


def setup_api_base(vault: FernetVault):
    print("\n── 🌐 API Base URL ───────────────────────────────────")
    api_base = input("  API base URL [http://localhost:5009]: ").strip()
    if not api_base:
        api_base = "http://localhost:5009"
    vault.store("sentinel_api_base", api_base)
    print(f"  ✅ API base: {api_base}")


async def test_notification(vault: FernetVault):
    print("\n── 🔔 Test Notification ──────────────────────────────")
    send_test = input("  Send a test notification? [Y/n]: ").strip().lower()
    if send_test != "n":
        disp = NotificationDispatcher(vault=vault)
        result = await disp.send_test()
        if result.get("status") == "delivered":
            print("  ✅ Test notification sent! Check your phone.")
        else:
            print(f"  ❌ Test failed: {result.get('error', 'unknown')}")
            print("     Make sure you're subscribed to the ntfy topic.")


def main():
    banner()

    vault = FernetVault()
    print("  🔐 Fernet vault initialized.\n")
    print(f"  Vault keys: {vault.list_keys()}")

    setup_ntfy(vault)
    setup_google_calendar(vault)
    setup_api_base(vault)

    asyncio.run(test_notification(vault))

    print("""
╔══════════════════════════════════════════════════════════╗
║                    ✅ SETUP COMPLETE                     ║
║                                                          ║
║  Launch Sentinel Bridge:                                 ║
║    python sentinel_server.py                             ║
║    — or —                                                ║
║    launch_sentinel.bat                                   ║
║                                                          ║
║  Dashboard: http://localhost:5009                        ║
║  ntfy topic: Subscribe on your phone to receive alerts   ║
╚══════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    main()
# V3 AUTO-HEAL ACTIVE
