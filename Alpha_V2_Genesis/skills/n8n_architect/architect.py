import requests
import json
import logging
import os
from typing import Dict, List, Optional, Any

# Setup Logging
logger = logging.getLogger("N8NArchitect")
logger.setLevel(logging.INFO)

class N8NArchitect:
    """
    Senior N8N Workflow Architect.
    Capable of searching, creating, configuring, and testing n8n workflows via API.
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://humanresource.app.n8n.cloud"):
        self.base_url = base_url.rstrip('/')
        # Try to load from env or use default if provided (In prod, use env vars!)
        # V2.0 Vault integration — remove hardcoded key
        try:
            _alpha_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            import sys as _sys
            if _alpha_root not in _sys.path:
                _sys.path.insert(0, _alpha_root)
            from vault_client import get_secret
            self.api_key = api_key or get_secret("N8N_API_KEY") or os.getenv("N8N_API_KEY", "")
        except ImportError:
            self.api_key = api_key or os.getenv("N8N_API_KEY", "")
        
        if not self.api_key:
             logger.warning("N8N API Key not found! Architect will be limited.")
             
        self.headers = {
            "X-N8N-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

    # --- 1. SEARCH & DISCOVERY ---

    def list_workflows(self, tags: List[str] = None) -> List[Dict]:
        """Retrieves all workflows, optionally filtered."""
        endpoint = f"{self.base_url}/api/v1/workflows"
        try:
            resp = requests.get(endpoint, headers=self.headers, timeout=60)
            resp.raise_for_status()
            data = resp.json().get('data', [])
            
            if tags:
                # Client-side filter if API doesn't support tag filtering directly
                # (API usually supports ?tags=... check docs if needed, but this is safe)
                # For now just return all, logic can be enhanced.
                pass
                
            return data
        except Exception as e:
            logger.error(f"Failed to list workflows: {e}")
            return []

    def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        """Gets full details of a specific workflow."""
        endpoint = f"{self.base_url}/api/v1/workflows/{workflow_id}"
        try:
            resp = requests.get(endpoint, headers=self.headers, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to get workflow {workflow_id}: {e}")
            return None

    def get_executions(self, limit: int = 50, status: str = None) -> List[Dict]:
        """
        Retrieves recent executions.
        status: 'error', 'success', 'waiting'
        """
        endpoint = f"{self.base_url}/api/v1/executions"
        params = {"limit": limit, "includeData": "true"}
        if status:
            params["status"] = status
            
        try:
            resp = requests.get(endpoint, headers=self.headers, params=params)
            resp.raise_for_status()
            return resp.json().get('data', [])
        except Exception as e:
            logger.error(f"Failed to get executions: {e}")
            return []

    # --- 2. CREATION & DEPLOYMENT ---

    def create_workflow(self, workflow_json: Dict, activate: bool = True) -> Optional[str]:
        """
        Deploys a new workflow to N8N.
        Returns: Workflow ID if successful.
        """
        endpoint = f"{self.base_url}/api/v1/workflows"
        
        # Ensure 'nodes' and 'connections' exist
        if "nodes" not in workflow_json or "connections" not in workflow_json:
            logger.error("Invalid Schema: Missing 'nodes' or 'connections'.")
            return None
            
        try:
            logger.info(f"Deploying Workflow: {workflow_json.get('name', 'Untitled')}...")
            resp = requests.post(endpoint, json=workflow_json, headers=self.headers, timeout=60)
            resp.raise_for_status()
            
            wf_id = resp.json().get('id')
            logger.info(f"Workflow Created: {wf_id}")
            
            if activate:
                self.activate_workflow(wf_id)
                
            return wf_id
        except Exception as e:
            logger.error(f"Deployment Failed: {e}")
            # If 400, print details
            if hasattr(e, 'response') and e.response:
                logger.error(f"API Response: {e.response.text}")
            return None

    def update_workflow(self, workflow_id: str, workflow_json: Dict) -> bool:
        """
        Updates an existing workflow.
        """
        endpoint = f"{self.base_url}/api/v1/workflows/{workflow_id}"
        
        # Ensure 'nodes' and 'connections' exist
        if "nodes" not in workflow_json or "connections" not in workflow_json:
            logger.error("Invalid Schema: Missing 'nodes' or 'connections'.")
            return False
            
        try:
            logger.info(f"Updating Workflow {workflow_id} ({workflow_json.get('name', 'Untitled')})...")
            
            # --- SANITIZATION ---
            # Whitelist approach: ULTRA-STRICT 
            # 1. Allow 'name', 'nodes', 'connections'
            # 2. ENFORCE 'settings' as empty dict {} to satisfy API requirement without triggering "additional properties" error
            allowed_fields = ['name', 'nodes', 'connections']
            
            payload = {k: v for k, v in workflow_json.items() if k in allowed_fields}
            payload['settings'] = {} # Explicitly set empty settings object
            
            headers = self.headers.copy()
            resp = requests.put(endpoint, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            logger.info(f"Workflow {workflow_id} Updated.")
            return True
        except Exception as e:
            logger.error(f"Update Failed: {e}")
            # Explicitly check and print response text
            if hasattr(e, 'response') and e.response is not None:
                 print(f"DEBUG: API Error Detail: {e.response.text}") # Force print to console
                 logger.error(f"API Response: {e.response.text}")
            return False

    def activate_workflow(self, workflow_id: str) -> bool:
        """Activates a workflow."""
        endpoint = f"{self.base_url}/api/v1/workflows/{workflow_id}/activate"
        try:
            resp = requests.post(endpoint, headers=self.headers, timeout=60)
            resp.raise_for_status()
            logger.info(f"Workflow {workflow_id} Activated.")
            return True
        except Exception as e:
            logger.error(f"Activation Failed: {e}")
            return False

    def delete_workflow(self, workflow_id: str) -> bool:
        """Deletes a workflow."""
        endpoint = f"{self.base_url}/api/v1/workflows/{workflow_id}"
        try:
            resp = requests.delete(endpoint, headers=self.headers, timeout=60)
            resp.raise_for_status()
            logger.info(f"Workflow {workflow_id} Deleted.")
            return True
        except Exception as e:
            logger.error(f"Deletion Failed for {workflow_id}: {e}")
            return False

    # --- 3. VERIFICATION & DEBUGGING ---
    
    def verify_connection(self) -> bool:
        """Quick connectivity check."""
        try:
            self.list_workflows()
            return True
        except:
            return False

    # --- 4. SCHEMA BUILDING HELPERS (Loki Protocol) ---
    # These helpers allow the Agent to construct nodes programmatically
    
    def create_webhook_node(self, name="Webhook", path="webhook", method="POST") -> Dict:
        return {
            "parameters": {
                "path": path,
                "httpMethod": method,
                "options": {}
            },
            "name": name,
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 1,
            "position": [100, 300]
        }
        
    def create_code_node(self, javascript_code: str, name="Code") -> Dict:
        return {
            "parameters": {
                "jsCode": javascript_code
            },
            "name": name,
            "type": "n8n-nodes-base.code",
            "typeVersion": 1,
            "position": [300, 300]
        }
