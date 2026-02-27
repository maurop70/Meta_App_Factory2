import os
import sys
import json
import requests
from dotenv import load_dotenv

# --- FLIGHT RECORDER: OpenTelemetry Setup ---
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

# Load environment variables
load_dotenv()

# Configuration from .env or defaults
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://humanresource.app.n8n.cloud/webhook/gemini-flash")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.getenv("PROJECTS_DIR", os.path.join(BASE_DIR, "Projects"))

# Docker Path Guard
if os.path.exists("/skills"):
    SKILLS_DIR = "/skills"
else:
    SKILLS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "skills"))

if SKILLS_DIR not in sys.path: sys.path.append(SKILLS_DIR)

# [CRITICAL] Pre-load Skills to ensure registration
from financial_planner import FinancialPlanner
from file_factory import FileFactory
from google_suite import GoogleSuiteManager

# Vision Skill - safe optional import
try:
    from list_files import get_triad_context, list_files as _list_files_skill
    VISION_SKILL_AVAILABLE = True
except ImportError:
    VISION_SKILL_AVAILABLE = False
    get_triad_context = None

# [ROUTER CONFIG] Specialist Agent Registry
# Verified Active URLs — synced by Zero-G Diagnostic (2026-02-24)
AGENT_REGISTRY = {
    # The Core Team (Verified ACTIVE)
    "CFO": "https://humanresource.app.n8n.cloud/webhook/cfo",          # cfo-v2 INACTIVE, using legacy cfo (ACTIVE)
    "CMO": "https://humanresource.app.n8n.cloud/webhook/cmo-v2",        # ACTIVE
    "HR": "https://humanresource.app.n8n.cloud/webhook/hr",             # ACTIVE

    # The New Special Forces (Verified ACTIVE)
    "CRITIC": "https://humanresource.app.n8n.cloud/webhook/critic-v2",  # ACTIVE
    "PITCH": "https://humanresource.app.n8n.cloud/webhook/pitch-v2",    # ACTIVE
    "ATOMIZER": "https://humanresource.app.n8n.cloud/webhook/atomizer-v2",  # ACTIVE
    "ARCHITECT": "https://humanresource.app.n8n.cloud/webhook/architect-v2",  # ACTIVE
    "PRESENTATION_ARCHITECT": "https://humanresource.app.n8n.cloud/webhook/architect-v2",  # ACTIVE

    # Claude Executor (Triad Protocol Execution Engine)
    # Primary: 'Claude Executor (Triad Protocol)' at /webhook/claude-executor (sync responses)
    # Requires: Anthropic API credentials configured in n8n
    # Falls back to Gemini via call_app if unavailable
    "CLAUDE": os.getenv("N8N_CLAUDE_WEBHOOK_URL", "https://humanresource.app.n8n.cloud/webhook/claude-executor"),

    # Operations & Tech — routed through gemini-flash (elite-council is INACTIVE)
    "COO": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",
    "CTO": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",
    "LEGAL": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",

    # Legacy/Generic — routed through gemini-flash
    "PRODUCT": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",
    "SALES": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",
    "ANALYST": "https://humanresource.app.n8n.cloud/webhook/gemini-flash"
}

# Execution Engine Config — which model handles Triad Execute steps
# Set to "CLAUDE" for reliable JSON tool calls, "GEMINI" for legacy behavior
EXECUTION_ENGINE = os.getenv("EXECUTION_ENGINE", "CLAUDE")
CLAUDE_EXECUTOR_URL = AGENT_REGISTRY.get("CLAUDE", WEBHOOK_URL)

# Sentry Persistence
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

def _inject_triad_vision(prompt: str) -> str:
    """
    If the prompt contains a Triad Execute signal, prepend a live
    file-structure and MASTER_INDEX snapshot so agents know exactly
    what files exist before making decisions.
    """
    if not VISION_SKILL_AVAILABLE:
        return prompt
    triad_signals = ["SOP Triad Protocol", "Triad Execute", "Execute per SOP"]
    if not any(sig in prompt for sig in triad_signals):
        return prompt
    try:
        factory_dir = os.path.abspath(os.path.join(BASE_DIR, ".."))
        vision_block = get_triad_context(factory_dir)
        return f"{vision_block}\n\n{prompt}"
    except Exception as e:
        print(f"--- VISION CONTEXT ERROR: {e} ---", flush=True)
        return prompt


