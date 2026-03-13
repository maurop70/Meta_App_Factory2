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


import os
import sys
import subprocess

def create_shortcut():
    """
    Creates a Desktop shortcut for start_cloud_terminal.bat using VBScript.
    This method is used to avoid dependencies like pywin32 or winshell.
    """
    # 1. Configuration
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    BATCH_FILE = os.path.join(SCRIPT_DIR, "start_cloud_terminal.bat")
    ICON_FILE = os.path.join(SCRIPT_DIR, "app.ico")
    LINK_NAME = "Adv Agent (Cloud).lnk"
    
    # Resolve Desktop Path
    candidates = [
        os.path.join(os.environ["USERPROFILE"], "Desktop"),
        os.path.join(os.environ["USERPROFILE"], "OneDrive", "Desktop"),
        os.path.join(os.environ["USERPROFILE"], "OneDrive - Gelato Petrini", "Desktop")
    ]
    
    desktop_path = None
    for path in candidates:
        if os.path.exists(path):
            desktop_path = path
            break
            
    if not desktop_path:
        print("ERROR: Could not locate Desktop folder.")
        return
    
    link_path = os.path.join(desktop_path, LINK_NAME)

    print(f"--- Creating Shortcut ---")
    print(f"Target: {BATCH_FILE}")
    print(f"Start In: {SCRIPT_DIR}")
    print(f"Dest:   {link_path}")

    if not os.path.exists(BATCH_FILE):
        print(f"ERROR: {BATCH_FILE} not found!")
        return

    # 2. VBScript Generation
    vbs_content = f"""
    Set oWS = WScript.CreateObject("WScript.Shell")
    sLinkFile = "{link_path}"
    Set oLink = oWS.CreateShortcut(sLinkFile)
    oLink.TargetPath = "{BATCH_FILE}"
    oLink.WorkingDirectory = "{SCRIPT_DIR}"
    oLink.Description = "Launch Adv_Autonomous_Agent (Cloud Mode)"
    """
    
    if os.path.exists(ICON_FILE):
        print(f"Icon:   Found app.ico")
        vbs_content += f'\noLink.IconLocation = "{ICON_FILE}"'
    else:
        print(f"Icon:   Default (app.ico not found)")

    vbs_content += "\noLink.Save"

    # Write Temp VBS
    vbs_path = os.path.join(SCRIPT_DIR, "temp_create_shortcut.vbs")
    try:
        with open(vbs_path, "w") as f:
            f.write(vbs_content)
        
        # 3. Execute VBS
        subprocess.run(["cscript", "//Nologo", vbs_path], check=True)
        print(f"\n[SUCCESS] Shortcut created on Desktop: {LINK_NAME}")
        
    except Exception as e:
        print(f"\n[ERROR] Failed to create shortcut: {e}")
    finally:
        # Cleanup
        if os.path.exists(vbs_path):
            os.remove(vbs_path)

if __name__ == "__main__":
    create_shortcut()
    print("\nYou can now close this window.")
    try:
        input("Press Enter to exit...")
    except:
        pass
# V3 AUTO-HEAL ACTIVE
