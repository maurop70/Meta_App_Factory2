"""
N8N Workflow Lifecycle Manager — Antigravity
Activates/deactivates N8N workflows per-app on launch/shutdown.
Usage:
    python n8n_lifecycle.py activate alpha
    python n8n_lifecycle.py deactivate alpha
    python n8n_lifecycle.py activate meta
    python n8n_lifecycle.py deactivate meta
    python n8n_lifecycle.py deactivate all       # emergency kill-all
"""
import os, sys, json, requests, time

# Force UTF-8 output on Windows (cp1252 can't handle emoji)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Config ──────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
N8N_BASE   = "https://humanresource.app.n8n.cloud/api/v1"

# V2.0 Vault integration
try:
    sys.path.insert(0, SCRIPT_DIR)
    from vault_client import get_secret as _vault_get
except ImportError:
    _vault_get = None

def _get_api_key():
    """Load N8N_API_KEY from vault, then .env or environment."""
    # 1. Try vault
    if _vault_get:
        val = _vault_get("N8N_API_KEY")
        if val:
            return val
    # 2. Try environment
    key = os.getenv("N8N_API_KEY")
    if key:
        return key
    # 3. Try loading from .env in same directory
    env_path = os.path.join(SCRIPT_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if line.strip().startswith("N8N_API_KEY="):
                    return line.strip().split("=", 1)[1]
    return None

# ── Workflow Registry ───────────────────────────────────────────
# Alpha V2 Genesis workflows
ALPHA_WORKFLOWS = {
    "VkE0dmwynRPMIyjdmiONL": "Alpha_V2_Macro_Event_Tracker",
    "Q36ImsxRy4by47kw":      "Alpha Architect - Genesis (v3)",
    "tbQnSD6n9JHHvZ3D":      "Alpha Ledger Daily Cron",
    "S8KVkRMA56B21MXs":      "Alpha Architect - Research (v2 Robust)",
    "nQ8DLY23Q8Dm2dc8":      "Alpha Phase 3 Logic (Push Mode)",
    "Z99Py4WeaUHry8pj":      "Alpha Architect - Research (Universal Linear)",
}

# Meta App Factory workflows
META_WORKFLOWS = {
    "KsWSsAFyOxyt2yud":     "Claude Executor (Triad Protocol)",
    "1JjyTk5VwmBItQvG":     "Gemini Agent Bridge",
    "rx4DvnQ5BOVFri5w":     "Antigravity Ops Intelligence",
    "JlEXsH2MbzBx15Mk":    "Claude Code Executor",
    "noQvg47G_QUjwBjWN7Gfs": "System - Drive Manager",
    "V02GhFXscGo4ClZCngBJb": "Elite Council v2.2 (Legacy)",
    "I1vS9bPieuXVjbTe":     "Specialist - Pitch Director (V2)",
    "GDXZMERlXQke9U80":     "Specialist - Architect (V2)",
    "MaMZwBjp2mMB27l0":     "System - Atomizer V2",
}

APP_GROUPS = {
    "alpha": ALPHA_WORKFLOWS,
    "meta":  META_WORKFLOWS,
    "all":   {**ALPHA_WORKFLOWS, **META_WORKFLOWS},
}

# ── API Functions ───────────────────────────────────────────────
def set_workflow_active(workflow_id, active: bool, api_key: str, name: str = ""):
    """Activate or deactivate a single N8N workflow."""
    url = f"{N8N_BASE}/workflows/{workflow_id}/{'activate' if active else 'deactivate'}"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, timeout=10)
        verb = "ACTIVATED" if active else "DEACTIVATED"
        if resp.status_code == 200:
            print(f"  ✅ {verb}: {name or workflow_id}")
            return True
        else:
            print(f"  ❌ Failed to {verb.lower()} {name or workflow_id}: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"  ⚠️  Error for {name or workflow_id}: {e}")
        return False


def manage_workflows(group_name: str, activate: bool):
    """Activate or deactivate all workflows in a named group."""
    api_key = _get_api_key()
    if not api_key:
        print("❌ N8N_API_KEY not found. Cannot manage workflows.")
        return False

    workflows = APP_GROUPS.get(group_name)
    if not workflows:
        print(f"❌ Unknown group: {group_name}. Valid: {', '.join(APP_GROUPS.keys())}")
        return False

    action = "Activating" if activate else "Deactivating"
    print(f"\n🔧 {action} {len(workflows)} {group_name.upper()} workflows...")
    print("-" * 50)

    success = 0
    for wf_id, wf_name in workflows.items():
        if set_workflow_active(wf_id, activate, api_key, wf_name):
            success += 1
        time.sleep(0.3)  # Rate limit courtesy

    total = len(workflows)
    status = "✅" if success == total else "⚠️"
    print(f"\n{status} {success}/{total} workflows {'activated' if activate else 'deactivated'}.")
    return success == total


# ── Graceful Shutdown Handler ───────────────────────────────────
_shutdown_registered = False
_shutdown_group = None
_shutdown_workflow_id = None

def _shutdown_callback():
    """Called on process exit — deactivates N8N workflows."""
    if _shutdown_group:
        print(f"\n🛑 Shutdown detected — deactivating {_shutdown_group.upper()} workflows...")
        manage_workflows(_shutdown_group, activate=False)
    elif _shutdown_workflow_id:
        api_key = _get_api_key()
        if api_key:
            print(f"\n🛑 Shutdown detected — deactivating workflow...")
            set_workflow_active(_shutdown_workflow_id, False, api_key, "app workflow")

def _signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM gracefully."""
    print(f"\n🛑 Signal {signum} received — cleaning up...")
    _shutdown_callback()
    sys.exit(0)

def register_shutdown_hook(group_name=None, workflow_id=None):
    """
    Register atexit + signal handlers to deactivate workflows on exit.
    Call this once at app startup:
        register_shutdown_hook('alpha')          # For group-managed apps
        register_shutdown_hook(workflow_id='xx') # For single-workflow apps
    """
    global _shutdown_registered, _shutdown_group, _shutdown_workflow_id

    if _shutdown_registered:
        return  # Already registered

    _shutdown_group = group_name
    _shutdown_workflow_id = workflow_id

    # 1. Python atexit (runs on normal exit and unhandled exceptions)
    import atexit
    atexit.register(_shutdown_callback)

    # 2. Signal handlers (SIGINT = Ctrl+C, SIGTERM = kill)
    import signal
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # 3. Windows-specific: Catch console close event (X button)
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
            def _console_handler(event):
                # Events: 0=CTRL_C, 1=CTRL_BREAK, 2=CLOSE, 5=LOGOFF, 6=SHUTDOWN
                if event in (2, 5, 6):
                    _shutdown_callback()
                    return True
                return False

            kernel32.SetConsoleCtrlHandler(_console_handler, True)
        except Exception:
            pass  # Non-critical if ctypes fails

    _shutdown_registered = True
    label = group_name.upper() if group_name else workflow_id or "unknown"
    print(f"  🛡️  Shutdown hook registered for: {label}")


# ── CLI Entry Point ─────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python n8n_lifecycle.py <activate|deactivate> <alpha|meta|all>")
        sys.exit(1)

    action = sys.argv[1].lower()
    group  = sys.argv[2].lower()

    if action not in ("activate", "deactivate"):
        print(f"❌ Invalid action: {action}. Use 'activate' or 'deactivate'.")
        sys.exit(1)

    # Load .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
    except ImportError:
        pass

    ok = manage_workflows(group, activate=(action == "activate"))
    sys.exit(0 if ok else 1)

