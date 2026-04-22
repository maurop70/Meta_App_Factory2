import json
import os
import sys
from pathlib import Path

# Add system core to path for project_manager
SYSTEM_CORE = str(Path(__file__).parent.parent.parent / ".system_core")
if SYSTEM_CORE not in sys.path:
    sys.path.insert(0, SYSTEM_CORE)

try:
    import project_manager
except ImportError:
    project_manager = None
    print("Warning: .system_core.project_manager not found. Using local fallback.")

AGENT_ROLE = "venture_architect"
FALLBACK_DIR = Path(__file__).parent / "local_memory"

def get_project_state(project_name: str) -> dict:
    if not project_name:
        return {}
        
    try:
        if project_manager:
            data = project_manager.read_project_file(project_name, AGENT_ROLE, "architect_state.json")
            return json.loads(data)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Error reading state: {e}")
        
    # Local fallback
    local_file = FALLBACK_DIR / f"{project_name}_state.json"
    if local_file.exists():
        with open(local_file, "r") as f:
            return json.load(f)
    return {"project_name": project_name}

def save_project_state(project_name: str, state: dict) -> bool:
    if not project_name:
        return False
        
    state_json = json.dumps(state, indent=2).encode('utf-8')
    
    if project_manager:
        try:
            project_manager.write_project_file(project_name, AGENT_ROLE, "architect_state.json", state_json)
            return True
        except Exception as e:
            print(f"Project manager write failed: {e}")
            
    # Local fallback
    FALLBACK_DIR.mkdir(exist_ok=True)
    local_file = FALLBACK_DIR / f"{project_name}_state.json"
    with open(local_file, "wb") as f:
        f.write(state_json)
    return True

def list_projects() -> list:
    projects = []
    if project_manager:
        # We can scan the Global_Projects dir
        global_dir = project_manager.GLOBAL_PROJECTS_DIR
        if global_dir.exists():
            for p in global_dir.iterdir():
                if p.is_dir():
                    projects.append(p.name)
    else:
        if FALLBACK_DIR.exists():
            for p in FALLBACK_DIR.iterdir():
                if p.name.endswith("_state.json"):
                    projects.append(p.name.replace("_state.json", ""))
    return list(set(projects))

def get_cmo_context(project_name: str) -> dict:
    """Read context from the CMO Elite agent's memory for this project."""
    if not project_manager:
        return {}
        
    try:
        # CMO Elite saves its DB locally in CMO_Elite_Agent/backend/marketing_memory.db
        # But if it uses project_manager, it saves to Global_Projects/{project}/cmo/state.json
        # We will attempt to read standard shared context
        data = project_manager.read_project_file(project_name, "cmo", "cmo_state.json")
        return json.loads(data)
    except Exception:
        return {}
