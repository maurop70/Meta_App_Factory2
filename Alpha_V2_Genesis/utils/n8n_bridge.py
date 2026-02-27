import os
import sys
import json
import requests
from dotenv import load_dotenv

class N8NBridge:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
    
    def execute_workflow(self, payload):
        """
        Executes an n8n workflow via webhook.
        """
        try:
            # We use a higher timeout (30s) because N8N might be doing heavy AI processing
            from requests.exceptions import Timeout
            response = requests.post(self.webhook_url, json=payload, timeout=45) # Increased timeout to 45s
            if response.status_code == 200:
                try:
                    return response.json()
                except:
                    # If it's not JSON, return as text in a dict
                    return {"commentary": response.text}
            else:
                print(f"N8NBridge Error: Status {response.status_code}, Body: {response.text[:200]}")
            return None
        except Exception as e:
            print(f"N8NBridge Connection Error: {e}")
            return None

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
    # Dummy tracer for when opentelemetry is not installed
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
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://humanresource.app.n8n.cloud/webhook/elite-council")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.getenv("PROJECTS_DIR", os.path.join(BASE_DIR, "Projects"))
SKILLS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "skills")) # Updated for Alpha_V2_Genesis structure
if SKILLS_DIR not in sys.path: sys.path.append(SKILLS_DIR)

# [CRITICAL] Pre-load Skills to ensure registration
# Guard: these skills only exist in the Adv_Autonomous_Agent context, not Alpha_V2_Genesis
try:
    from financial_planner import FinancialPlanner
    from file_factory import FileFactory
    from google_suite import GoogleSuiteManager
except ImportError:
    FinancialPlanner = None
    FileFactory = None
    GoogleSuiteManager = None

# [ROUTER CONFIG] Specialist Agent Registry
# Verified Unique URLs (Path-Based for Stability)
AGENT_REGISTRY = {
    # The Core Team
    "CFO": "https://humanresource.app.n8n.cloud/webhook/cfo-v2", 
    "CMO": "https://humanresource.app.n8n.cloud/webhook/cmo-v2",
    "HR": "https://humanresource.app.n8n.cloud/webhook/hr",

    # The New Special Forces
    "CRITIC": "https://humanresource.app.n8n.cloud/webhook/critic-v2",
    "PITCH": "https://humanresource.app.n8n.cloud/webhook/pitch-v2",
    "ATOMIZER": "https://humanresource.app.n8n.cloud/webhook/atomizer-v2", 
    "ARCHITECT": "https://humanresource.app.n8n.cloud/webhook/architect-v2", 
    "PRESENTATION_ARCHITECT": "https://humanresource.app.n8n.cloud/webhook/architect-v2", 

    # Operations & Tech (Fallbacks until dedicated workflows are deployed)
    "COO": "https://humanresource.app.n8n.cloud/webhook/elite-council?role=coo",
    "CTO": "https://humanresource.app.n8n.cloud/webhook/elite-council?role=cto",
    "LEGAL": "https://humanresource.app.n8n.cloud/webhook/elite-council?role=legal",
    
    # Legacy/Generic
    "PRODUCT": "https://humanresource.app.n8n.cloud/webhook/elite-council?role=product",
    "SALES": "https://humanresource.app.n8n.cloud/webhook/elite-council?role=sales",
    "ANALYST": "https://humanresource.app.n8n.cloud/webhook/elite-council?role=analyst"
}

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
                
                response = requests.post(WEBHOOK_URL, json=payload, timeout=300)
                
                if response.status_code in [500, 502, 503, 504, 404]:
                     raise Exception(f"N8N Server Error: {response.status_code}")
                     
                response.raise_for_status()
                
                try: 
                    result = response.json()
                    if not result: raise Exception("Empty JSON Response")
                    span.add_event("N8N Response Received")
                    break # Success
                except ValueError:
                    raise Exception(f"Invalid JSON Response: {response.text[:50]}...")

            except Exception as e:
                print(f"⚠️ N8N Error: {str(e)}. Retrying in 3s...", flush=True)
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
