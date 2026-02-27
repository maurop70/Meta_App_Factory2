import os
import json
import requests
import sys

# Force UTF-8 output on Windows (cp1252 can't handle emojis, crashes server)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import time

# --- DEPENDENCY CHECK ---
try:
    from flask import Flask, request, jsonify, Response
    from flask_cors import CORS
    from pyngrok import ngrok
    from dotenv import load_dotenv
except ImportError as e:
    print(f"\n❌ CRITICAL ERROR: Missing Dependency.\nError: {e}\n\nPlease run: pip install flask flask-cors pyngrok python-dotenv\n")
    print("Press Enter to exit...")
    input()
    sys.exit(1)

# Add project root for skills import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from vault_client import get_secret
try:
    from skills.loki.loki import Loki
except ImportError as e:
    Loki = None
    print(f"⚠️ WARNING: Loki Skill not found. Error: {e}")
except Exception as e:
    Loki = None
    print(f"⚠️ WARNING: Loki initialization failed. Error: {e}")

# SSE Streaming Bridge
try:
    from stream_bridge import stream_chat, clear_stream_history
    STREAMING_AVAILABLE = True
except ImportError as e:
    STREAMING_AVAILABLE = False
    print(f"⚠️ WARNING: Stream bridge not available: {e}")

# Supabase Long-Term Memory
try:
    from memory_engine import save_message_async, get_history, clear_history as clear_supa_history
    MEMORY_AVAILABLE = True
except ImportError as e:
    MEMORY_AVAILABLE = False
    print(f"⚠️ WARNING: Memory engine not available: {e}")

# 1. BRAIN INITIALIZATION
load_dotenv()

app = Flask(__name__)
# ENABLE CORS FOR ALL ROUTES AND ORIGINS
CORS(app, resources={r"/*": {"origins": "*"}})

# --- CONFIGURATION FROM .ENV ---
PORT = 5005 
NGROK_TOKEN = get_secret("NGROK_AUTH_TOKEN")
N8N_API_KEY = get_secret("N8N_API_KEY")
N8N_WORKFLOW_ID = "VkE0dmwynRPMIyjdmiONL"
N8N_NODE_NAME = "Push_to_Alpha_UI"

# Pathing for local data
script_dir = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_PATH = os.path.join(script_dir, 'Alpha_Data', 'portfolio.json')
MEMO_PATH = os.path.join(script_dir, 'market_memo.md')

# Initialize Loki Pattern
loki_engine = Loki(portfolio_path=PORTFOLIO_PATH) if Loki else None

