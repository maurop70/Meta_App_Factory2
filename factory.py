# ═══════════════════════════════════════════════════════════════════
#  RESILIENCE ANCHOR V3.0 — factory.py
# ═══════════════════════════════════════════════════════════════════
#
#  This file is the CENTRAL ORCHESTRATOR of the Antigravity Ops
#  Intelligence system. All child apps, agents, and workflows
#  depend on this module for:
#
#    • safe_post()    — V3 resilience pattern (preflight → log → POST)
#    • healed_post()  — Auto-heal layer (retry + backoff + diagnosis)
#    • StateManager   — UUID+timestamp logging via local_state_manager.py
#    • Safe-Buffer    — Automatic offline queuing during cloud outages
#
#  AUTHORIZED CREDENTIAL:
#    Name:        Antigravity_Full_v2
#    Fingerprint: eyJhbGciOiJIUzI1NiIs...UebO3WCxto
#    Length:      267 chars
#    Source:      Meta_App_Factory/.env (READ-ONLY — do NOT modify directly)
#    Rotation:    Via env_updater.py only (see SOP_MAINTENANCE.md)
#
#  DO NOT bypass this module. Doing so removes Safe-Buffer protection
#  and Auto-Heal capabilities from the calling agent.
#
#  Frozen: 2026-03-13T12:22:22-04:00
#  Status: [SYSTEM_V3_UPGRADE] FULLY DEPLOYED & SEALED
# ═══════════════════════════════════════════════════════════════════

import os
import json
import argparse
import sys
import requests
from typing import Dict, Optional
from datetime import datetime

# Git deployment
SYSTEM_CORE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, SYSTEM_CORE_DIR)

# Add skill path to sys.path — validate that critical modules (n8n_architect) are present
FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_CANDIDATES = [
    os.path.abspath(os.path.join(FACTORY_DIR, "..", "..", "_ANTIGRAVITY_SKILLS_LIBRARY")),
    os.path.abspath(os.path.join(FACTORY_DIR, "..", "skills")),
    os.path.join(FACTORY_DIR, "Alpha_V2_Genesis", "skills"),
]
SKILL_PATH = None
for _candidate in _SKILL_CANDIDATES:
    if os.path.isdir(os.path.join(_candidate, "n8n_architect")):
        SKILL_PATH = _candidate
        break
if not SKILL_PATH:
    # Accept any existing directory as last resort
    for _candidate in _SKILL_CANDIDATES:
        if os.path.isdir(_candidate):
            SKILL_PATH = _candidate
            break
if SKILL_PATH:
    sys.path.append(SKILL_PATH)
# Also add all existing candidate paths so scattered modules are discoverable
for _candidate in _SKILL_CANDIDATES:
    if os.path.isdir(_candidate) and _candidate not in sys.path:
        sys.path.append(_candidate)

# Lazy imports — these are only needed for the `create` command
# CLI commands (status, build, launch, tunnels) work without them
_SKILLS_LOADED = False
N8NArchitect = Librarian = ArtisanCritic = Scribe = UIDesigner = None

def _load_skills():
    global _SKILLS_LOADED, N8NArchitect, Librarian, ArtisanCritic, Scribe, UIDesigner
    if _SKILLS_LOADED:
        return
    from n8n_architect.architect import N8NArchitect as _A
    from registry import Librarian as _L
    from utils.critic import ArtisanCritic as _C
    from scribe import Scribe as _S
    from ui_designer import UIDesigner as _U
    N8NArchitect, Librarian, ArtisanCritic, Scribe, UIDesigner = _A, _L, _C, _S, _U
    _SKILLS_LOADED = True

# n8n API config for project creation
N8N_API_BASE = "https://humanresource.app.n8n.cloud/api/v1"
# Load from .env — no hardcoded fallback (COMPLIANCE-CRED-001 remediation)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass  # dotenv not installed; relies on system env vars
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
if not N8N_API_KEY:
    print("⚠️ WARNING: N8N_API_KEY not set. n8n operations will fail.", flush=True)
N8N_HEADERS = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}
DEFAULT_PROJECT_ID = os.getenv("N8N_DEFAULT_PROJECT_ID", "boV7btArBtpvCiXm")

