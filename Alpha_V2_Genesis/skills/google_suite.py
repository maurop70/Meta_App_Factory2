import os
import requests
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
            resp = requests.post(self.webhook_url, json=payload, timeout=30)
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
            resp = requests.post(self.webhook_url, json=payload, timeout=60)
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