def _wipe_stale_cache():
    """
    Checks if the sentry cache is older than 24 hours.
    If stale, wipes it and stamps MASTER_INDEX.md with FRESH_BOOT.
    Returns True if a wipe was performed.
    """
    import time
    from datetime import datetime

    if not os.path.exists(CACHE_FILE):
        return False

    file_age_seconds = time.time() - os.path.getmtime(CACHE_FILE)
    if file_age_seconds > 86400:  # 24 hours
        print("--- DIAGNOSTIC: Sentry cache is older than 24h. Auto-wiping for fresh boot. ---", flush=True)
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump([], f)
        except Exception as e:
            print(f"--- CACHE WIPE ERROR: {e} ---", flush=True)

        # Stamp MASTER_INDEX.md
        master_index_path = os.path.join(BASE_DIR, "..", "MASTER_INDEX.md")
        master_index_path = os.path.abspath(master_index_path)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fresh_boot_entry = f"\n## FRESH_BOOT\n- **Timestamp:** {timestamp}\n- **Reason:** Sentry cache was older than 24 hours. Auto-wiped by System Diagnostic.\n- **Status:** FRESH_BOOT\n"
        try:
            if os.path.exists(master_index_path):
                with open(master_index_path, "a", encoding="utf-8") as f:
                    f.write(fresh_boot_entry)
            else:
                with open(master_index_path, "w", encoding="utf-8") as f:
                    f.write(f"# MASTER INDEX\n{fresh_boot_entry}")
            print(f"--- DIAGNOSTIC: MASTER_INDEX.md updated with FRESH_BOOT status. ---", flush=True)
        except Exception as e:
            print(f"--- MASTER_INDEX UPDATE ERROR: {e} ---", flush=True)

        return True

    return False

def check_system_health():
    """
    Pings all agents in the registry to verify they are online.
    First performs a stale-cache check — auto-wipes if older than 24 hours.
    Returns a dict: {"CFO": True, "CMO": False, ...}
    """
    print("--- DIAGNOSTIC: Initiating Neural Network Scan ---", flush=True)

    # Step 0: Stale Cache Guard
    wiped = _wipe_stale_cache()
    if wiped:
        print("--- DIAGNOSTIC: Cache wiped. System is starting fresh. ---", flush=True)

    status_report = {}

    # Only check dedicated agents to save time, skip fallbacks
    targets = {k: v for k, v in AGENT_REGISTRY.items() if "role=" not in v}

    for role, url in targets.items():
        try:
            # Fast timeout ping
            resp = requests.post(url, json={"prompt": "PING"}, timeout=8)
            if resp.status_code == 200:
                status_report[role] = True
            else:
                status_report[role] = False
        except:
            status_report[role] = False

    return status_report

