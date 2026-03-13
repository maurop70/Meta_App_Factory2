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

# Add skills to path
SKILLS_DIR = r"C:\Users\mpetr\.gemini\antigravity\skills"
if SKILLS_DIR not in sys.path: sys.path.append(SKILLS_DIR)

try:
    from n8n_architect.architect import N8NArchitect
    arch = N8NArchitect()
    
    print("--- Fetching Workflows ---")
    workflows = arch.list_workflows()
    
    specialists = ["CFO", "CMO", "HR", "Product", "Sales", "Architect", "Analyst"]
    found = {}
    
    for wf in workflows:
        name = wf.get("name", "")
        print(f"Workflow: {name} (ID: {wf.get('id')}, Active: {wf.get('active')})")
        
        # Check if this workflow IS a specialist agent
        for role in specialists:
            if role.lower() in name.lower():
                found[role] = wf
                
        # Also check nodes inside? The architect list_workflows might not return nodes.
        # We might need to get_workflow(id)
        
    print("\n--- Detailed Inspection ---")
    # If we found dedicated workflows, great. 
    # If not, let's look at the 'Elite Council' workflow for multiple webhooks?
    
    # We'll just dump what we found for now.
    print(json.dumps(found, indent=2, default=str))

except Exception as e:
    print(f"Error: {e}")
# V3 AUTO-HEAL ACTIVE