def self_heal_n8n(new_url):
    """
    Antigravity Logic: Reprograms the n8n node with the new tunnel URL.
    Filters 'settings' to only include API-supported keys to avoid validation errors.
    """
    url = f"https://humanresource.app.n8n.cloud/api/v1/workflows/{N8N_WORKFLOW_ID}"
    headers = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}
    SUPPORTED_SETTINGS = {
        "saveExecutionProgress", "saveManualExecutions", "saveDataErrorExecution",
        "saveDataSuccessExecution", "executionTimeout", "errorWorkflow",
        "timezone", "executionOrder"
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            workflow = res.json()
            for node in workflow.get('nodes', []):
                if node.get('name') == N8N_NODE_NAME:
                    node['parameters']['url'] = f"{new_url}/api/hot_update"
                    node['parameters']['sendHeaders'] = True
                    node['parameters']['headerParametersUi'] = {
                        "parameter": [{"name": "Content-Type", "value": "application/json"}]
                    }
            raw_settings   = workflow.get("settings", {})
            clean_settings = {k: v for k, v in raw_settings.items() if k in SUPPORTED_SETTINGS}
            payload = {
                "name": workflow.get("name"), "nodes": workflow.get("nodes"),
                "connections": workflow.get("connections"),
                "settings": clean_settings, "staticData": workflow.get("staticData")
            }
            update_res = requests.put(url, headers=headers, json=payload)
            if update_res.status_code == 200:
                print(f"✅ Antigravity: n8n Workflow '{workflow.get('name')}' successfully synced.")
            else:
                print(f"❌ Failed to push update: {update_res.text}")
        else:
            print(f"❌ Failed to reach n8n: {res.status_code}. Verify API Key.")
    except Exception as e:
        print(f"⚠️ Antigravity Critical Error: {e}")


def heal_ledger_cron(new_url):
    """
    Self-Healing for the Alpha Ledger Daily Cron workflow.
    Reads ledger_cron_meta.json and patches the Refresh_Ledger HTTP node
    with the current ngrok URL so the 09:15 daily trigger always reaches us.
    """
    meta_path = os.path.join(script_dir, "Alpha_Data", "ledger_cron_meta.json")
    if not os.path.exists(meta_path):
        print("⚠️ ledger_cron_meta.json not found — skipping Ledger Cron self-heal.")
        return
    try:
        with open(meta_path, "r") as f:
            meta = json.load(f)
    except Exception as e:
        print(f"⚠️ Could not read ledger_cron_meta.json: {e}")
        return

    wf_id       = meta.get("workflow_id")
    target_node = meta.get("target_node", "Refresh_Ledger")
    if not wf_id:
        return

    headers = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}
    url     = f"https://humanresource.app.n8n.cloud/api/v1/workflows/{wf_id}"
    SUPPORTED_SETTINGS = {
        "saveExecutionProgress", "saveManualExecutions", "saveDataErrorExecution",
        "saveDataSuccessExecution", "executionTimeout", "errorWorkflow",
        "timezone", "executionOrder"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            print(f"⚠️ Ledger Cron heal: could not fetch workflow ({res.status_code})")
            return
        workflow = res.json()
        patched  = False
        for node in workflow.get("nodes", []):
            if node.get("name") == target_node:
                node["parameters"]["url"] = f"{new_url}/api/ledger/refresh"
                patched = True
        if not patched:
            print(f"⚠️ Ledger Cron heal: node '{target_node}' not found in workflow.")
            return
        clean_settings = {k: v for k, v in workflow.get("settings", {}).items() if k in SUPPORTED_SETTINGS}
        payload = {
            "name": workflow.get("name"), "nodes": workflow.get("nodes"),
            "connections": workflow.get("connections"),
            "settings": clean_settings, "staticData": workflow.get("staticData"),
        }
        up = requests.put(url, headers=headers, json=payload, timeout=10)
        if up.status_code == 200:
            print(f"✅ Antigravity: Ledger Cron synced → {new_url}/api/ledger/refresh")
        else:
            print(f"❌ Ledger Cron heal failed: {up.text[:200]}")
    except Exception as e:
        print(f"⚠️ Ledger Cron heal error: {e}")

# ── Strategy Ledger Import ──────────────────────────────────────
try:
    sys.path.insert(0, script_dir)
    from strategy_ledger import run_ledger, load_state, LEDGER_MD_PATH
    LEDGER_AVAILABLE = True
except ImportError as e:
    LEDGER_AVAILABLE = False
    print(f"⚠️ Ledger module not available: {e}")

import threading as _threading

@app.route('/api/ledger', methods=['GET'])
def get_ledger():
    """Returns the current strategy ledger state and markdown report."""
    if not LEDGER_AVAILABLE:
        return jsonify({"error": "Strategy Ledger module not available"}), 503
    try:
        state = load_state()
        md_content = ""
        if os.path.exists(LEDGER_MD_PATH):
            with open(LEDGER_MD_PATH, "r", encoding="utf-8") as f:
                md_content = f.read()
        return jsonify({
            "status":    "ok",
            "last_run":  state.get("last_run"),
            "positions": state.get("positions", {}),
            "markdown":  md_content,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ledger/refresh', methods=['POST'])
def refresh_ledger():
    """Triggers a background ledger recalibration run."""
    if not LEDGER_AVAILABLE:
        return jsonify({"error": "Strategy Ledger module not available"}), 503
    try:
        force = request.json.get("force", False) if request.json else False
        _threading.Thread(target=run_ledger, kwargs={"force_full": force}, daemon=True).start()
        return jsonify({"status": "triggered", "force": force})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/journal', methods=['GET'])
def get_journal():
    """Returns the closed trade journal (Priority 5)."""
    journal_path = os.path.join(script_dir, "Alpha_Data", "trade_journal.json")
    try:
        if not os.path.exists(journal_path):
            return jsonify({"status": "ok", "trades": [], "count": 0})
        with open(journal_path, "r", encoding="utf-8") as f:
            trades = json.load(f)
        # Sort newest close date first
        trades.sort(key=lambda t: t.get("close_date", ""), reverse=True)
        return jsonify({"status": "ok", "trades": trades, "count": len(trades)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── SSE Streaming Chat ──────────────────────────────────────────
STREAM_SESSION = "alpha-stream"  # Default session ID for the chat panel

@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """SSE endpoint: streams Gemini responses chunk-by-chunk."""
    if not STREAMING_AVAILABLE:
        return jsonify({"error": "Streaming bridge not available."}), 503
    data = request.get_json(force=True, silent=True) or {}
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "No prompt provided."}), 400
    project = data.get("project_name", "General")
    session = data.get("session_id", STREAM_SESSION)
    dashboard_context = data.get("dashboard_context")  # Live UI metrics

    # Save user message to Supabase (non-blocking)
    if MEMORY_AVAILABLE:
        save_message_async(session, "user", prompt)

    def generate():
        full_response = []
        for event in stream_chat(prompt, project, dashboard_context=dashboard_context):
            if event.get("text"):
                full_response.append(event["text"])
            yield f"data: {json.dumps(event)}\n\n"
        # Save assistant response to Supabase after stream completes
        if MEMORY_AVAILABLE and full_response:
            save_message_async(session, "assistant", "".join(full_response))

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )

@app.route('/api/chat/clear', methods=['POST'])
def chat_clear():
    """Clears the streaming chat history (local + Supabase)."""
    if STREAMING_AVAILABLE:
        clear_stream_history()
    if MEMORY_AVAILABLE:
        data = request.get_json(force=True, silent=True) or {}
        session = data.get("session_id", STREAM_SESSION)
        clear_supa_history(session)
    return jsonify({"status": "ok", "message": "Chat history cleared."})


@app.route('/')
def home():
    return jsonify({"status": "online", "port": PORT, "system": "Alpha V2 Genesis"})

@app.route('/api/analyze', methods=['GET'])
def analyze_market():
    if not loki_engine:
        return jsonify({"error": "Loki Engine not available."}), 500
    try:
        availability = float(request.args.get('availability', 2000))
        decision = loki_engine.run_strategy(availability=availability)
        return jsonify(decision)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/memo', methods=['GET'])
def get_memo():
    try:
        if os.path.exists(MEMO_PATH):
            with open(MEMO_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({"content": content})
        return jsonify({"content": "## No Memo Available.\nRun analysis to generate."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/memo/refresh', methods=['POST'])
def refresh_memo():
    if not loki_engine: return jsonify({"error": "No Loki"}), 500
    try:
        loki_engine.run_strategy()
        return get_memo()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/hot_update', methods=['POST'])
def hot_update():
    """Endpoint for n8n to push FOMC and Macro data into the local JSON database."""
    try:
        data = request.json
        if not data: return jsonify({"status": "error", "message": "No data"}), 400
        
        os.makedirs(os.path.dirname(PORTFOLIO_PATH), exist_ok=True)
        
        # Data Routing Logic: Check for macro/FOMC related keys
        is_macro = False
        
        # Helper to check if a dict looks like a macro update
        def looks_like_macro(d):
            if not isinstance(d, dict): return False
            macro_keys = {'event', 'event_name', 'impact', 'impact_level', 'strategic_note', 'strategic_rationale'}
            return any(k in d for k in macro_keys)

        if isinstance(data, list) and len(data) > 0:
            if looks_like_macro(data[0]):
                is_macro = True
        elif isinstance(data, dict):
            if looks_like_macro(data):
                is_macro = True
        
        if is_macro:
             event_file = os.path.join(script_dir, "Alpha_Data", "upcoming_events.json")
             with open(event_file, "w") as f:
                json.dump(data, f, indent=4)
             print("📥 Received Macro Event Update. updated upcoming_events.json")
        else:
             with open(PORTFOLIO_PATH, 'w') as f:
                json.dump(data, f, indent=4)
             print("📥 Received Position Hot-Fix. updated portfolio.json")

        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def warm_up_system():
    """
    Antigravity Warm-up Sequence:
    Populates local database and builds the first memo BEFORE UI requests it.
    """
    print("\n🔥 Starting Antigravity Warm-up Sequence...")
    
    # 1. Start Background Supervisors
    import subprocess
    try:
        print("🛡️ Launching Infrastructure Supervisor & Volatility Sentry...")
        subprocess.Popen([sys.executable, "infrastructure_supervisor.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        subprocess.Popen([sys.executable, "volatility_sentry.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
    except Exception as e:
        print(f"⚠️ Failed to launch background agents: {e}")

    # 2. Trigger Strategic Analysis
    if loki_engine:
        try:
            print("🧠 Triggering Strategic Analysis (Loki)...")
            # This triggers SentimentSkill, Macro polling, and sets the initial memo
            loki_engine.run_strategy(availability=2000)
            print("✅ Warm-up Complete: portfolio.json and market_memo.md initialized.")
        except Exception as e:
            print(f"⚠️ Warm-up Warning: Loki failed to initialize data ({e})")
    else:
        print("⚠️ Warm-up Skipped: Loki Engine not found.")

if __name__ == '__main__':
    if not NGROK_TOKEN:
        print("❌ CRITICAL: NGROK_AUTH_TOKEN missing from vault/.env")
    else:
        print("Initializing Ngrok Tunnel...")
        try:
            ngrok.set_auth_token(NGROK_TOKEN)
            tunnels = ngrok.get_tunnels()
            for t in tunnels:
                ngrok.disconnect(t.public_url)

            public_url = ngrok.connect(PORT).public_url
            print(f"Tunnel Live: {public_url}")

            # ── Static URL Detection ────────────────────────────
            # Load the previously known URL from connection_info.json
            conn_info_path  = os.path.join(script_dir, "Alpha_Data", "connection_info.json")
            previous_url    = None
            try:
                if os.path.exists(conn_info_path):
                    with open(conn_info_path, "r") as f:
                        ci = json.load(f)
                        previous_url = ci.get("ngrok_url")
            except Exception:
                pass

            url_changed = (previous_url != public_url)

            if url_changed:
                print(f"🔄 URL CHANGED: {previous_url} → {public_url}")
                print("   Reprogramming N8N workflows with new URL...")
                self_heal_n8n(public_url)
                heal_ledger_cron(public_url)
            else:
                print(f"✅ Static URL confirmed: {public_url} (no N8N reprogramming needed)")

            # Always update connection_info.json with current status
            conn_data = {
                "ngrok_url":        public_url,
                "last_updated":     __import__('datetime').datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "system_status":    "STABLE",
                "url_is_static":    not url_changed,
                "macro_sensor":     "ACTIVE",
                "genesis_fallback": "ENABLED"
            }
            os.makedirs(os.path.dirname(conn_info_path), exist_ok=True)
            with open(conn_info_path, "w") as f:
                json.dump(conn_data, f, indent=4)

            # Verify tunnel responds
            try:
                test_resp = requests.get(public_url, timeout=10)
                if test_resp.status_code == 200:
                    print("✅ Tunnel Verification: SUCCESS")
            except Exception:
                print("⚠️ Tunnel verification timed out — continuing anyway")

            # PERFORM WARM-UP
            warm_up_system()

            # Register graceful shutdown hook (deactivates N8N even on force-close)
            try:
                from n8n_lifecycle import register_shutdown_hook
                register_shutdown_hook('alpha')
            except Exception as e:
                print(f"⚠️ Shutdown hook registration failed: {e}")

            # Run Server
            print(f"🤖 Alpha Server listening on Port {PORT}...")
            app.run(host='0.0.0.0', port=PORT, use_reloader=False)

        except Exception as e:
            print(f"❌ Tunnel Initialization Failed: {e}")
            sys.exit(1)