def _sanitize_response(response) -> dict:
    """
    Robust JSON parser for n8n responses.
    Handles: raw JSON, JSON in markdown fences, plain text,
    empty bodies, and mixed-content blobs.
    Always returns a dict with at least {"output": ...}.
    """
    import re as _re

    raw = response.text.strip() if response.text else ""

    # DEBUG: Always log raw response so we can diagnose n8n payloads
    print(f"--- BRIDGE RAW RESPONSE ({len(raw)} chars): {raw[:300]} ---", flush=True)

    # Handle empty body gracefully
    if not raw:
        print("--- BRIDGE: Empty response body. N8N may be async. ---", flush=True)
        return {"output": "(N8N processed the request but returned no response body. Check Respond to Webhook node configuration.)"}

    # 1. Try native JSON parse first (fastest path)
    try:
        data = response.json()
        if data:
            return data
    except Exception:
        pass

    # 2. Extract JSON from markdown code fences ```json ... ```
    fence_match = _re.search(r'```(?:json)?\s*([\s\S]+?)```', raw)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except Exception:
            pass

    # 3. Find first {...} block in the raw text
    brace_match = _re.search(r'(\{[\s\S]+\})', raw)
    if brace_match:
        try:
            return json.loads(brace_match.group(1))
        except Exception:
            pass

    # 4. Graceful fallback — treat whole response as plain text output
    print(f"--- BRIDGE: Non-JSON response wrapped as plain text. ---", flush=True)
    return {"output": raw}


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

        # Triad Vision Injection — attach file & index context
        payload["prompt"] = _inject_triad_vision(payload["prompt"])

        # CRASH SHIELD: Retry Logic
        import time
        max_retries = 3
        result = None
        
        for attempt in range(max_retries):
            try:
                print(f"--- CEO: Sending prompt to Elite Council (Attempt {attempt+1}/{max_retries}) [Context: {project_name}] ---", flush=True)
                span.add_event("Calling N8N", {"attempt": attempt + 1, "url": WEBHOOK_URL})
                
                # INJECT MEMORY CONTEXT
                # N8N WindowBufferMemory usually looks for 'sessionId'
                payload["sessionId"] = project_name 
                
                # Send prompt under all common LangChain field aliases
                # n8n AI Chain nodes read from chatInput, input, or prompt
                prompt_text = payload.get("prompt", "")
                n8n_payload = {
                    "prompt": prompt_text,
                    "chatInput": prompt_text,
                    "input": prompt_text,
                    "sessionId": payload.get("sessionId", project_name),
                    "project_name": project_name,
                }
                response = requests.post(WEBHOOK_URL, json=n8n_payload, timeout=300)
                
                if response.status_code in [500, 502, 503, 504, 404]:
                     raise Exception(f"N8N Server Error: {response.status_code}")
                     
                response.raise_for_status()
                
                try:
                    result = _sanitize_response(response)
                    if not result:
                        raise Exception("Empty Response")
                    span.add_event("N8N Response Received")
                    break  # Success
                except Exception as parse_err:
                    raise Exception(f"Parse Error: {parse_err}")

            except Exception as e:
                print(f"N8N Error: {str(e)}. Retrying in 3s...", flush=True)
                span.record_exception(e)
                if attempt < max_retries - 1:
                    time.sleep(3)
                else:
                    return f"Graceful Failure: The CEO is currently unreachable after 3 attempts ({str(e)}). Please check your N8N Workflow or Internet Connection."

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

        # 4. Tool Loop (handles both n8n responses and Claude _force_tool calls)
        # Check for _force_tool first (from Claude executor)
        if isinstance(payload.get("_force_tool"), dict):
            result = payload["_force_tool"]

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

            if tool_name == "list_files":
                if VISION_SKILL_AVAILABLE:
                    target_dir = query if query else os.path.abspath(os.path.join(BASE_DIR, ".."))
                    observation = _list_files_skill(target_dir)
                else:
                    observation = "Vision skill not available. Ensure list_files.py is in the skills directory."
            elif tool_name == "market_search":
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
            
            elif tool_name == "write_file":
                print(f"--- BRIDGE: Writing File... ---", flush=True)
                try:
                    if isinstance(query, str):
                        try: params = json.loads(query)
                        except: params = {"path": "output.txt", "content": query}
                    else:
                        params = query

                    file_path = params.get("path", "output.txt")
                    content = params.get("content", "")

                    # Security: resolve relative to project directory
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    deliverables_dir = os.path.join(base_dir, ".Gemini_state", "deliverables")
                    os.makedirs(deliverables_dir, exist_ok=True)

                    # If path is relative, put it in deliverables
                    if not os.path.isabs(file_path):
                        full_path = os.path.join(deliverables_dir, file_path)
                    else:
                        full_path = file_path

                    # Create parent dirs
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)

                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    observation = f"File written successfully: {full_path}"
                    print(f"  >> File created: {full_path}", flush=True)
                except Exception as e:
                    observation = f"Write File Error: {str(e)}"

            elif tool_name == "modify_code":
                print(f"--- BRIDGE: Modifying Code... ---", flush=True)
                try:
                    if isinstance(query, str):
                        try: params = json.loads(query)
                        except: params = {}
                    else:
                        params = query

                    file_path = params.get("path", "")
                    search_text = params.get("search", "")
                    replace_text = params.get("replace", "")

                    if not file_path or not search_text:
                        observation = "Modify Code Error: 'path' and 'search' are required."
                    else:
                        # Resolve path
                        base_dir = os.path.dirname(os.path.abspath(__file__))
                        if not os.path.isabs(file_path):
                            full_path = os.path.join(base_dir, file_path)
                        else:
                            full_path = file_path

                        if not os.path.exists(full_path):
                            observation = f"Modify Code Error: File not found: {full_path}"
                        else:
                            with open(full_path, "r", encoding="utf-8") as f:
                                content = f.read()

                            if search_text not in content:
                                observation = f"Modify Code Error: Search text not found in {full_path}"
                            else:
                                new_content = content.replace(search_text, replace_text, 1)
                                with open(full_path, "w", encoding="utf-8") as f:
                                    f.write(new_content)
                                observation = f"Code modified successfully in {full_path}"
                                print(f"  >> Code modified: {full_path}", flush=True)
                except Exception as e:
                    observation = f"Modify Code Error: {str(e)}"

            else:
                 print(f"--- BRIDGE WARNING: UNKNOWN TOOL '{tool_name}' REQUESTED ---", flush=True)
                 observation = f"System Error: Tool '{tool_name}' is not available. Available tools: write_file, modify_code, produce_document, financial_model, google_workspace, market_search, list_files."

            print(f"--- Tool Success. Returning to Council. ---", flush=True)
            return call_app({"prompt": f"OBSERVATION: {observation}", "context": "TOOL_RESULT", "project_name": project_name})

        # Extract the final text output — check all common n8n response fields
        output = (
            result.get("output")         # standard
            or result.get("text")        # legacy agent format
            or result.get("message")     # {status, message} format
            or result.get("chatOutput")  # LangChain chain output
            or result.get("response")    # generic
            or result.get("answer")      # QA chains
            or (result if isinstance(result, str) else None)
            or str(result)
        )

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


