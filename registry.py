"""
Antigravity Registry — n8n Data Table Backed
=============================================
Upgraded Librarian that reads/writes the ANTIGRAVITY_INVENTORY
data table via the n8n API. Replaces the old JSON-file registry.
"""
import json
import os
import requests
from datetime import datetime

# ── Configuration ──
CONFIG_PATH = os.path.join(
    os.path.expanduser("~"),
    "My Drive (maurotgs@gmail.com)",
    "Antigravity-AI Agents",
    ".system_core",
    "registry_config.json",
)

BASE = "https://humanresource.app.n8n.cloud/api/v1"

# Load config
def _load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}

_CONFIG = _load_config()
TABLE_ID = _CONFIG.get("inventory_table_id", "")
API_KEY = os.getenv("N8N_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1ZGM3MWNiMy0yZWRkLTRmMWItODQwMS00MGQ4M2FkOTBmMWIiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY4NTE1NDM5fQ.RibOEnSDVDwlwVJGuac_BTfmZdnpx7SL0-QhxUn4xns")
HEADERS = {"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}

# ── Legacy fallback ──
LEGACY_REGISTRY = os.path.join(
    os.path.expanduser("~"),
    "My Drive (maurotgs@gmail.com)",
    "Antigravity-AI Agents",
    ".system_core",
    "Meta_App_Factory",
    "registry.json",
)


class Librarian:
    """
    The Librarian Agent (v2).
    Manages the ANTIGRAVITY_INVENTORY via n8n Data Tables API.
    Falls back to local JSON if the API is unreachable.
    """

    def __init__(self):
        self.table_id = TABLE_ID
        self.base = BASE
        self.headers = HEADERS

    # ── Core CRUD ──

    def register_app(self, app_name, workflow_id, webhook_url, blueprint,
                     project_id="", project_name="", drive_path="",
                     capabilities=None, is_skill=False, item_type="App"):
        """Register a new item in the ANTIGRAVITY_INVENTORY."""
        row = {
            "Item_Name": app_name,
            "Type": item_type,
            "Project_ID": project_id,
            "Project_Name": project_name,
            "Workflow_ID": workflow_id,
            "Webhook_Path": webhook_url.split("/webhook/")[-1] if "/webhook/" in webhook_url else "",
            "Drive_Path": drive_path,
            "Status": "Active",
        }

        if self.table_id:
            r = requests.post(
                f"{self.base}/data-tables/{self.table_id}/rows",
                headers=self.headers,
                json={"data": [row]},
            )
            if r.status_code in (200, 201):
                print(f"--- Librarian: Registered '{app_name}' in INVENTORY (type={item_type}) ---")
                return True
            else:
                print(f"--- Librarian: API failed ({r.status_code}), falling back to JSON ---")

        # Fallback to local JSON
        self._legacy_register(app_name, workflow_id, webhook_url, blueprint, capabilities, is_skill)
        return True

    def search_by_type(self, item_type):
        """Query INVENTORY for items of a specific type (App/Skill/Tool/Workflow)."""
        if self.table_id:
            r = requests.get(
                f"{self.base}/data-tables/{self.table_id}/rows?limit=250",
                headers=self.headers,
            )
            if r.status_code == 200:
                rows = r.json().get("data", [])
                return [row for row in rows if row.get("Type") == item_type]
        return []

    def search_by_name(self, name_query):
        """Search for items by name (partial match)."""
        if self.table_id:
            r = requests.get(
                f"{self.base}/data-tables/{self.table_id}/rows?limit=250",
                headers=self.headers,
            )
            if r.status_code == 200:
                rows = r.json().get("data", [])
                return [row for row in rows
                        if name_query.lower() in row.get("Item_Name", "").lower()]
        return []

    def get_all_tools(self):
        """Get all items tagged as Tool — these are universal/reusable."""
        return self.search_by_type("Tool")

    def get_all_skills(self):
        """Get all items tagged as Skill."""
        return self.search_by_type("Skill")

    def get_all_apps(self):
        """Get all registered Apps."""
        return self.search_by_type("App")

    def find_tool(self, tool_name):
        """Find a specific tool by name. Returns workflow_id and project_id."""
        results = self.search_by_name(tool_name)
        tools = [r for r in results if r.get("Type") == "Tool"]
        if tools:
            t = tools[0]
            return {
                "name": t.get("Item_Name"),
                "workflow_id": t.get("Workflow_ID"),
                "project_id": t.get("Project_ID"),
                "webhook_path": t.get("Webhook_Path"),
                "status": t.get("Status"),
            }
        return None

    def get_full_inventory(self):
        """Return the entire inventory."""
        if self.table_id:
            r = requests.get(
                f"{self.base}/data-tables/{self.table_id}/rows?limit=250",
                headers=self.headers,
            )
            if r.status_code == 200:
                return r.json().get("data", [])
        return []

    # ── Convenience ──

    def register_skill(self, app_name, webhook_url, skill_path, capabilities=None):
        """Register a reusable skill."""
        return self.register_app(
            app_name=app_name,
            workflow_id="",
            webhook_url=webhook_url,
            blueprint="skill",
            drive_path=skill_path,
            item_type="Skill",
        )

    # ── Legacy fallback ──

    def _legacy_register(self, app_name, workflow_id, webhook_url, blueprint, capabilities, is_skill):
        """Fallback: write to local JSON file."""
        path = LEGACY_REGISTRY
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = {"apps": [], "last_updated": ""}
        else:
            with open(path) as f:
                data = json.load(f)

        entry = {
            "name": app_name,
            "workflow_id": workflow_id,
            "webhook_url": webhook_url,
            "blueprint": blueprint,
            "capabilities": capabilities or [],
            "is_skill": is_skill,
            "last_build": datetime.now().isoformat(),
        }

        data["apps"] = [a for a in data["apps"] if a["name"] != app_name]
        data["apps"].append(entry)
        data["last_updated"] = datetime.now().isoformat()

        with open(path, "w") as f:
            json.dump(data, f, indent=4)
        print(f"--- Librarian: Registered '{app_name}' in legacy JSON ---")


# ── Tool Discovery ──

def discover_tool(tool_name):
    """
    Utility function for specialist agents to find tools.
    Returns the webhook URL to call a tool.
    """
    lib = Librarian()
    tool = lib.find_tool(tool_name)
    if tool and tool["webhook_path"]:
        return f"https://humanresource.app.n8n.cloud/webhook/{tool['webhook_path']}"
    return None


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    lib = Librarian()

    print("=== ANTIGRAVITY INVENTORY ===\n")

    print("TOOLS (Universal):")
    for t in lib.get_all_tools():
        print(f"  {t.get('Item_Name'):>35}  wf={t.get('Workflow_ID')}  wh={t.get('Webhook_Path')}")

    print("\nSKILLS:")
    for s in lib.get_all_skills():
        print(f"  {s.get('Item_Name'):>35}  wf={s.get('Workflow_ID')}  wh={s.get('Webhook_Path')}")

    print("\nAPPS:")
    for a in lib.get_all_apps():
        print(f"  {a.get('Item_Name'):>35}  wf={a.get('Workflow_ID')}  proj={a.get('Project_Name')}")

    print(f"\nTool Discovery test:")
    for name in ["Gemini Agent Bridge", "System - Atomizer", "Drive Manager"]:
        url = discover_tool(name)
        print(f"  {name}: {url or 'not found'}")
