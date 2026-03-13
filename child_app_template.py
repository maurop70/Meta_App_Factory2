"""
child_app_template.py — V3.0 Resilience-Inherited Child App Template
═════════════════════════════════════════════════════════════════════
This is the standard boilerplate for every Antigravity child agent.
It inherits 100% of the Hardened V3.0 architecture:

  • Antigravity_Full_v2 API key — inherited automatically via
    the factory's .env access. Child apps NEVER handle raw keys.

  • StateManager — every outgoing call is logged with a UUID +
    timestamp in local_pending_sync.json BEFORE the HTTP POST.

  • Safe-Buffer mode — if n8n Cloud is unreachable, payloads
    are queued to pending_sync/ and the Recovery Sync Engine
    (recovery_sync.py) delivers them when connectivity returns.

  • Watchdog preflight — cloud health is validated before any
    data-heavy operation via the Resonance_Watchdog_V3 ping
    (ID: Ap8cp7Q5jkcmCKmd).

Usage:
    1. Copy this file and rename to your agent's name.
    2. Implement your logic in the execute() function.
    3. Run:  python my_agent.py

Author: Antigravity Ops Intelligence
Framework: V3.0 Resilience Inheritance
"""

import os
import sys
import json

# ── Resolve paths relative to Meta_App_Factory ──────────────
# This ensures all child apps, regardless of where they're run,
# can find factory.py, local_state_manager.py, and .env.
FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, FACTORY_DIR)

# ── Import the V3.0 Hardened Factory ────────────────────────
# The factory module auto-loads the .env file, giving this app
# access to Antigravity_Full_v2 (N8N_API_KEY), GEMINI_API_KEY,
# and all other credentials without ever exposing raw keys.
from factory import safe_post                       # V3 Safe-Post pattern
from local_state_manager import StateManager        # UUID + state tracking

# ── Initialize State ────────────────────────────────────────
sm = StateManager()


# ═══════════════════════════════════════════════════════════
#  PREFLIGHT CHECK — Call before any data-heavy operation
# ═══════════════════════════════════════════════════════════

def preflight() -> bool:
    """
    Validate cloud health by pinging the Resonance_Watchdog_V3
    (ID: Ap8cp7Q5jkcmCKmd) before any heavy work.

    Returns True if healthy, False if unreachable.
    """
    import requests

    # Load watchdog URL from resilience config
    cfg_path = os.path.join(FACTORY_DIR, "resilience_config.json")
    if not os.path.exists(cfg_path):
        print("⚠️ resilience_config.json not found — skipping preflight")
        return True

    with open(cfg_path) as f:
        cfg = json.load(f)

    url = cfg.get("cloud_health", {}).get("watchdog_url", "")
    if not url:
        return True

    try:
        r = requests.get(url, timeout=5)
        latency = r.elapsed.total_seconds() * 1000
        healthy = r.status_code == 200
        icon = "🟢" if healthy else "🔴"
        print(f"  Preflight: {icon} Watchdog {r.status_code} ({latency:.0f}ms)")
        return healthy
    except Exception as e:
        print(f"  Preflight: 🔴 Watchdog UNREACHABLE ({e})")
        return False


# ═══════════════════════════════════════════════════════════
#  EXECUTE — Your agent logic goes here
# ═══════════════════════════════════════════════════════════

def execute():
    """
    Main agent logic. Replace this with your workflow.

    The safe_post() function handles the full V3 lifecycle:
      1. Log to StateStore (UUID + timestamp)
      2. Preflight Watchdog check
      3. Attempt POST to n8n target
      4. Mark result (sent / buffered / failed)

    If the cloud is down, the payload is automatically queued
    to pending_sync/ and the Recovery Sync Engine (recovery_sync.py)
    will deliver it when connectivity returns.
    """

    # ── Step 1: Preflight ────────────────────────────────
    if not preflight():
        print("  ⚠️ Cloud is unhealthy — proceeding in Safe-Buffer mode.")
        # The safe_post function will auto-buffer if needed.

    # ── Step 2: Build your payload ───────────────────────
    # Replace this with your actual data / AI output.
    target_url = "https://humanresource.app.n8n.cloud/webhook/YOUR-WEBHOOK-PATH"
    payload = {
        "agent": "child_app_template",
        "action": "example_action",
        "data": {
            "message": "Hello from a V3.0 Hardened child app",
            "timestamp": __import__('datetime').datetime.now().isoformat(),
        }
    }

    # ── Step 3: Safe-Post (the V3 pattern) ───────────────
    # Logic: Log to StateStore -> Attempt Post -> Mark Result
    status = safe_post(target_url, payload, project="ChildApp_Example")

    if status == "sent":
        print("  ✅ Payload delivered to n8n Cloud.")
    elif status == "buffered":
        print("  ⚠️ Cloud lag detected. Data secured in local_pending_sync.json")
        print("     Recovery Sync Engine will deliver when cloud recovers.")
    elif status == "failed":
        print("  ❌ n8n returned a server error (5xx).")
        print("     Entry logged — run `python recovery_sync.py --force` to retry.")

    # ── Step 4: Check State ──────────────────────────────
    stats = sm.get_stats()
    print(f"\n  State: {stats['sent']} sent, {stats['pending']} pending, "
          f"{stats['failed']} failed, buffer={'ON' if stats['safe_buffer_mode'] else 'OFF'}")


# ═══════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  🚀 V3.0 Hardened Child App — Template")
    print(f"{'='*60}\n")

    execute()

    print(f"\n{'='*60}\n")