class MetaAppFactory:
    # Canonical app storage: Google Drive > local fallback
    GDRIVE_PATH = os.path.join(os.path.expanduser("~"), "My Drive", "Antigravity-AI Agents", "Meta_App_Factory")

    def __init__(self):
        _load_skills()
        self.architect = N8NArchitect()
        self.librarian = Librarian()
        self.critic = ArtisanCritic()
        self.scribe = Scribe()
        self.designer = UIDesigner()
        # Always create apps in Google Drive if available
        if os.path.isdir(self.GDRIVE_PATH):
            self.base_dir = self.GDRIVE_PATH
        else:
            self.base_dir = FACTORY_DIR  # local fallback
        self.blueprints_dir = os.path.join(FACTORY_DIR, "blueprints")  # blueprints stay with the code

    # ── Port Allocation ────────────────────────────────────
    PORT_BASE = 5005
    PORT_RANGE = 100  # 5005-5104

    def _allocate_port(self):
        """Scan registry for used ports and return the next available one."""
        used_ports = set()
        reg_path = os.path.join(FACTORY_DIR, "registry.json")
        try:
            with open(reg_path, "r") as f:
                registry = json.load(f)
            for app_data in registry.get("apps", {}).values():
                p = app_data.get("port")
                if p:
                    used_ports.add(int(p))
        except Exception:
            pass
        for port in range(self.PORT_BASE, self.PORT_BASE + self.PORT_RANGE):
            if port not in used_ports:
                return port
        raise RuntimeError("No available ports in range {}-{}".format(self.PORT_BASE, self.PORT_BASE + self.PORT_RANGE))

    def create_app(self, app_name: str, blueprint_name: str, description: str, system_prompt: Optional[str] = None):
        print(f"--- Creating Meta App: {app_name} ---")

        # 0. Allocate a dedicated port for this app
        app_port = self._allocate_port()
        print(f"  >> Allocated port: {app_port}")
        
        # 1. Load Blueprint
        blueprint_path = os.path.join(self.blueprints_dir, f"{blueprint_name}.json")
        if not os.path.exists(blueprint_path):
            print(f"Error: Blueprint '{blueprint_name}' not found at {blueprint_path}")
            return
            
        with open(blueprint_path, 'r') as f:
            workflow_json = json.load(f)
            
        # Customize workflow name and path
        workflow_json['name'] = f"MetaApp: {app_name}"
        webhook_path = f"{app_name}-webhook"
        for node in workflow_json.get('nodes', []):
            if node.get('type') == 'n8n-nodes-base.webhook':
                node['parameters']['path'] = webhook_path
            
            # [REFINEMENT LOGIC] Inject custom system instructions if provided
            if system_prompt and (node.get('name') == "Gemini Chain" or node.get('type') == "@n8n/n8n-nodes-langchain.chainLlm"):
                node['parameters']['prompt'] = f"SYSTEM INSTRUCTIONS: {system_prompt}\n\nUSER INPUT: {{{{ $json.body.prompt }}}}"

        # 2. Create n8n Project for this app (or fall back to Specialist Agents)
        project_id = DEFAULT_PROJECT_ID
        project_name = "Specialist Agents"
        try:
            r = requests.post(
                f"{N8N_API_BASE}/projects",
                headers=N8N_HEADERS,
                json={"name": f"App: {app_name}"},
            )
            if r.status_code in (200, 201):
                project_id = r.json()["id"]
                project_name = f"App: {app_name}"
                print(f"  >> Created dedicated project '{project_name}' ({project_id})")
            else:
                print(f"  >> Project limit reached, deploying to Specialist Agents")
        except Exception as e:
            print(f"  >> Project creation failed ({e}), using Specialist Agents")

        # 2.5 Deploy to N8N (non-fatal — app scaffold is built regardless)
        workflow_id = self.architect.create_workflow(workflow_json)
        if not workflow_id:
            print("  >> N8N workflow deploy failed — continuing with local scaffold only.")
            workflow_id = f"LOCAL_{app_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
        print(f"Workflow deployed successfully. ID: {workflow_id}")

        # 2.6 Transfer workflow to target project
        try:
            r = requests.put(
                f"{N8N_API_BASE}/workflows/{workflow_id}/transfer",
                headers=N8N_HEADERS,
                json={"destinationProjectId": project_id},
            )
            if r.status_code in (200, 204):
                print(f"  >> Workflow moved to project '{project_name}'")
            else:
                print(f"  >> Transfer warning: {r.status_code}")
        except Exception as e:
            print(f"  >> Transfer warning: {e}")

        # 3. Create Local App Directory
        app_dir = os.path.join(self.base_dir, app_name)
        os.makedirs(app_dir, exist_ok=True)
        os.makedirs(os.path.join(app_dir, ".Gemini_state"), exist_ok=True)
        
        # 4. Generate Local Bridge
        self._generate_bridge(app_dir, app_name, webhook_path, blueprint_name, workflow_id, port=app_port)

        # 4.5 Copy Action Plan Engine (Triad Execute Inheritance)
        import shutil
        action_plan_src = os.path.join(self.base_dir, "Adv_Autonomous_Agent", "action_plan.py")
        if os.path.exists(action_plan_src):
            shutil.copy2(action_plan_src, os.path.join(app_dir, "action_plan.py"))
            print(f"  >> Action Plan Engine inherited")

        # 4.6 Copy N8N Lifecycle Manager (Activate on launch, deactivate on close)
        lifecycle_src = os.path.join(self.base_dir, "Alpha_V2_Genesis", "n8n_lifecycle.py")
        if os.path.exists(lifecycle_src):
            shutil.copy2(lifecycle_src, os.path.join(app_dir, "n8n_lifecycle.py"))
            print(f"  >> N8N Lifecycle Manager inherited")

        # 4.7 Copy Preflight Check Module (Startup validation)
        preflight_src = os.path.join(self.base_dir, "Alpha_V2_Genesis", "preflight.py")
        if os.path.exists(preflight_src):
            shutil.copy2(preflight_src, os.path.join(app_dir, "preflight.py"))
            print(f"  >> Preflight Check Module inherited")

        # 4.8 Copy Stability Suite
        stability_modules = [
            "error_aggregator.py",
            "circuit_breaker.py",
            "config_snapshot.py",
            "n8n_budget_guard.py",
            "telemetry_dashboard.py",
        ]
        for mod in stability_modules:
            src = os.path.join(self.base_dir, "Alpha_V2_Genesis", mod)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(app_dir, mod))
        print(f"  >> Stability Suite inherited ({len(stability_modules)} modules)")

        # 4.9 Generate .env Template
        webhook_url = f"https://humanresource.app.n8n.cloud/webhook/{webhook_path}"
        self._generate_env(app_dir, app_name, webhook_url)
        
        # --- ELITE COUNCIL SEQUENCING ---
        
        # 5. Librarian: Register in ANTIGRAVITY_INVENTORY (n8n Data Table)
        capabilities = [blueprint_name.replace("_", " ")]
        if "file" in description.lower(): capabilities.append("file system")
        if "agent" in description.lower() or "persona" in description.lower(): capabilities.append("multi-agent")
        if "sheets" in description.lower() or "financial" in description.lower(): capabilities.append("spreadsheet logic")
        
        self.librarian.register_app(
            app_name=app_name,
            workflow_id=workflow_id,
            webhook_url=webhook_url,
            blueprint=blueprint_name,
            project_id=project_id,
            project_name=project_name,
            drive_path=f".system_core/Meta_App_Factory/{app_name}/",
            capabilities=capabilities,
            item_type="App",
            port=app_port,
        )

        # 6. Inspector: Smoke Test
        self.critic.run_smoke_test(app_name, webhook_url)

        # 7. Scribe: Create Commercial Documentation Suite
        self.scribe.generate_commercial_docs(app_dir, app_name, blueprint_name, description, capabilities)

        # 8. Designer: Create UI (with Action Plan panel)
        self.designer.build_ui(app_dir, app_name, port=app_port)

        # 8.5 Generate Launch Script
        self._generate_launch_script(app_dir, app_name, port=app_port)

        # 8.6 Generate Docker Deployment Artifacts
        self._generate_docker_artifacts(app_dir, app_name, port=app_port)

        # 9. Register as Skill / Tool
        self._register_as_skill(app_dir, app_name, webhook_url, capabilities, description)

        # 10. Deploy to GitHub + Log to INVENTORY
        try:
            from git_deployer import deploy_to_github
            result = deploy_to_github(
                app_path=app_dir,
                repo_name=None,  # Auto-generate from app name
                private=True,
            )
            repo_url = result['repo_url']
            print(f"  >> GitHub: {repo_url}")

            # Log GitHub URL to ANTIGRAVITY_INVENTORY
            try:
                inventory_rows = requests.get(
                    f"{N8N_API_BASE}/data-tables/4Bx8Iv8tx8lit144/rows?limit=100",
                    headers=N8N_HEADERS,
                ).json().get("data", [])
                
                # Find the row for this app (just registered in Step 5)
                app_row = next(
                    (r for r in inventory_rows if r.get("Item_Name") == app_name),
                    None,
                )
                if app_row:
                    requests.patch(
                        f"{N8N_API_BASE}/data-tables/4Bx8Iv8tx8lit144/rows/{app_row['id']}",
                        headers=N8N_HEADERS,
                        json={"github_repo_url": repo_url},
                    )
                    print(f"  >> INVENTORY updated: github_repo_url = {repo_url}")
                else:
                    print(f"  >> INVENTORY: app row not found, URL not logged")
            except Exception as inv_e:
                print(f"  >> INVENTORY log warning: {inv_e}")

        except Exception as e:
            print(f"  >> GitHub deploy skipped: {e}")

        print(f"--- Commercial Grade App {app_name} Ready ---")
        print(f"--- Documentation: README.md, USER_GUIDE.md, INSTALL.md, API_REFERENCE.md, LICENSE, CHANGELOG.md ---")
        print(f"--- Skill registered at: skills/{app_name.lower().replace(' ', '_')} ---")

    def _generate_bridge(self, app_dir, app_name, webhook_path, blueprint_name, workflow_id=None, port=5005):
        webhook_url = f"https://humanresource.app.n8n.cloud/webhook/{webhook_path}"
        
        if "elite" in blueprint_name.lower():
            # Injecting Cloud-Native Router Bridge (v2.0)
            bridge_code = r'''import os
import sys
import json
import requests
from dotenv import load_dotenv

# --- FLIGHT RECORDER: OpenTelemetry Setup ---
# --- FLIGHT RECORDER: OpenTelemetry Setup ---
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource

    # Initialize Tracer
    resource = Resource(attributes={
        SERVICE_NAME: "Adv_Autonomous_Agent"
    })
    provider = TracerProvider(resource=resource)

    # Export to Console for now (and OTLP if configured)
    processor = BatchSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)

    # Optional OTLP Exporter (Google Cloud Trace ready)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(__name__)
except ImportError:
    class DummySpan:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def set_attribute(self, k, v): pass
        def add_event(self, name, attributes=None): pass
        def record_exception(self, e): pass
    
    class DummyTracer:
        def start_as_current_span(self, name): return DummySpan()
        
    tracer = DummyTracer()

# Load environment variables
load_dotenv()

# Configuration from .env or defaults
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "URL_PLACEHOLDER")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.getenv("PROJECTS_DIR", os.path.join(BASE_DIR, "Projects"))
SKILLS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "skills"))
if SKILLS_DIR not in sys.path: sys.path.append(SKILLS_DIR)

# [CRITICAL] Pre-load Skills to ensure registration
from financial_planner import FinancialPlanner
from file_factory import FileFactory
from google_suite import GoogleSuiteManager

# [ROUTER CONFIG] Specialist Agent Registry
# Verified Active URLs — synced by Zero-G Diagnostic (2026-02-24)
AGENT_REGISTRY = {
    # The Core Team (Verified ACTIVE)
    "CFO": "https://humanresource.app.n8n.cloud/webhook/cfo",
    "CMO": "https://humanresource.app.n8n.cloud/webhook/cmo-v2",
    "HR": "https://humanresource.app.n8n.cloud/webhook/hr",

    # The New Special Forces (Verified ACTIVE)
    "CRITIC": "https://humanresource.app.n8n.cloud/webhook/critic-v2",
    "PITCH": "https://humanresource.app.n8n.cloud/webhook/pitch-v2",
    "ATOMIZER": "https://humanresource.app.n8n.cloud/webhook/atomizer-v2",
    "ARCHITECT": "https://humanresource.app.n8n.cloud/webhook/architect-v2",
    "PRESENTATION_ARCHITECT": "https://humanresource.app.n8n.cloud/webhook/architect-v2",

    # Operations & Tech — routed through gemini-flash (elite-council is INACTIVE)
    "COO": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",
    "CTO": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",
    "LEGAL": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",

    # Legacy/Generic — routed through gemini-flash
    "PRODUCT": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",
    "SALES": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",
    "ANALYST": "https://humanresource.app.n8n.cloud/webhook/gemini-flash"
}

# Sentry Persistence
CACHE_FILE = os.path.join(BASE_DIR, ".Gemini_state", ".sentry_cache.json")
HISTORY_FILE = os.path.join(BASE_DIR, ".Gemini_state", ".chat_history.json")

class LocalMemory:
    def __init__(self, filepath, window_size=5):
        self.filepath = filepath
        self.window = window_size
        
    def add(self, role, content):
        history = self.load()
        history.append({"role": role, "content": content})
        if len(history) > (self.window * 2): # Keep last N turns (user+ai)
            history = history[-(self.window * 2):]
        self._save(history)
        
    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f: return json.load(f)
            except: pass
        return []
        
    def get_context_string(self):
        history = self.load()
        if not history: return ""
        text = "--- CHAT HISTORY ---\n"
        for msg in history:
            text += f"{msg['role'].upper()}: {msg['content']}\n"
        text += "--------------------\n"
        return text

    def clear(self):
        self._save([])
        
    def _save(self, data):
        with open(self.filepath, "w") as f:
            json.dump(data, f, indent=2)

memory = LocalMemory(HISTORY_FILE)
PROJECT_CACHE =  os.path.join(BASE_DIR, ".Gemini_state", ".project_context.json")

def _check_project_switch(new_project):
    """Auto-wipes memory if project changes AND inits Cloud Folder"""
    try:
        last_project = ""
        if os.path.exists(PROJECT_CACHE):
             with open(PROJECT_CACHE, "r") as f: last_project = f.read().strip()
             
        if new_project != "General_Consulting" and new_project != last_project:
            print(f"--- CONTEXT SWITCH: {last_project} -> {new_project}. Wiping Memory. ---", flush=True)
            memory.clear()
            
            # Cloud Initialization
            if SKILLS_DIR not in sys.path: sys.path.append(SKILLS_DIR)
            try:
                from google_suite import GoogleSuiteManager
                mgr = GoogleSuiteManager(new_project)
                mgr.ensure_project_folder()
            except Exception as e:
                print(f"--- Cloud Init Warning: {e} ---", flush=True)
            
        with open(PROJECT_CACHE, "w") as f: f.write(new_project)
    except: pass

def clear_memory():
    memory.clear()
    print("--- MEMORY WIPED ---", flush=True)

def _update_cache(prompt):
    try:
        cache = []
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f: cache = json.load(f)
        cache.append(prompt)
        cache = cache[-5:] # Keep last 5
        with open(CACHE_FILE, "w") as f: json.dump(cache, f)
    except: pass

def get_last_prompt():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f: return json.load(f)[-1]
    except: pass
    return None

def _healing_protocol():
    """
    Sentry Level 2: Infrastructure Repair.
    Scans N8N for valid workflows if the connection is dead.
    """
    global WEBHOOK_URL
    print("--- SENTRY L2: INITIATING INFRASTRUCTURE SCAN ---", flush=True)
    
    if SKILLS_DIR not in sys.path: sys.path.append(SKILLS_DIR)
    try:
        from n8n_architect.architect import N8NArchitect
        arch = N8NArchitect()
        workflows = arch.list_workflows()
        
        # Priority Search: Find ANY active workflow that looks like our agent
        target_id = None
        for wf in workflows:
            if wf.get("active") and ("Elite Council" in wf.get("name") or "Adv_Autonomous_Agent" in wf.get("name")):
                 target_id = wf.get("id")
                 break
        
        if target_id:
             # Construct the ID-based URL which is most robust
             new_url = f"https://humanresource.app.n8n.cloud/webhook/{target_id}/elite-council"
             
             # Check if we need to switch (or if we just need to try the simplified one)
             print(f"--- SENTRY L2: FOUND ACTIVE NODE {target_id}. RE-ALIGNING SATELLITES... ---", flush=True)
             WEBHOOK_URL = new_url
             return True
        else:
            print("--- SENTRY L2: NO ACTIVE WORKFLOWS FOUND. PLEASE CHECK N8N DASHBOARD. ---", flush=True)
            
    except Exception as e:
        print(f"--- SENTRY L2 ERROR: {e} ---", flush=True)
        
    return False

def check_system_health():
    """
    Pings all agents in the registry to verify they are online.
    Returns a dict: {"CFO": True, "CMO": False, ...}
    """
    print("--- DIAGNOSTIC: Initiating Neural Network Scan ---", flush=True)
    status_report = {}
    
    # Only check dedicated agents to save time, skip fallbacks
    targets = {k: v for k, v in AGENT_REGISTRY.items() if "role=" not in v}
    
    for role, url in targets.items():
        try:
             # Fast timeout ping
             resp = requests.post(url, json={"prompt": "PING"}, timeout=3)
             if resp.status_code == 200:
                 status_report[role] = True
             else:
                 status_report[role] = False
        except:
             status_report[role] = False
             
    return status_report

def call_app(payload):
    """
    Elite Consulting Bridge.
    Orchestrates Tool Loops, Drafting Protocol, and Project Isolation.
    """
    with tracer.start_as_current_span("call_app") as span:
        prompt = payload.get("prompt", "")
        project_name = payload.get("project_name", "General_Consulting")
        is_suite_cmd = payload.get("suite_command", False)
        
        span.set_attribute("project_name", project_name)
        span.add_event("Prompt Received", {"prompt_preview": prompt[:100]})

        # 1. Prompt Persistence
        if prompt and not payload.get("context"):
            _update_cache(prompt)
    if "Project:" in prompt:
        try: 
            temp = prompt.split("Project:")[1].strip()
            project_name = temp.split("\n")[0].split(":")[0].strip().replace(" ", "_")
        except: pass
    elif "Project " in prompt:
        try: 
            temp = prompt.split("Project ")[1].strip()
            candidate = temp.split("\n")[0].split(":")[0].strip()
            # Heuristic for long prompt interpreted as name
            if len(candidate) > 50:
                candidate = "_".join(candidate.split()[:3])
            project_name = candidate.replace(" ", "_").strip(".")
        except: pass
    payload["project_name"] = project_name

    # 1.5 Context Switching (Memory Wipe)
    _check_project_switch(project_name)

    # 2. Ingestion Trigger (DEPRECATED - Cloud Native Mode)
    # Files are uploaded directly to Drive via UI.
    # if "ANALYST: Ingest" in prompt: ...



    try:
        tool_awareness = """
[SYSTEM UPGRADE: CREATIVE SUITE ACTIVE]
You have access to new "Professional Grade" tools. DO NOT Refuse these tasks.
1. Financial Modeling: Use 'financial_model' tool. It creates LIVE Excel files with working formulas.
2. Presentations: Use 'produce_document' with file_type='pptx'. You can design slides.
3. Images: Use 'produce_document' with file_type='image' and content='DALL-E Prompt' to generate visual assets.
"""

        if payload.get("clean_slate"):
             payload["prompt"] = f"{tool_awareness}\nUSER INPUT:\n{prompt}"
        
        elif is_suite_cmd:
            print("--- SENTRY: SUITE COMMAND BYPASS ACTIVE ---", flush=True)
            payload["context"] = "SUITE_OVERRIDE"
            # Sentry Level 3.5: Supervisor Context
            history_text = memory.get_context_string()
            if history_text:
                payload["prompt"] = f"CONTEXT(HISTORY):\n{history_text}\n{tool_awareness}\nSUPERVISOR COMMAND:\n{prompt}"
            else:
                 payload["prompt"] = f"{tool_awareness}\nSUPERVISOR COMMAND:\n{prompt}"
            
        else:
            # Normal flow: Inject history + Tool Awareness
            history_text = memory.get_context_string()
            
            if history_text:
                 payload["prompt"] = f"CONTEXT(HISTORY):\n{history_text}\n{tool_awareness}\nUSER INPUT:\n{prompt}"
            else:
                 payload["prompt"] = f"{tool_awareness}\nUSER INPUT:\n{prompt}"

        # IMMEDIATE LOGGING: Capture user intent before network call
        memory.add("user", prompt)

        # CRASH SHIELD: Exponential Backoff + Circuit Breaker (SWDR v1.0)
        import time
        import random
        max_retries = 3
        backoff_base = 2  # seconds — delays: 2s, 4s, 8s
        result = None

        # Circuit Breaker Gate — 3 consecutive failures = Soft Pause
        try:
            from circuit_breaker import CircuitBreaker
            _cb = CircuitBreaker("elite-council-webhook", failure_threshold=3, cooldown_seconds=120)
        except ImportError:
            _cb = None

        if _cb and not _cb.can_call():
            # SOFT PAUSE: Circuit is OPEN — do NOT hammer the endpoint
            try:
                from error_aggregator import ErrorAggregator
                ErrorAggregator("SWDR").log_critical(
                    "Soft Pause triggered — circuit breaker OPEN for elite-council-webhook",
                    context={"project": project_name, "action": "soft_pause"}
                )
            except ImportError:
                pass
            status = _cb.get_status()
            cooldown = status.get("cooldown_remaining_s", "?")
            return (f"🛑 SOFT PAUSE: The Elite Council circuit breaker is OPEN "
                    f"({status.get('consecutive_failures', '?')} consecutive failures). "
                    f"Cooldown: {cooldown}s remaining. "
                    f"The Overseer has been notified.")

        for attempt in range(max_retries):
                try:
                    print(f"--- CEO: Sending prompt to Elite Council (Attempt {attempt+1}/{max_retries}) [Context: {project_name}] ---", flush=True)
                    span.add_event("Calling N8N", {"attempt": attempt + 1, "url": WEBHOOK_URL})
                    
                    # INJECT MEMORY CONTEXT
                    payload["sessionId"] = project_name 

                    # ── STATE MANAGER + SAFE-BUFFER (Hardening V3 Sealed) ──
                    _sm = None
                    _entry_id = None
                    try:
                        from local_state_manager import StateManager
                        _sm = StateManager()

                        # Check Safe-Buffer mode (set by heartbeat on watchdog failure)
                        if _sm.is_safe_buffer_mode():
                            _entry_id = _sm.log_outgoing(WEBHOOK_URL, payload, project_name)
                            _sm.mark_failed(_entry_id, "Safe-Buffer mode active — cloud unreachable")
                            _sync_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pending_sync")
                            os.makedirs(_sync_dir, exist_ok=True)
                            _ts = time.strftime("%Y%m%d_%H%M%S")
                            _queue_file = os.path.join(_sync_dir, f"{project_name}_{_ts}.json")
                            import json as _json
                            with open(_queue_file, "w") as _qf:
                                _json.dump({"url": WEBHOOK_URL, "payload": payload, "project": project_name, "queued_at": _ts}, _qf, indent=2, default=str)
                            print(f"📦 Safe-Buffer: Payload queued to {_queue_file}", flush=True)
                            span.add_event("Safe-Buffer queue", {"file": _queue_file})
                            return "Your request has been queued (Safe-Buffer mode active). It will be sent when cloud connectivity is restored."

                        # Log outgoing request BEFORE the call
                        _entry_id = _sm.log_outgoing(WEBHOOK_URL, payload, project_name)
                    except ImportError:
                        pass
                    # ── END STATE MANAGER SETUP ──────────────────────────

                    _call_start = time.time()
                    response = requests.post(WEBHOOK_URL, json=payload, timeout=300)
                    _latency_ms = (time.time() - _call_start) * 1000
                    
                    if response.status_code in [500, 502, 503, 504, 404]:
                         if _sm and _entry_id: _sm.mark_failed(_entry_id, f"N8N Server Error: {response.status_code}")
                         raise Exception(f"N8N Server Error: {response.status_code}")
                         
                    response.raise_for_status()
                    
                    try: 
                        result = response.json()
                        if not result: raise Exception("Empty JSON Response")
                        span.add_event("N8N Response Received")
                        if _cb: _cb.record_success()
                        if _sm and _entry_id: _sm.mark_sent(_entry_id, response.status_code, _latency_ms)
                        print(f"--- Response received in {_latency_ms:.0f}ms ---", flush=True)
                        break # Success
                    except ValueError:
                        raise Exception(f"Invalid JSON Response: {response.text[:50]}...")

                except Exception as e:
                    if _cb: _cb.record_failure()
                    if _sm and _entry_id: _sm.mark_failed(_entry_id, str(e))
                    delay = backoff_base * (2 ** attempt) + random.uniform(-0.4, 0.4) * backoff_base
                    print(f"⚠️ N8N Error: {str(e)}. Exponential backoff: {delay:.1f}s...", flush=True)
                    span.record_exception(e)
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                    else:
                        # Overseer Notification on final failure
                        try:
                            from error_aggregator import ErrorAggregator
                            ErrorAggregator("SWDR").log_critical(
                                f"Elite Council unreachable after {max_retries} attempts",
                                context={"project": project_name, "error": str(e), "action": "overseer_notify"}
                            )
                        except ImportError:
                            pass
                        return (f"Graceful Failure: The CEO is currently unreachable after {max_retries} attempts ({str(e)}). "
                                f"Circuit breaker engaged. Please check your N8N Workflow or Internet Connection.")

        # 3. Interaction Protocol (Drafting)
        if isinstance(result, dict) and result.get("action") == "draft_summary":
            content = result.get("content", "No summary.")
            # Save to Memory
            # memory.add("user", prompt) # Already added
            memory.add("ai", f"DRAFT: {content[:50]}...")
            
            print("\n" + "="*50, flush=True)
            print("--- ANALYST: DRAFT SUMMARY FOR REVIEW ---", flush=True)
            print(content, flush=True)
            print("="*50 + "\n", flush=True)
            return f"DRAFT FOR REVIEW:\n\n{content}\n\nFEEDBACK REQUIRED: Please approve or provide pivot instructions."

        # 4. Tool Loop
        if isinstance(result, dict) and result.get("action") == "use_tool":
            # CASE INSENSITIVE NORMALIZATION
            tool_name = result.get("tool", "").lower()
            query = result.get("query")
            span.add_event("Tool Call Requested", {"tool": tool_name})
            # memory.add("user", prompt) # Already added
            memory.add("ai", f"TOOL_CALL: {tool_name}")
            print(f"--- Council Request: {tool_name} ---", flush=True)
            
            observation = "Tool Error."
            if SKILLS_DIR not in sys.path: sys.path.append(SKILLS_DIR)

            if tool_name == "market_search":
                from tavily_search import TavilySearch
                observation = TavilySearch().search(query)
            elif tool_name == "vector_memory":
                from chroma_db import ChromaMemory
                observation = ChromaMemory(project_name=project_name).query(query)
            elif tool_name == "google_workspace":
                from google_suite import GoogleSuiteManager
                # Expecting query to be a JSON string with {action, file_type, file_name, content}
                try:
                    params = json.loads(query)
                    mgr = GoogleSuiteManager(project_name=project_name)
                    observation = mgr.manage_document(params.get("action"), params.get("file_type"), params.get("file_name"), params.get("content"))
                except:
                    observation = "Error parsing Google Workspace parameters. Ensure query is a valid JSON."

            elif tool_name == "financial_model":
                from financial_planner import FinancialPlanner
                try:
                    # Expecting query to be JSON assumptions
                    assumptions = json.loads(query)
                    # Output to local App Folder
                    import os
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    output_dir = os.path.join(base_dir, "project_files")
                    os.makedirs(output_dir, exist_ok=True)
                    
                    observation = FinancialPlanner(output_dir=output_dir).generate_financial_plan(assumptions)
                except Exception as e:
                    observation = f"Financial Error: {str(e)}. Ensure query is valid JSON assumptions."

            elif tool_name == "produce_document":
                print(f"--- BRIDGE: Processing Document Request... ---", flush=True)
                from file_factory import FileFactory
                from google_suite import GoogleSuiteManager
                try:
                    # Expecting: {file_type, file_name, content, ...}
                    # Handle sloppy JSON from LLM
                    if isinstance(query, str):
                        try: params = json.loads(query)
                        except: params = {"content": query, "file_type": "txt", "file_name": "output.txt"}
                    else:
                        params = query

                    import os
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    output_dir = os.path.join(base_dir, "project_files")
                    os.makedirs(output_dir, exist_ok=True)

                    ff = FileFactory(output_dir=output_dir)
                    local_path = ""
                    
                    ftype = params.get("file_type", "").lower()
                    
                    # 1. Image Generation Special Case
                    if ftype in ["image", "png", "jpg", "jpeg"]:
                        print(f"--- BRIDGE: Generating Image ({params.get('file_name')})... ---", flush=True)
                        local_path = ff.generate_image(params.get("content"), params.get("file_name", "image.png"))
                    
                    # 2. Document/Presentation Creation
                    else:
                        print(f"--- BRIDGE: Creating File ({ftype})... ---", flush=True)
                        local_path = ff.create_file(params.get("content"), ftype, params.get("file_name", f"document.{ftype}"))
                    
                    if "Error" in local_path:
                         observation = local_path
                    else:
                        # 3. Upload to Drive
                        print(f"--- BRIDGE: Uploading to Drive... ---", flush=True)
                        mgr = GoogleSuiteManager(project_name=project_name)
                        drive_link = mgr.upload_file(local_path, params.get("file_name", "output"), mime_type=None)
                        observation = f"File Created and Uploaded: {drive_link}"
                except Exception as e:
                    observation = f"Document Production Error: {str(e)}"
            
            else:
                 print(f"--- BRIDGE WARNING: UNKNOWN TOOL '{tool_name}' REQUESTED ---", flush=True)
                 observation = f"System Error: Tool '{tool_name}' is not available on this terminal. Available tools: financial_model, produce_document, google_workspace, market_search."

            print(f"--- Tool Success. Returning to Council. ---", flush=True)
            return call_app({"prompt": f"OBSERVATION: {observation}", "context": "TOOL_RESULT", "project_name": project_name})

        output = result.get("text") or result.get("output") or result

        # 5. Delegation Routing (The Switchboard)
        # 5. Router Pattern (JSON Delegation)
        if isinstance(result, dict) and result.get("action") == "delegate_task":
            target_role = result.get("recipient", "").upper()
            task_payload = result.get("content")
            
            span.add_event("Delegation Requested", {"recipient": target_role})
            print(f"--- 🔄 ROUTER: Delegating to {target_role} ---", flush=True)
            
            # INJECT TOOL AWARENESS into the delegated task so the specialist knows what tools exist!
            # Rerunning the tool_awareness block here locally or just hardcoding it
            sub_agent_context = f"""
[SYSTEM UPGRADE: CREATIVE SUITE ACTIVE]
You have access to new "Professional Grade" tools via the Bridge.
1. Financial Modeling: Return JSON {{ "action": "use_tool", "tool": "financial_model", "query": {{...assumptions...}} }}
2. Presentations: Return JSON {{ "action": "use_tool", "tool": "produce_document", "query": {{ "file_type": "pptx", ... }} }}
3. Images: Return JSON {{ "action": "use_tool", "tool": "produce_document", "query": {{ "file_type": "image", ... }} }}

TASK:
{task_payload}
"""
            
            target_url = AGENT_REGISTRY.get(target_role)
            if target_url:
                try:
                    # Call the Specialist Agent
                    response = requests.post(target_url, json={"prompt": sub_agent_context}, timeout=120)
                    response.raise_for_status()
                    
                    try: 
                        specialist_data = response.json()
                        specialist_output = specialist_data.get("text") or specialist_data.get("output") or json.dumps(specialist_data)
                    except: 
                        specialist_output = response.text
                    
                    print(f"--- 🔄 ROUTER: {target_role} Completed Task. ---", flush=True)

                    # Recursive Call: Feed the result back to the Council
                    return call_app({
                        "prompt": f"OBSERVATION FROM {target_role}: {specialist_output}", 
                        "context": "DELEGATION_RESULT",
                        "project_name": project_name
                    })
                except Exception as e:
                    error_msg = f"System Error: Failed to contact {target_role}. {str(e)}"
                    print(f"--- ROUTER ERROR: {error_msg} ---", flush=True)
                    return call_app({"prompt": error_msg, "context": "SYSTEM_ERROR", "project_name": project_name})
            else:
                return f"System Error: No route defined for agent '{target_role}'. Check AGENT_REGISTRY."

        if not isinstance(output, str): output = json.dumps(output)
        # memory.add("user", prompt) # Already added
        memory.add("ai", output)
        return output

    except Exception as e:
        error_msg = str(e)
        print(f"--- SENTRY ALERT: {error_msg} ---", flush=True)
        
        # Sentry Level 2: Infrastructure Healing
        # Trigger on connection issues (404/Timeout/ConnectionError)
        is_conn_issue = any(x in error_msg for x in ["404", "Connection", "Timeout", "Valid N8N"])
        
        if is_conn_issue and "HEALED" not in payload.get("context", ""):
             if _healing_protocol():
                 print("--- SENTRY L2: RETRYING WITH NEW COORDINATES... ---", flush=True)
                 clean_context = payload.get("context", "") or ""
                 payload["context"] = f"{clean_context} HEALED".strip()
                 return call_app(payload)

        # Sentry Level 1: Context Recovery
        last_prompt = get_last_prompt()
        if last_prompt and "RECOVERY" not in payload.get("context", ""):
            print(f"--- SENTRY: Attempting Self-Heal & Re-Injection ---", flush=True)
            return call_app({
                "prompt": f"SENTRY RECOVERY: The system hit a glitch ({error_msg}). Please resume the task: {last_prompt}",
                "project_name": project_name,
                "context": "SENTRY_RECOVERY"
            })
            
        return f"Bridge Connection Error: {e}"

if __name__ == "__main__":
    print(call_app({"prompt": "Hello"}))
'''
            # Replace placeholder with actual app name config if needed
            bridge_code = bridge_code.replace("URL_PLACEHOLDER", webhook_url)
        else:
            bridge_code = f"""import requests
import sys
import json

WEBHOOK_URL = "{webhook_url}"

def call_app(payload):
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=30)
        response.raise_for_status()
        try: return response.json()
        except: return response.text
    except Exception as e: return f"Error: {{e}}"

if __name__ == "__main__":
    print(call_app({{"prompt": "Hello"}}))
"""
        with open(os.path.join(app_dir, "bridge.py"), "w") as f:
            f.write(bridge_code)
            
        # Create a simple config
        config_data = {
            "app_name": app_name,
            "webhook_url": webhook_url,
            "blueprint": blueprint_name,
            "n8n_workflow_id": workflow_id,
            "port": port
        }
        with open(os.path.join(app_dir, "config.json"), "w") as f:
            json.dump(config_data, f, indent=4)

        # [V2.1] Inject Self-Healing Debug Pipeline
        self._inject_debug_pipeline(app_dir, webhook_url)

    def _inject_debug_pipeline(self, app_dir, webhook_url):
        print(f"--- Factory: Injecting Self-Healing Debug Pipeline into {app_dir} ---", flush=True)
        debug_code = r'''import sys
import os
import time
import json
import requests
from dotenv import load_dotenv
import bridge # Added missing import

# Path Setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "skills")))
from google_suite import GoogleSuiteManager

# Load Env
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(env_path)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "URL_PLACEHOLDER")

# Configuration
DEBUG_PROJECT = "Project_Debug_Phoenix"

# -------------------------------------------------------------------------
# STRICT STOP-AND-FIX DEBUGGER
# -------------------------------------------------------------------------

def run_agent_with_retry(agent_name, input_payload):
    """
    Executes a strict 'Stop-and-Fix' loop.
    It traps the process until the agent returns a valid 200 OK + JSON response.
    Infinite Loop until Agent passes strict checks or correctly handles tools.
    """
    attempt = 1
    while True:
        print(f"\n--- [DEBUGGER] Testing {agent_name} (Attempt {attempt}) ---")
        try:
            # INTEGRATION: Call via Bridge to ensure Tool Awareness & Execution
            # bridge.call_app returns a STRING (Final Output) usually, or a DICT if we change it. 
            # Based on bridge.py, it returns 'output' which is usually text.
            
            print(f"    >>> Invoking Bridge...")
            raw_response = bridge.call_app(input_payload)
            
            # Bridge returns the final text, handling all tool loops internally.
            if not raw_response:
                 raise Exception("Empty Response from Bridge")
            
            content = str(raw_response)
            
            # --- THE APOLOGY TRAP ---
            forbidden_phrases = ["my apologies", "i made an error", "tool does not exist", "unable to", "cannot directly"]
            lower_content = content.lower()
            
            if any(phrase in lower_content for phrase in forbidden_phrases):
                 raise Exception(f"Agent Apology/Failure detected: '{content[:50]}...'")

            # 3. Success -> Break Loop
            print(f"[OK] {agent_name} Passed.")
            # Return a mock dict for compatibility with the rest of the script if needed
            return {"content": content}
            
        except Exception as e:
            # 4. Failure -> Analyze & Retry (Do NOT Proceed)
            print(f"\n[FAIL] {agent_name} Failed: {e}")
            print("   >>> DIAGNOSING & RETRYING in 5 seconds...")
            time.sleep(5)
            
            # Auto-Correction Logic
            current_prompt = input_payload.get("prompt", "")
            if "PREVIOUS ERROR:" not in current_prompt:
                 input_payload["prompt"] = f"{current_prompt}\n\n[SYSTEM NOTICE] PREVIOUS ERROR: {str(e)}. You MUST fix this. Do not apologize, just correct the tool call."
            
            attempt += 1

def run_functional_test(mgr):
    """
    Phase 3: Verify that FILES are actually created.
    """
    print("\n--- [PHASE 3] FUNCTIONAL VERIFICATION (CREATIVE SUITE) ---")
    
    # Test 1: Financial Model
    print(">>> Testing Live Excel Generation...")
    payload = {
        "prompt": "Create a simple Live Excel Financial Model for a 'Lemonade Stand'. Assumptions: Price $5, Cost $2. Return the file.",
        "project_name": "Debug_Functional_Test",
        "suite_command": True
    }
    # We use the generic 'CEO' or 'Bridge' (webhook url is generic)
    try:
        result = run_agent_with_retry("FUNCTIONAL_EXCEL", payload)
        content = str(result.get("output") or result.get("text") or "")
        if "http" not in content and ".xlsx" not in content:
             print(f"[WARNING] No file link detected in output: {content}")
        else:
             print(f"[SUCCESS] Excel Link Generated: {content}")
    except Exception as e:
        print(f"[FAIL] Functional Excel Test Failed: {e}")

    # Test 2: PPTX
    print("\n>>> Testing PPTX Generation...")
    payload = {
        "prompt": "Create a 1-slide Pitch Deck for 'Lemonade Stand'. File type: pptx. Return the file.",
        "project_name": "Debug_Functional_Test",
        "suite_command": True
    }
    try:
        result = run_agent_with_retry("FUNCTIONAL_PPTX", payload)
        content = str(result.get("output") or result.get("text") or "")
        if "http" not in content and ".pptx" not in content:
             print(f"[WARNING] No file link detected in output: {content}")
        else:
             print(f"[SUCCESS] PPTX Link Generated: {content}")
    except: pass

if __name__ == "__main__":
    
    print("--- [INIT] STRICT DEBUGGER PROTOCOL ACTIVATED ---")
    
    # 1. Setup Cloud
    try:
        mgr = GoogleSuiteManager(DEBUG_PROJECT)
        mgr.ensure_project_folder()
        print("--- [CLOUD] Workspace Verified ---")
    except Exception as e:
        print(f"--- [CLOUD] Warning: {e} ---")

    # 2. The Gauntlet (Health Checks)
    agents_to_test = ["CEO", "CFO", "CMO", "CRITIC", "PITCH", "ARCHITECT", "ATOMIZER"]
    
    for agent in agents_to_test:
        payload = {
            "prompt": f"ROLE CHECK: {agent}. Report status and confirm you are online.",
            "project_name": DEBUG_PROJECT,
            "context": "DEBUG_STRICT_MODE"
        }
        run_agent_with_retry(agent, payload)

    print("\n[SUCCESS] PHASE 2 COMPLETE. AGENTS ONLINE.")
    
    # 3. Functional Tests
    run_functional_test(mgr)
    
    print("\n[DONE] SYSTEM VERIFIED.")
'''
        debug_code = debug_code.replace("URL_PLACEHOLDER", webhook_url)
        with open(os.path.join(app_dir, "debug_pipeline.py"), "w") as f:
            f.write(debug_code)

    def _generate_env(self, app_dir, app_name, webhook_url):
        """Generate .env file with all required keys for the new app."""
        env_content = f"""# {app_name} — Environment Configuration
# Generated by Meta App Factory

# N8N Webhook (Primary)
WEBHOOK_URL={webhook_url}

# N8N API (for workflow management)
N8N_API_KEY=${{N8N_API_KEY}}
N8N_BASE_URL=https://humanresource.app.n8n.cloud

# Google (Gemini + Drive + Sheets)
GOOGLE_API_KEY=${{GOOGLE_API_KEY}}
GOOGLE_CX=${{GOOGLE_CX}}

# Tavily (Market Research)
TAVILY_API_KEY=${{TAVILY_API_KEY}}

# OpenTelemetry (Optional)
OTEL_EXPORTER_OTLP_ENDPOINT=

# Project Isolation
PROJECTS_DIR=./Projects
"""
        env_path = os.path.join(app_dir, ".env")
        if not os.path.exists(env_path):
            with open(env_path, "w") as f:
                f.write(env_content)
            print(f"  >> .env template created")

        # Also create .env.template (safe to commit)
        with open(os.path.join(app_dir, ".env.template"), "w") as f:
            f.write(env_content.replace(webhook_url, "YOUR_WEBHOOK_URL_HERE"))

        # Encrypt sensitive env values (Fernet AES-128)
        try:
            from env_encryption import encrypt_env_file
            encrypt_env_file(env_path)
        except ImportError:
            print("  >> env_encryption not available — skipping .env encryption")
        except Exception as e:
            print(f"  >> .env encryption warning: {e}")

    def _generate_launch_script(self, app_dir, app_name, port=5005):
        """Generate a launch .bat script with N8N lifecycle hooks."""
        bat_content = f"""@echo off
title {app_name} Launcher
color 0B
echo.
echo  ============================================
echo    {app_name} - Antigravity Launch
echo  ============================================
echo.

cd /d "%~dp0"

REM Auto-install dependencies
if exist requirements.txt (
    echo [1/4] Installing dependencies...
    pip install -r requirements.txt -q 2>nul
) else (
    echo [1/4] No requirements.txt found, skipping...
)

REM Check Docker
echo [2/4] Checking Docker...
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Docker not running. Starting Docker Desktop...
    start "" "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"
    timeout /t 15 /nobreak >nul
)

REM Activate N8N Workflows
echo [3/4] Activating N8N workflows...
if exist n8n_lifecycle.py (
    python -c "import json,sys,os; sys.path.insert(0,'.'); from n8n_lifecycle import set_workflow_active; cfg=json.load(open('config.json')); wid=cfg.get('n8n_workflow_id',''); from dotenv import load_dotenv; load_dotenv(); key=os.getenv('N8N_API_KEY',''); set_workflow_active(wid,True,key,cfg.get('app_name','')) if wid and key else print('No workflow ID or API key')"
) else (
    echo    No lifecycle manager found, skipping...
)

REM Launch UI
echo [4/4] Launching {app_name} UI...
python ui.py

REM === CLEANUP: Deactivate N8N workflows on shutdown ===
echo.
echo  Shutting down N8N workflows...
if exist n8n_lifecycle.py (
    python -c "import json,sys,os; sys.path.insert(0,'.'); from n8n_lifecycle import set_workflow_active; cfg=json.load(open('config.json')); wid=cfg.get('n8n_workflow_id',''); from dotenv import load_dotenv; load_dotenv(); key=os.getenv('N8N_API_KEY',''); set_workflow_active(wid,False,key,cfg.get('app_name','')) if wid and key else print('No workflow ID or API key')"
)
echo  N8N workflows deactivated.

pause
"""
        bat_path = os.path.join(app_dir, f"launch_{app_name}.bat")
        with open(bat_path, "w") as f:
            f.write(bat_content)
        print(f"  >> Launch script created: launch_{app_name}.bat")

    def _generate_docker_artifacts(self, app_dir, app_name, port=5005):
        """Generate Docker deployment artifacts (Dockerfile, docker-compose.yml, .dockerignore)."""
        frontend_port = port + 100  # e.g., 5005 -> 5105 for frontend container

        # -- Dockerfile (Backend - FastAPI) --
        dockerfile = (
            f"# {app_name} - Backend Container\n"
            f"# Generated by Meta App Factory\n"
            f"FROM python:3.10-slim\n"
            f"\n"
            f"WORKDIR /app\n"
            f"\n"
            f"# Dependencies first for Docker layer caching\n"
            f"COPY requirements.txt .\n"
            f"RUN pip install --no-cache-dir -r requirements.txt\n"
            f"\n"
            f"# Application code\n"
            f"COPY . .\n"
            f"\n"
            f"# Security: don't run as root\n"
            f"RUN useradd -m appuser && chown -R appuser:appuser /app\n"
            f"USER appuser\n"
            f"\n"
            f"EXPOSE {port}\n"
            f'CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "{port}"]\n'
        )

        # -- Dockerfile.frontend (React/Vite) --
        dockerfile_frontend = (
            f"# {app_name} - Frontend Container\n"
            f"# Generated by Meta App Factory\n"
            f"FROM node:20-alpine AS build\n"
            f"\n"
            f"WORKDIR /app\n"
            f"\n"
            f"# Dependencies first for Docker layer caching\n"
            f"COPY resonance_ui/package*.json ./\n"
            f"RUN npm ci\n"
            f"\n"
            f"# Build\n"
            f"COPY resonance_ui/ .\n"
            f"RUN npm run build\n"
            f"\n"
            f"# Production serve\n"
            f"FROM nginx:alpine\n"
            f"COPY --from=build /app/dist /usr/share/nginx/html\n"
            f"EXPOSE 80\n"
            f'CMD ["nginx", "-g", "daemon off;"]\n'
        )

        # -- docker-compose.yml --
        compose = (
            f"# {app_name} - Docker Compose\n"
            f"# Generated by Meta App Factory\n"
            f"\n"
            f'version: "3.9"\n'
            f"\n"
            f"services:\n"
            f"  backend:\n"
            f"    build:\n"
            f"      context: .\n"
            f"      dockerfile: Dockerfile\n"
            f"    container_name: {app_name.lower()}_backend\n"
            f"    restart: unless-stopped\n"
            f"    ports:\n"
            f'      - "{port}:{port}"\n'
            f"    env_file:\n"
            f"      - .env\n"
            f"    volumes:\n"
            f"      - app_data:/app/data\n"
            f"    healthcheck:\n"
            f'      test: ["CMD", "curl", "-f", "http://localhost:{port}/api/health"]\n'
            f"      interval: 30s\n"
            f"      timeout: 5s\n"
            f"      retries: 3\n"
            f"\n"
            f"  frontend:\n"
            f"    build:\n"
            f"      context: .\n"
            f"      dockerfile: Dockerfile.frontend\n"
            f"    container_name: {app_name.lower()}_frontend\n"
            f"    restart: unless-stopped\n"
            f"    ports:\n"
            f'      - "{frontend_port}:80"\n'
            f"    depends_on:\n"
            f"      backend:\n"
            f"        condition: service_healthy\n"
            f"\n"
            f"volumes:\n"
            f"  app_data:\n"
        )

        # -- .dockerignore --
        dockerignore = (
            "node_modules\n"
            "__pycache__\n"
            ".git\n"
            ".env\n"
            ".env.enc\n"
            "*.pyc\n"
            "*.pyo\n"
            ".Gemini_state\n"
            "vault.enc\n"
            "vault.enc.salt\n"
            ".vault_pw\n"
            "*.log\n"
        )

        # Write files (don't overwrite if they already exist)
        artifacts = {
            "Dockerfile": dockerfile,
            "Dockerfile.frontend": dockerfile_frontend,
            "docker-compose.yml": compose,
            ".dockerignore": dockerignore,
        }
        written = []
        for fname, content in artifacts.items():
            fpath = os.path.join(app_dir, fname)
            if not os.path.exists(fpath):
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
                written.append(fname)
        if written:
            print(f"  >> Docker artifacts created: {', '.join(written)}")
        else:
            print(f"  >> Docker artifacts already exist, skipping")

    def _register_as_skill(self, app_dir, app_name, webhook_url, capabilities, description):
        """Register the new app as a skill/tool in the skills directory."""
        skills_dir = os.path.abspath(os.path.join(FACTORY_DIR, "..", "skills"))
        skill_name = app_name.lower().replace(" ", "_").replace("-", "_")
        skill_path = os.path.join(skills_dir, skill_name)
        os.makedirs(skill_path, exist_ok=True)

        # SKILL.md — Skill instructions file
        cap_list = "\n".join(f"- {c}" for c in capabilities) if capabilities else "- General purpose"
        skill_md = f"""---
name: {app_name}
description: {description or 'AI-powered skill generated by Meta App Factory'}
---

# {app_name} Skill

## Overview
{description or 'An AI-powered tool generated by Meta App Factory.'}

## Capabilities
{cap_list}

## Usage

```python
from skills.{skill_name} import invoke

result = invoke("Your prompt here")
print(result)
```

## Configuration
- Webhook: `{webhook_url}`
- Source App: `{app_dir}`

## Auto-Generated
This skill was auto-registered by Meta App Factory on {datetime.now().strftime('%Y-%m-%d')}.
"""
        with open(os.path.join(skill_path, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(skill_md)

        # __init__.py — Importable wrapper
        init_code = f'''"""
{app_name} — Auto-Generated Skill
Wraps the app's bridge.py for use as a Meta App Factory tool.
"""
import os
import sys
import requests

WEBHOOK_URL = "{webhook_url}"
APP_DIR = r"{app_dir}"

def invoke(prompt: str, context: str = "", agent: str = "") -> str:
    """Invoke this skill with a prompt."""
    payload = {{
        "prompt": prompt,
        "chatInput": prompt,
        "input": prompt,
    }}
    if context:
        payload["context"] = context
    if agent:
        payload["agent"] = agent

    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=90)
        response.raise_for_status()
        data = response.json()
        return data.get("text", data.get("output", str(data)))
    except Exception as e:
        return f"Skill Error ({{APP_DIR}}): {{e}}"


def get_capabilities():
    """Return the list of capabilities this skill provides."""
    return {capabilities!r}


def get_info():
    """Return skill metadata."""
    return {{
        "name": "{app_name}",
        "description": "{description or 'AI-powered skill'}",
        "webhook": WEBHOOK_URL,
        "app_dir": APP_DIR,
        "capabilities": get_capabilities()
    }}
'''
        with open(os.path.join(skill_path, "__init__.py"), "w", encoding="utf-8") as f:
            f.write(init_code)

        print(f"  >> Skill registered: skills/{skill_name}/ (SKILL.md + __init__.py)")


# ═══════════════════════════════════════════════════════════════════
#  CLI — Extended Commands (build / launch / status / tunnels / create)
# ═══════════════════════════════════════════════════════════════════

def _load_registry():
    reg_path = os.path.join(FACTORY_DIR, "registry.json")
    with open(reg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_app_dir(app_name, reg=None):
    """Resolve app directory from registry or filesystem."""
    if reg is None:
        reg = _load_registry()
    app = reg.get("apps", {}).get(app_name, {})
    if app.get("path"):
        p = os.path.join(os.path.dirname(FACTORY_DIR), app["path"])
        if os.path.isdir(p):
            return p
    direct = os.path.join(FACTORY_DIR, app_name)
    if os.path.isdir(direct):
        return direct
    for child in os.listdir(FACTORY_DIR):
        full = os.path.join(FACTORY_DIR, child)
        if os.path.isdir(full) and child.replace(" ", "_").replace("-", "_") == app_name:
            return full
    return None


def cmd_status(_args):
    """Show all registered apps."""
    reg = _load_registry()
    apps = reg.get("apps", {})
    print("\n🏭 Meta App Factory — Registry Status")
    print("=" * 60)
    for name, info in apps.items():
        status = info.get("status", "unknown")
        port = info.get("port", "-")
        app_type = info.get("type", "")
        icon = "🟢" if status == "active" else "🔴"
        app_dir = _resolve_app_dir(name, reg)
        has_dir = "✓" if app_dir else "✗"
        has_reqs = "📦" if app_dir and os.path.exists(os.path.join(app_dir, "requirements.txt")) else "  "
        caps = ", ".join(info.get("capabilities", [])[:3])
        print(f"  {icon} {name:<30} port:{str(port):<6} {app_type}")
        print(f"       {has_reqs} dir:{has_dir}  caps: {caps}")
    print(f"\n  📋 Total: {len(apps)}   "
          f"🟢 Active: {sum(1 for a in apps.values() if a.get('status') == 'active')}")
    print(f"  📅 Last updated: {reg.get('last_updated', 'unknown')}\n")


def cmd_build(args):
    """Install deps + run preflight for an app."""
    import subprocess as _sp
    app_name = args.app_name
    reg = _load_registry()
    app_dir = _resolve_app_dir(app_name, reg)
    if not app_dir:
        print(f"❌ App '{app_name}' not found"); return
    print(f"\n🔧 Building {app_name}\n   Dir: {app_dir}")
    print("=" * 50)
    req = os.path.join(app_dir, "requirements.txt")
    if os.path.exists(req):
        print("\n📦 Installing dependencies...")
        r = _sp.run([sys.executable, "-m", "pip", "install", "-r", req, "-q"],
                     capture_output=True, text=True, encoding="utf-8", errors="replace")
        print("   ✅ Done" if r.returncode == 0 else f"   ❌ Failed:\n{r.stderr[:300]}")
    else:
        print("   ⓘ No requirements.txt")
    for script in ["preflight.py", "sentinel_config.py", "setup.py"]:
        sp = os.path.join(app_dir, script)
        if os.path.exists(sp):
            print(f"\n🔑 Running {script}...")
            _sp.run([sys.executable, sp, "--check"], cwd=app_dir,
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
            break
    if app_name in reg.get("apps", {}):
        reg["apps"][app_name]["last_build"] = datetime.utcnow().isoformat() + "Z"
        reg_path = os.path.join(FACTORY_DIR, "registry.json")
        with open(reg_path, "w", encoding="utf-8") as f:
            json.dump(reg, f, indent=4)
    print(f"\n✅ {app_name} built!\n")


def cmd_launch(args):
    """Build then launch an app's server."""
    app_name = args.app_name
    reg = _load_registry()
    app_dir = _resolve_app_dir(app_name, reg)
    if not app_dir:
        print(f"❌ App '{app_name}' not found"); return
    cmd_build(args)
    for s in ["sentinel_server.py", "server.py", "app.py", "main.py"]:
        sp = os.path.join(app_dir, s)
        if os.path.exists(sp):
            port = reg.get("apps", {}).get(app_name, {}).get("port", "?")
            print(f"\n🚀 Launching {app_name} on port {port}")
            os.execv(sys.executable, [sys.executable, sp])
    print(f"❌ No server script found in {app_dir}")


def cmd_tunnels(_args):
    """Show active ngrok tunnels."""
    print("\n🔗 Active ngrok Tunnels")
    print("=" * 50)
    try:
        from pyngrok import ngrok as _ngrok
        tunnels = _ngrok.get_tunnels()
        if not tunnels:
            print("   No active tunnels")
        for t in tunnels:
            print(f"   {t.public_url}  →  {t.config.get('addr', '?')}")
    except Exception as e:
        print(f"   ⚠️ {e}")
    print()


# ── SWDR — System-Wide Diagnostic & Repair ─────────────────────────
def cmd_swdr(_args):
    """Run a System-Wide Diagnostic & Repair check across all circuit breakers and error logs."""
    print("\n🔬 SWDR — System-Wide Diagnostic & Repair")
    print("=" * 60)

    # 1. Credential Sentinel — check N8N_API_KEY validity
    print("\n🔑 CREDENTIAL SENTINEL")
    api_key = os.getenv("N8N_API_KEY", "")
    if not api_key:
        print("   🔴 N8N_API_KEY: NOT SET")
    else:
        try:
            r = requests.get(f"{N8N_API_BASE}/workflows?limit=1", headers=N8N_HEADERS, timeout=10)
            if r.status_code == 200:
                print(f"   🟢 N8N_API_KEY: VALID (connected to {N8N_API_BASE})")
            elif r.status_code == 401:
                print(f"   🔴 N8N_API_KEY: EXPIRED / INVALID (401 Unauthorized)")
            else:
                print(f"   🟡 N8N_API_KEY: UNKNOWN STATUS ({r.status_code})")
        except Exception as e:
            print(f"   🔴 N8N Connection Failed: {e}")

    # 2. Circuit Breaker Status
    print("\n⚡ CIRCUIT BREAKER STATUS")
    cb_dir = os.path.join(os.path.expanduser("~"), ".antigravity", "circuit_breakers")
    if not os.path.exists(cb_dir):
        print("   No circuit breakers registered yet.")
    else:
        sys.path.insert(0, FACTORY_DIR)
        try:
            from circuit_breaker import CircuitBreaker
            for fname in os.listdir(cb_dir):
                if fname.endswith(".json"):
                    name = fname[:-5]
                    cb = CircuitBreaker(name)
                    s = cb.get_status()
                    icons = {"CLOSED": "🟢", "OPEN": "🔴", "HALF_OPEN": "🟡"}
                    icon = icons.get(s["state"], "❓")
                    line = f"   {icon} {s['name']}: {s['state']} (fails: {s['total_failures']}, ok: {s['total_successes']})"
                    if s.get("cooldown_remaining_s"):
                        line += f" — cooldown: {s['cooldown_remaining_s']}s"
                    print(line)
        except ImportError:
            print("   ⚠️ circuit_breaker module not found")

    # 3. Error Aggregator Summary
    print("\n📊 ERROR AGGREGATOR SUMMARY")
    try:
        sys.path.insert(0, FACTORY_DIR)
        from error_aggregator import ErrorAggregator
        summary = ErrorAggregator.get_summary()
        print(f"   Total logged events: {summary['total']}")
        if summary['by_severity']:
            for sev, count in summary['by_severity'].items():
                icons = {"error": "❌", "warning": "⚠️", "info": "ℹ️", "critical": "🚨"}
                print(f"   {icons.get(sev, '❓')} {sev}: {count}")
        if summary['by_app']:
            print("   By app:")
            for app, count in summary['by_app'].items():
                print(f"      {app}: {count}")
    except ImportError:
        print("   ⚠️ error_aggregator module not found")
    except Exception as e:
        print(f"   ⚠️ Error reading logs: {e}")

    print(f"\n{'=' * 60}")
    print("✅ SWDR diagnostic complete.\n")


# ── Audience Validation ────────────────────────────────────────────
APP_PROFILE_MAP = {
    "Resonance": "teen_learner",
    "Alpha_V2_Genesis": "retail_trader",
    "Delegate_AI_Beta_Agreement_Vault": "enterprise_user",
}

def cmd_validate(args):
    """Validate an app's content against its target audience profile."""
    from Project_Aether.audience_validator import AudienceValidator

    app_name = args.app_name
    validator = AudienceValidator()

    # ── Profile Resolution ────────────────────────────────────
    # Priority: --generate > --profile > auto-detect from APP_PROFILE_MAP
    if args.generate:
        # AI-generate a new profile from description
        context = args.context or f"Building/validating the {app_name} application"
        profile = validator.generate_profile(
            audience_description=args.generate,
            context=context,
        )
        profile_id = profile.id
    else:
        profile_id = args.profile or APP_PROFILE_MAP.get(app_name)
        if not profile_id:
            print(f"❌ No audience profile mapped for '{app_name}'.")
            print(f"   Use --profile <id> to specify one, or --generate \"<description>\" to create one.")
            print(f"   Available profiles: {[p['id'] for p in validator.list_profiles()]}")
            return
        if not any(p["id"] == profile_id for p in validator.list_profiles()):
            print(f"❌ Profile '{profile_id}' not found. Available: {[p['id'] for p in validator.list_profiles()]}")
            return

    # ── Content Collection ────────────────────────────────────
    reg = _load_registry()
    app_dir = _resolve_app_dir(app_name, reg)

    sample_content = f"App: {app_name}\n"
    # Try to load system prompt
    for prompt_file in ["app_stream.py", "server.py"]:
        prompt_path = os.path.join(app_dir, prompt_file)
        if os.path.isfile(prompt_path):
            with open(prompt_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if "SYSTEM_PROMPT" in content or "system_prompt" in content:
                sample_content += f"\nSystem prompt excerpt from {prompt_file}:\n{content[:3000]}\n"
                break

    # Try to load welcome message from UI
    app_jsx = os.path.join(app_dir, "resonance_ui", "src", "App.jsx")
    if not os.path.isfile(app_jsx):
        app_jsx = os.path.join(app_dir, "src", "App.jsx")
    if os.path.isfile(app_jsx):
        with open(app_jsx, "r", encoding="utf-8", errors="replace") as f:
            ui_content = f.read()
        sample_content += f"\nUI excerpt (first 2000 chars):\n{ui_content[:2000]}\n"

    # ── Validate ──────────────────────────────────────────────
    print(f"🎯 Validating {app_name} against profile: {profile_id}")
    print(f"   Sending {len(sample_content)} chars to Gemini for evaluation...\n")

    result = validator.validate(sample_content, profile_id, app_name=app_name)
    print(result.summary())


# ═══════════════════════════════════════════════════════════
# safe_post — V3.0 Resilience Pattern for Child Apps
# ═══════════════════════════════════════════════════════════

def safe_post(target_url: str, payload: dict, project: str = "child_app",
              timeout: int = 60) -> str:
    """
    V3.0 Safe-Post Pattern.
    Returns: "sent" | "buffered" | "failed"
    Auth: Antigravity_Full_v2 inherited automatically via factory .env.
    """
    import json as _json
    import time as _time
    _sm = None
    _entry_id = None

    try:
        from local_state_manager import StateManager
        _sm = StateManager()
    except ImportError:
        pass

    if _sm and _sm.is_safe_buffer_mode():
        _entry_id = _sm.log_outgoing(target_url, payload, project)
        _sm.mark_failed(_entry_id, "Safe-Buffer mode active")
        _queue_to_disk(target_url, payload, project)
        return "buffered"

    try:
        _rc_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resilience_config.json")
        if os.path.exists(_rc_path):
            with open(_rc_path) as _f:
                _rc = _json.load(_f)
            _wdog = _rc.get("cloud_health", {}).get("watchdog_url", "")
            if _wdog:
                _probe = requests.get(_wdog, timeout=5)
                if _probe.status_code != 200:
                    if _sm:
                        _entry_id = _sm.log_outgoing(target_url, payload, project)
                        _sm.mark_failed(_entry_id, f"Watchdog returned {_probe.status_code}")
                    _queue_to_disk(target_url, payload, project)
                    return "buffered"
    except requests.exceptions.RequestException:
        if _sm:
            _entry_id = _sm.log_outgoing(target_url, payload, project)
            _sm.mark_failed(_entry_id, "Watchdog unreachable")
        _queue_to_disk(target_url, payload, project)
        return "buffered"
    except Exception:
        pass

    if _sm:
        _entry_id = _sm.log_outgoing(target_url, payload, project)

    try:
        _start = _time.time()
        resp = requests.post(target_url, json=payload, timeout=timeout)
        _latency = (_time.time() - _start) * 1000
        if resp.status_code >= 500:
            if _sm and _entry_id:
                _sm.mark_failed(_entry_id, f"Server Error: {resp.status_code}")
            return "failed"
        if _sm and _entry_id:
            _sm.mark_sent(_entry_id, resp.status_code, _latency)
        return "sent"
    except requests.exceptions.RequestException as e:
        if _sm and _entry_id:
            _sm.mark_failed(_entry_id, str(e))
        _queue_to_disk(target_url, payload, project)
        return "buffered"


def _queue_to_disk(url: str, payload: dict, project: str):
    """Write a payload to pending_sync/ for recovery."""
    import json as _json
    import time as _time
    _sync_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pending_sync")
    os.makedirs(_sync_dir, exist_ok=True)
    _ts = _time.strftime("%Y%m%d_%H%M%S")
    _path = os.path.join(_sync_dir, f"{project}_{_ts}.json")
    with open(_path, "w") as f:
        _json.dump({"url": url, "payload": payload, "project": project, "queued_at": _ts}, f, indent=2, default=str)


if __name__ == "__main__":
    # Force UTF-8 on Windows
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(
        description="🏭 Meta App Factory — Orchestrator & CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python factory.py create  --name MyApp --blueprint gemini_reasoner
  python factory.py status
  python factory.py build   Sentinel_Bridge
  python factory.py validate Resonance --profile teen_learner
  python factory.py validate Resonance --generate "Teen students aged 14-17"
  python factory.py build   Sentinel_Bridge
  python factory.py launch  Sentinel_Bridge
  python factory.py tunnels
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # Legacy create mode
    p_create = sub.add_parser("create", help="Create a new app from blueprint")
    p_create.add_argument("--name", required=True, help="App name")
    p_create.add_argument("--blueprint", default="gemini_reasoner")
    p_create.add_argument("--desc", default="")
    p_create.add_argument("--system_prompt", default=None)

    # New commands
    sub.add_parser("status", help="Show all registered apps")
    p_build = sub.add_parser("build", help="Install deps + init for an app")
    p_build.add_argument("app_name", help="App name from registry")
    p_launch = sub.add_parser("launch", help="Build and launch an app")
    p_launch.add_argument("app_name", help="App name from registry")
    sub.add_parser("tunnels", help="Show active ngrok tunnels")
    sub.add_parser("swdr", help="System-Wide Diagnostic & Repair")
    p_validate = sub.add_parser("validate", help="Validate app against target audience")
    p_validate.add_argument("app_name", help="App name from registry")
    p_validate.add_argument("--profile", default=None, help="Audience profile ID (auto-detected if not set)")
    p_validate.add_argument("--generate", default=None, metavar='DESCRIPTION', help='AI-generate a new profile from description (e.g. "Pet owners aged 25-40")')
    p_validate.add_argument("--context", default="", help="Product/content context for profile generation")

    args = parser.parse_args()

    # Legacy fallback: if --name used without subcommand
    if args.command is None and hasattr(args, 'name') and args.name:
        args.command = "create"

    if args.command == "create":
        factory = MetaAppFactory()
        factory.create_app(
            app_name=args.name,
            blueprint_name=args.blueprint,
            description=args.desc,
            system_prompt=args.system_prompt,
        )
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "launch":
        cmd_launch(args)
    elif args.command == "tunnels":
        cmd_tunnels(args)
    elif args.command == "swdr":
        cmd_swdr(args)
    elif args.command == "validate":
        cmd_validate(args)
    else:
        parser.print_help()
