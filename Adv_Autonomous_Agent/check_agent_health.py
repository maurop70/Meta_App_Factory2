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
import os
import json

# Add project root to path to import bridge
PROJECT_DIR = r"C:\Users\mpetr\My Drive\Antigravity-AI Agents\Meta_App_Factory\Adv_Autonomous_Agent"
if PROJECT_DIR not in sys.path: sys.path.append(PROJECT_DIR)

try:
    from bridge import AGENT_REGISTRY
except ImportError:
    # Fallback if bridge.py import fails (e.g. env vars)
    print("Could not import AGENT_REGISTRY directly. Using hardcoded backup for check.")
    AGENT_REGISTRY = {
        "CFO": "https://humanresource.app.n8n.cloud/webhook/cfo", 
        "CMO": "https://humanresource.app.n8n.cloud/webhook/cmo",
        "HR": "https://humanresource.app.n8n.cloud/webhook/hr",
        "CRITIC": "https://humanresource.app.n8n.cloud/webhook/critic",
        "PITCH": "https://humanresource.app.n8n.cloud/webhook/pitch",
        "ATOMIZER": "https://humanresource.app.n8n.cloud/webhook/atomizer-v2",
        "ARCHITECT": "https://humanresource.app.n8n.cloud/webhook/architect"
    }

print("--- AGENT HEALTH CHECK (DCC DIAGNOSTIC) ---")
print(f"Scanning {len(AGENT_REGISTRY)} Neural Nodes...\n")

active_count = 0
for role, url in AGENT_REGISTRY.items():
    if "role=" in url:
        # Skip fallbacks/routers for now, focus on dedicated
        # print(f"⚪ {role}: Routing Check (Shared Endpoint)")
        continue
        
    print(f"Ping: {role}...", end=" ")
    try:
        # Send a harmless 'health_check' prompt
        # We use a short timeout because we just want to know if it's hitting a 404 or 500
        # A 200 active response is good.
        _v3_status = healed_post(url, {"prompt": "PING (Health Check)

        resp = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()"}, timeout=5)
        
        if resp.status_code == 200:
            print("[OK] ONLINE")
            active_count += 1
        else:
            print(f"[FAIL] ERROR ({resp.status_code})")
            # print(f"   {resp.text[:100]}")
            
    except Exception as e:
        print(f"[WARN] UNREACHABLE: {e}")

print("-" * 30)
print(f"SYSTEM STATUS: {active_count}/{len([k for k,v in AGENT_REGISTRY.items() if 'role=' not in v])} Dedicated Agents Online.")

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
