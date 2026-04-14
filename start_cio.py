"""
start_cio.py — CIO Agent Launcher
═══════════════════════════════════════════════════════════════
Run this from the Meta_App_Factory root OR from CIO_Agent/ to
launch the Chief Innovation Officer on port 5090.

Usage:
    python start_cio.py                  # from Meta_App_Factory root
    python CIO_Agent/start_cio.py        # from workspace root

Sets up correct sys.path so cio_engine can resolve:
  - agent_base.py      (Meta_App_Factory root)
  - ai_utils.py        (Meta_App_Factory root)
"""

import sys
import os
from pathlib import Path

# ── Resolve paths ──────────────────────────────────────────────────────────
CIO_DIR      = Path(__file__).parent / "CIO_Agent"
FACTORY_ROOT = Path(__file__).parent

# Ensure Meta_App_Factory root is on sys.path (for agent_base, ai_utils)
for p in [str(FACTORY_ROOT), str(CIO_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ── Load .env ──────────────────────────────────────────────────────────────
from dotenv import load_dotenv
for env in [FACTORY_ROOT / ".env", CIO_DIR / ".env"]:
    if env.exists():
        load_dotenv(env)
        break

# ── Validate GEMINI_API_KEY ────────────────────────────────────────────────
if not os.environ.get("GEMINI_API_KEY"):
    print("[CIO Launcher] ERROR: GEMINI_API_KEY not set in .env — CIO agent requires it for intelligence sweeps.")
    sys.exit(1)

# ── Launch ─────────────────────────────────────────────────────────────────
import uvicorn

print("=" * 60)
print("  CIO Agent — Chief Innovation Officer")
print("  Port 5090 | Gemini 2.5 Pro | UDPP Enforced")
print("  24-hour autonomous intelligence sweep loop: ACTIVE")
print("  Dashboard: http://localhost:5090")
print("=" * 60)

# Change to CIO_Agent dir so server.py imports work correctly
os.chdir(CIO_DIR)
sys.path.insert(0, str(CIO_DIR))

uvicorn.run(
    "server:app",
    host="0.0.0.0",
    port=5090,
    reload=False,  # reload=False for production; set True for dev
    log_level="info",
)