# ═══════════════════════════════════════════════════════
#   TRIAD ACTION PLAN — Bridge Integration
# ═══════════════════════════════════════════════════════

def call_for_plan(user_task: str) -> str:
    """Send a task to Gemini and get back a structured action plan."""
    plan_prompt = (
        f"SYSTEM OVERRIDE: TRIAD PLANNING MODE.\n"
        f"Create a detailed Action Plan for the following task.\n"
        f"TASK: {user_task}\n\n"
        f"FORMAT: Return a JSON object with:\n"
        f"- 'task': the task name\n"
        f"- 'steps': array of step objects, each with:\n"
        f"  - 'agent': who executes (Gemini/Antigravity/Claude/CFO/CMO/etc.)\n"
        f"  - 'description': what to do (clear, actionable)\n"
        f"  - 'tools': list of tools needed\n"
        f"  - 'code': any reference code (optional)\n\n"
        f"RULES:\n"
        f"- Make each step self-contained and actionable\n"
        f"- Start every description with a VERB\n"
        f"- Assign the best-fit agent for each step\n"
        f"- Return ONLY the JSON, wrapped in ```json``` code block\n"
    )
    return call_app({"prompt": plan_prompt, "context": "TRIAD_PLAN", "clean_slate": True})


def revise_plan(plan_context_json: str, user_feedback: str) -> str:
    """Send a plan + user feedback to Gemini for revision."""
    from action_plan import build_revision_prompt, ActionPlan
    # Build the revision prompt
    prompt = (
        f"SYSTEM OVERRIDE: PLAN REVISION MODE.\n"
        f"You previously created this Action Plan:\n\n"
        f"{plan_context_json}\n\n"
        f"The USER has provided the following feedback:\n"
        f"\"{user_feedback}\"\n\n"
        f"INSTRUCTIONS:\n"
        f"1. Review the feedback and update the plan accordingly.\n"
        f"2. If the feedback improves the plan, incorporate it.\n"
        f"3. If you DISAGREE with any feedback, explain WHY in a 'triad_notes' "
        f"field for that step, and suggest a better approach.\n"
        f"4. Return the REVISED plan in the SAME JSON format with a 'steps' array.\n"
        f"5. Each step must have: agent, description, tools (list), and optionally triad_notes.\n"
        f"6. Return ONLY the JSON, wrapped in ```json``` code block.\n"
    )
    return call_app({"prompt": prompt, "context": "TRIAD_REVISION", "clean_slate": True})


