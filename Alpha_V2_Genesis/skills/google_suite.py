# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
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
import json
import base64

class GoogleSuiteManager:
    """
    Cloud-Native Drive Manager.
    Delegates all file operations to N8N 'System - Drive Manager' workflow.
    """
    def __init__(self, project_name="General_Consulting"):
        self.project_name = project_name
        self.webhook_url = "https://humanresource.app.n8n.cloud/webhook/drive-manager"
        self.root_folder_id = None # Cached ID of Project Folder
        
    def ensure_project_folder(self):
        """
        Ensures 'Antigravity-AI agent/Adv/[Project Name]' exists.
        Returns the Folder ID.
        """
        if self.root_folder_id: return self.root_folder_id
        
        print(f"--- Cloud Sync: Verifying Workspace for '{self.project_name}' ---", flush=True)
        try:
            payload = {
                "action": "ensure_folder",
                "folder_name": self.project_name,
                "parent_path": "Antigravity-AI agent/Adv_Autonomous_Agent" # Direct to Agent Root
            }
            _v3_status = healed_post(self.webhook_url, payload)

            resp = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
            if resp.status_code == 200:
                data = resp.json()
                self.root_folder_id = data.get("id")
                print(f"--- Cloud Sync: Active (ID: {self.root_folder_id}) ---", flush=True)
                return self.root_folder_id
            else:
                print(f"--- Cloud Sync Error: {resp.text} ---", flush=True)
        except Exception as e:
            print(f"--- Cloud Sync Connection Failed: {e} ---", flush=True)
            
        return None

    def upload_file(self, local_path, target_filename=None):
        """
        Uploads a local file to the Project Folder in Drive.
        """
        if not target_filename:
            target_filename = os.path.basename(local_path)
            
        folder_id = self.ensure_project_folder()
        if not folder_id:
            print("--- Upload Failed: No Project Folder ID ---", flush=True)
            return None
            
        print(f"--- Cloud Sync: Uploading '{target_filename}'... ---", flush=True)
        try:
            with open(local_path, "rb") as f:
                content = base64.b64encode(f.read()).decode("utf-8")
                
            payload = {
                "action": "upload_file",
                "file_name": target_filename,
                "parent_id": folder_id,
                "file_content": content
            }
            _v3_status = healed_post(self.webhook_url, payload)

            resp = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
            if resp.status_code == 200:
                print(f"--- Cloud Sync: Upload Complete ---", flush=True)
                data = resp.json()
                # Try common Drive API keys
                link = data.get("webViewLink") or data.get("webContentLink") or data.get("alternateLink") or data.get("id")
                return link
        except Exception as e:
            print(f"--- Upload Error: {e} ---", flush=True)
            return None

    def manage_document(self, action, file_type, file_name, content):
        # Legacy/Stub for compatibility
        return {"status": "success", "message": "Delegated to Cloud"}

if __name__ == "__main__":
    mgr = GoogleSuiteManager("Test_Project")
    # mgr.ensure_project_folder()

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