def execute_plan_step(step_agent: str, step_prompt: str) -> str:
    """
    Route a single plan step through the full execution bridge.
    Prefers Claude for execution (reliable JSON tool calls).
    Falls back to Gemini if Claude is unavailable.
    """
    agent_upper = step_agent.upper().strip()

    # Inject tool awareness into the step prompt
    tool_awareness = """
[EXECUTION TOOLS AVAILABLE]
You MUST use these tools to produce real output. Do NOT just describe what you would do.

1. WRITE A FILE: Return JSON {"action": "use_tool", "tool": "write_file", "query": {"path": "relative/path/file.ext", "content": "file content here"}}
2. MODIFY CODE: Return JSON {"action": "use_tool", "tool": "modify_code", "query": {"path": "relative/path/file.py", "search": "old code", "replace": "new code"}}
3. CREATE DOCUMENT (pptx/docx/csv): Return JSON {"action": "use_tool", "tool": "produce_document", "query": {"file_type": "pptx", "file_name": "name.pptx", "content": "content here"}}
4. FINANCIAL MODEL: Return JSON {"action": "use_tool", "tool": "financial_model", "query": {..assumptions..}}
5. GOOGLE DRIVE: Return JSON {"action": "use_tool", "tool": "google_workspace", "query": {"action": "create", "file_type": "doc", "file_name": "name", "content": "..."}}
6. DELEGATE: Return JSON {"action": "delegate_task", "recipient": "CFO", "content": "task description"}

CRITICAL: You MUST return one of the JSON actions above to produce real output. Plain text descriptions are NOT acceptable.
"""
    enhanced_prompt = f"{tool_awareness}\n\n{step_prompt}"

    # Try Claude DIRECTLY via Anthropic API (no n8n middleman — faster and more reliable)
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if EXECUTION_ENGINE == "CLAUDE" and anthropic_key:
        try:
            print(f"--- TRIAD: Routing Step to Claude Direct API ({agent_upper})... ---", flush=True)

            claude_system = (
                "You are Claude, an execution agent in the Antigravity Triad Protocol. "
                "Your role is to EXECUTE tasks by returning JSON tool calls. "
                "When you need to create a file, modify code, or produce a document, "
                "you MUST return ONLY the JSON action — no explanation, no markdown fencing, just raw JSON."
            )

            r = requests.post("https://api.anthropic.com/v1/messages", headers={
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }, json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4096,
                "temperature": 0.3,
                "system": claude_system,
                "messages": [{"role": "user", "content": enhanced_prompt}]
            }, timeout=120)

            if r.status_code == 200:
                data = r.json()
                # Extract text from Claude's response
                response_text = ""
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        response_text += block.get("text", "")

                print(f"--- TRIAD: Claude responded ({len(response_text)} chars) ---", flush=True)

                # Check if Claude returned a tool call JSON
                try:
                    # Strip markdown code fencing if present
                    clean = response_text.strip()
                    if clean.startswith("```"):
                        clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()

                    parsed = json.loads(clean)
                    if isinstance(parsed, dict) and parsed.get("action") in ("use_tool", "delegate_task"):
                        print(f"--- TRIAD: Claude returned tool call: {parsed.get('tool', parsed.get('action'))} ---", flush=True)
                        return call_app({
                            "prompt": f"TOOL_CALL_FROM_CLAUDE: {clean}",
                            "suite_command": True,
                            "context": f"TRIAD_STEP_{agent_upper}",
                            "_force_tool": parsed
                        })
                except (json.JSONDecodeError, TypeError):
                    pass

                # If not a tool call, return as text
                return response_text
            else:
                print(f"--- TRIAD: Claude API error {r.status_code}: {r.text[:200]} ---", flush=True)
        except Exception as e:
            print(f"--- TRIAD: Claude unavailable ({e}), falling back to Gemini ---", flush=True)

    # Fallback: route through call_app (Gemini) with tool awareness
    return call_app({
        "prompt": enhanced_prompt,
        "suite_command": True,
        "context": f"TRIAD_STEP_{agent_upper}"
    })


if __name__ == "__main__":
    print(call_app({"prompt": "Hello"}))

