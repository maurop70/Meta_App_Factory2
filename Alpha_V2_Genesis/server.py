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
import json
import re
import requests
import sys
import base64
from datetime import datetime

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
PORT = 5008 
NGROK_TOKEN = get_secret("NGROK_AUTH_TOKEN")
N8N_API_KEY = get_secret("N8N_API_KEY")
N8N_WORKFLOW_ID = "VkE0dmwynRPMIyjdmiONL"
N8N_NODE_NAME = "Push_to_Alpha_UI"

# Pathing: shared data stays in Google Drive, runtime data goes to local machine
script_dir = os.path.dirname(os.path.abspath(__file__))
RUNTIME_DIR = os.environ.get('ALPHA_RUNTIME_DIR', os.path.join(script_dir, 'Alpha_Data'))
os.makedirs(RUNTIME_DIR, exist_ok=True)
PORTFOLIO_PATH = os.path.join(script_dir, 'Alpha_Data', 'portfolio.json')  # Shared (Google Drive)
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
    meta_path = os.path.join(RUNTIME_DIR, "ledger_cron_meta.json")
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
        trades.sort(key=lambda t: t.get("close_date") or "", reverse=True)
        return jsonify({"status": "ok", "trades": trades, "count": len(trades)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Trade Execution & Uploads (Priority 6) ────────────────────────
EXECUTIONS_DIR = os.path.join(script_dir, "Alpha_Data", "executions")
os.makedirs(EXECUTIONS_DIR, exist_ok=True)

@app.route('/api/executions/upload', methods=['POST'])
def upload_execution():
    """Handles trade execution logs and screenshot uploads."""
    try:
        # Check for image file
        file = request.files.get('screenshot')
        metadata = request.form.get('metadata')
        
        if not metadata:
            return jsonify({"error": "Missing metadata"}), 400
            
        entry = json.loads(metadata)
        entry_id = f"exec_{int(time.time())}"
        entry['id'] = entry_id
        entry['timestamp'] = datetime.now().isoformat()
        
        # Save screenshot if present
        if file:
            filename = f"{entry_id}_{file.filename}"
            filepath = os.path.join(EXECUTIONS_DIR, filename)
            file.save(filepath)
            entry['screenshot_path'] = filepath
            
        # Save metadata to log
        log_path = os.path.join(EXECUTIONS_DIR, "execution_history.json")
        history = []
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        
        history.append(entry)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
            
        # Sync to Portfolio if Action is OPEN or CLOSE
        sync_to_portfolio(entry)
            
        return jsonify({"status": "success", "id": entry_id})
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return jsonify({"error": str(e)}), 500

def sync_to_portfolio(entry):
    """Bridges Execution Log to live Portfolio.json."""
    port_path = os.path.join(script_dir, "Alpha_Data", "portfolio.json")
    try:
        if not os.path.exists(port_path):
            with open(port_path, "w") as f: json.dump({"positions": []}, f)
            
        with open(port_path, "r") as f:
            port = json.load(f)
            
        # Basic parsing of strikes for common SPX Iron Condor format (e.g. 7100/7125/6275/6250)
        strikes = re.findall(r"(\d{4})", entry.get('strikes', ''))
        
        if entry.get('action') == "OPEN":
            new_pos = {
                "id": f"exec_{int(time.time())}",
                "status": "OPEN",
                "strategy": entry.get('strategy', 'IRON_CONDOR'),
                "open_date": datetime.now().strftime("%Y-%m-%d"),
                "expiration_date": entry.get('strategy', '').split('(')[-1].split(')')[0] if '(' in entry.get('strategy', '') else "2026-04-10",
                "credit_received": float(re.findall(r"[\d.]+", entry.get('credit_debit', '0'))[0] or 0),
            }
            # Map strikes if we found 4 (standard IC)
            if len(strikes) == 4:
                new_pos.update({
                    "short_call_strike": int(strikes[0]),
                    "long_call_strike": int(strikes[1]),
                    "short_put_strike": int(strikes[2]),
                    "long_put_strike": int(strikes[3])
                })
            port['positions'].append(new_pos)
            
        elif entry.get('action') == "CLOSE":
            # Simple matching: find by ticker and strategy if possible
            # For now, just mark last matching strategy as CLOSED
            for p in reversed(port['positions']):
                if p.get('status') == 'OPEN' and (entry.get('ticker') in p.get('strategy', '') or entry.get('ticker') == 'SPX'):
                    p['status'] = 'CLOSED'
                    break
        
        with open(port_path, "w") as f:
            json.dump(port, f, indent=4)
        
        # Also sync to Trade Journal
        journal_path = os.path.join(script_dir, "Alpha_Data", "trade_journal.json")
        journal = []
        if os.path.exists(journal_path):
            try:
                with open(journal_path, "r") as f:
                    journal = json.load(f)
            except: pass
        
        journal_entry = {
            "trade_id": entry.get('id', f"exec_{int(time.time())}"),
            "strategy": entry.get('strategy', 'Unknown'),
            "entry_date": datetime.now().strftime("%Y-%m-%d"),
            "close_date": datetime.now().strftime("%Y-%m-%d") if entry.get('action') == 'CLOSE' else None,
            "expiry": entry.get('strategy', '').split('(')[-1].split(')')[0] if '(' in entry.get('strategy', '') else "",
            "credit_received": float(re.findall(r"[\d.]+", entry.get('credit_debit', '0'))[0] or 0),
            "close_mark": 0,
            "realized_pnl": 0,
            "realized_pnl_pct": 0,
            "days_held": 0,
            "entry_rating": "OPEN" if entry.get('action') == 'OPEN' else "CLOSED",
            "entry_score": 0,
            "strikes": {},
            "closes_at": datetime.now().isoformat() if entry.get('action') == 'CLOSE' else None,
        }
        
        if len(strikes) == 4:
            journal_entry["strikes"] = {
                "short_call": int(strikes[0]),
                "long_call": int(strikes[1]),
                "short_put": int(strikes[2]),
                "long_put": int(strikes[3])
            }
        
        journal.append(journal_entry)
        with open(journal_path, "w") as f:
            json.dump(journal, f, indent=2, default=str)
            
        # Trigger Ledger Refresh to update Risk Radar
        if LEDGER_AVAILABLE:
            _threading.Thread(target=run_ledger, kwargs={"force_full": True}, daemon=True).start()
            print(f"✅ Sync complete: Portfolio + Journal updated & Ledger refresh triggered for {entry.get('id')}")
        
    except Exception as e:
        print(f"⚠️ Sync to Portfolio failed: {e}")


@app.route('/api/executions', methods=['GET'])
def get_executions():
    """Returns the history of recorded trade executions."""
    log_path = os.path.join(EXECUTIONS_DIR, "execution_history.json")
    try:
        if not os.path.exists(log_path):
            return jsonify({"status": "ok", "executions": []})
        with open(log_path, "r", encoding="utf-8") as f:
            history = json.load(f)
        # Newest first
        history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return jsonify({"status": "ok", "executions": history})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/executions/<execution_id>', methods=['DELETE'])
def delete_execution(execution_id):
    """Deletes a specific trade execution from the log."""
    log_path = os.path.join(EXECUTIONS_DIR, "execution_history.json")
    try:
        if not os.path.exists(log_path):
            return jsonify({"error": "No history found"}), 404
            
        with open(log_path, "r", encoding="utf-8") as f:
            history = json.load(f)
            
        new_history = [ex for ex in history if ex.get('id') != execution_id]
        
        if len(new_history) == len(history):
            return jsonify({"error": "Execution not found"}), 404
            
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(new_history, f, indent=4)
            
        return jsonify({"status": "success", "message": "Execution deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/executions/images/<path:filename>')
def get_execution_image(filename):
    """Serves uploaded execution screenshots."""
    from flask import send_from_directory
    return send_from_directory(EXECUTIONS_DIR, filename)

@app.route('/api/executions/ocr', methods=['POST'])
def ocr_execution():
    """Uses Gemini 2.0 Flash Vision to extract trade details from a screenshot."""
    try:
        file = request.files.get('screenshot')
        if not file:
            return jsonify({"error": "No image provided"}), 400
            
        # Read image data
        image_data = file.read()
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        mime_type = file.content_type or 'image/png'
        
        # Prepare Gemini Vision Request
        api_key = get_secret("GEMINI_API_KEY")
        if not api_key:
            return jsonify({"error": "Gemini API key missing"}), 500
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        
        prompt = """
        Extract ALL trade execution details from this screenshot. 
        Detect if there are multiple orders or fills listed.
        Return ONLY a valid JSON object containing an array of objects under the key 'trades'.
        
        Example Output Format:
        {
          "trades": [
            {
              "ticker": "SPX",
              "action": "OPEN",
              "strategy": "Iron Condor (24 APR 26)",
              "strikes": "7100/7125/6275/6250",
              "credit_debit": "+10.00"
            },
            {
              "ticker": "SPX",
              "action": "CLOSE",
              "strategy": "Iron Condor (10 APR 26)",
              "strikes": "7150/7175/6425/6400",
              "credit_debit": "-7.30"
            }
          ]
        }
        Return ONLY the raw JSON string. No markdown, no prose.
        """
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_b64
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "topP": 1,
                "maxOutputTokens": 4096
            }
        }
        
        _v3_status = healed_post(url, payload)

        
        res = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
        res_data = res.json()
        
        if res.status_code != 200:
            return jsonify({"error": f"Gemini error: {res_data.get('error', {}).get('message', 'Unknown error')}"}), 500
            
        # Parse Gemini JSON response
        try:
            # Find the text part (skip any thought parts from thinking models)
            text_response = ""
            for part in res_data['candidates'][0]['content']['parts']:
                if 'text' in part and not part.get('thought'):
                    text_response = part['text']
            
            if not text_response:
                text_response = res_data['candidates'][0]['content']['parts'][0]['text']
            
            # Remove potential markdown formatting
            clean_json = text_response.replace('```json', '').replace('```', '').strip()
            raw_data = json.loads(clean_json)
            
            # Normalize the response into our expected format
            trades = []
            items = raw_data if isinstance(raw_data, list) else raw_data.get('trades', [raw_data])
            
            for item in items:
                # Map Gemini's complex response to our flat format
                trade = {
                    "ticker": item.get("ticker", item.get("symbol", "SPX")),
                    "action": "OPEN" if "open" in str(item.get("action", item.get("side", ""))).lower() or "sell to open" in str(item).lower() else "CLOSE",
                    "strategy": item.get("strategy", item.get("spread", "Unknown")),
                    "strikes": item.get("strikes", ""),
                    "credit_debit": item.get("credit_debit", ""),
                }
                
                # Handle nested legs format from Gemini 2.5
                legs = item.get("legs", [])
                if legs and not trade["strikes"]:
                    strike_parts = []
                    for leg in legs:
                        s = leg.get("strike", leg.get("strike_price", ""))
                        strike_parts.append(str(s))
                    trade["strikes"] = " / ".join(strike_parts)
                
                # Handle nested price format
                net_price = item.get("net_price", {})
                if isinstance(net_price, dict) and not trade["credit_debit"]:
                    val = net_price.get("value", 0)
                    ptype = net_price.get("type", "").upper()
                    trade["credit_debit"] = f"+{val}" if ptype == "CREDIT" else f"-{val}"
                elif not trade["credit_debit"]:
                    trade["credit_debit"] = str(item.get("price", item.get("net_credit", item.get("net_debit", "0"))))
                
                # Build strategy name from spread type + expiration
                if trade["strategy"] in ("Unknown", "") and item.get("spread"):
                    exp = item.get("expiration", item.get("exp_date", ""))
                    trade["strategy"] = f"{item['spread']} ({exp})" if exp else item['spread']
                
                # Detect action from leg sides
                if legs:
                    actions = [l.get("side", "").upper() for l in legs]
                    if all("OPEN" in a or "SELL" in a for a in actions):
                        trade["action"] = "OPEN"
                    elif all("CLOSE" in a or "BUY" in a for a in actions):
                        trade["action"] = "CLOSE"
                
                trades.append(trade)
            
            print(f"✅ OCR extracted {len(trades)} trade(s): {json.dumps(trades, indent=2)}")
            return jsonify({"status": "success", "data": {"trades": trades}})
                
        except Exception as e:
            print(f"❌ OCR Parsing Failed: {e}\nRaw Response: {text_response}")
            return jsonify({"error": f"Failed to parse trade details: {str(e)}"}), 500

            
    except Exception as e:
        print(f"❌ OCR Endpoint Failed: {e}")
        return jsonify({"error": str(e)}), 500


# ── Fragility Index Engine ──────────────────────────────────────
try:
    from fragility_engine import compute_fragility
    FRAGILITY_AVAILABLE = True
except ImportError as e:
    FRAGILITY_AVAILABLE = False
    print(f"⚠️ Fragility engine not available: {e}")

@app.route('/api/fragility', methods=['GET'])
def get_fragility():
    """Returns the Fragility Index, narrative intelligence, and trade impact analysis."""
    if not FRAGILITY_AVAILABLE:
        return jsonify({"error": "Fragility engine not available"}), 503
    try:
        result = compute_fragility()

        # ── Trade Impact Analysis ──────────────────────────────────
        # Cross-reference fragility with active ledger positions
        trade_impact = {
            "has_positions": False,
            "overall_risk": "green",
            "overall_assessment": "",
            "position_impacts": [],
            "warnings": [],
        }

        fidx = result.get("fragility_index", 0)

        if LEDGER_AVAILABLE:
            try:
                state = load_state()
                positions = state.get("positions", {})
                active = {k: v for k, v in positions.items() if v.get("status") == "OPEN"}

                if active:
                    trade_impact["has_positions"] = True

                    for ticker, pos in active.items():
                        # All Iron Condor / credit spread positions are inherently
                        # short-volatility = "Long Beta" exposure
                        p_risk = "green"
                        p_recommendation = ""

                        if fidx >= 80:
                            p_risk = "red"
                            p_recommendation = (
                                f"CRITICAL: Fragility at {fidx}/100 while holding short-vol on {ticker}. "
                                "Immediately tighten stops to 2x credit received. "
                                "Consider closing or hedging with VIX calls."
                            )
                        elif fidx >= 70:
                            p_risk = "red"
                            p_recommendation = (
                                f"HIGH RISK: Fragility at {fidx}/100 with active {ticker} position. "
                                "Consider tightening stops or adding protective puts. "
                                "Avoid rolling into new short-vol exposure."
                            )
                        elif fidx >= 55:
                            p_risk = "yellow"
                            p_recommendation = (
                                f"ELEVATED: Monitor {ticker} closely. "
                                "Reduce position sizing on any new entries. "
                                "Keep stops at 1.5x credit."
                            )
                        else:
                            p_risk = "green"
                            p_recommendation = (
                                f"NORMAL: {ticker} position is within a favorable environment. "
                                "Standard trade management applies."
                            )

                        trade_impact["position_impacts"].append({
                            "ticker": ticker,
                            "strikes": {
                                "short_put": pos.get("short_put_strike"),
                                "short_call": pos.get("short_call_strike"),
                                "long_put": pos.get("long_put_strike"),
                                "long_call": pos.get("long_call_strike"),
                            },
                            "risk_level": p_risk,
                            "recommendation": p_recommendation,
                        })

                    # Overall assessment
                    if fidx >= 80:
                        trade_impact["overall_risk"] = "red"
                        trade_impact["overall_assessment"] = (
                            "🛑 CRITICAL FRAGILITY while holding short-volatility positions. "
                            "Your Iron Condor/credit spread exposure is directly threatened by "
                            "systemic stress. Defensive action recommended immediately."
                        )
                        trade_impact["warnings"].append(
                            "High Fragility detected while holding Long Beta positions. "
                            "Consider tightening stops or hedging with Volatility calls."
                        )
                    elif fidx >= 70:
                        trade_impact["overall_risk"] = "red"
                        trade_impact["overall_assessment"] = (
                            "⚠️ HIGH FRAGILITY while holding short-vol exposure. "
                            "Market stress levels suggest reducing risk. "
                            "Review stop-loss levels and avoid new entries."
                        )
                        trade_impact["warnings"].append(
                            "High Fragility detected while holding Long Beta positions. "
                            "Consider tightening stops or hedging with Volatility calls."
                        )
                    elif fidx >= 55:
                        trade_impact["overall_risk"] = "yellow"
                        trade_impact["overall_assessment"] = (
                            "⚡ ELEVATED FRAGILITY with active positions. "
                            "Conditions are manageable but deteriorating. "
                            "Monitor closely and reduce position sizing on new entries."
                        )
                    else:
                        trade_impact["overall_risk"] = "green"
                        trade_impact["overall_assessment"] = (
                            "✅ Environment is favorable for current positions. "
                            "Fragility levels are low and systemic risk is contained."
                        )
                else:
                    trade_impact["overall_assessment"] = (
                        "No active positions in the Strategy Ledger. "
                        "Monitor fragility levels to time new entries optimally."
                    )
                    if fidx < 40:
                        trade_impact["overall_assessment"] += (
                            " Current low-fragility environment is favorable for "
                            "premium-selling entries."
                        )
            except Exception as e:
                trade_impact["overall_assessment"] = f"Ledger analysis unavailable: {e}"
        else:
            trade_impact["overall_assessment"] = (
                "Strategy Ledger not available — trade impact analysis disabled."
            )

        result["trade_impact"] = trade_impact
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Performance Audit Telemetry ─────────────────────────────────
try:
    from performance_audit import load_latest_report as load_perf_report, run_audit
    PERF_AUDIT_AVAILABLE = True
except ImportError:
    PERF_AUDIT_AVAILABLE = False

@app.route('/api/telemetry/perf', methods=['GET'])
def get_perf_telemetry():
    """Returns the latest performance audit report."""
    if not PERF_AUDIT_AVAILABLE:
        return jsonify({"error": "Performance audit module not available"}), 503
    try:
        report = load_perf_report()
        if not report:
            return jsonify({"status": "no_data", "message": "No audit has been run yet. Trigger via POST."}), 200
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/telemetry/perf', methods=['POST'])
def trigger_perf_audit():
    """Triggers a fresh performance audit and returns the results."""
    if not PERF_AUDIT_AVAILABLE:
        return jsonify({"error": "Performance audit module not available"}), 503
    try:
        report = run_audit()
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Market News Intelligence Report ────────────────────────────
try:
    from market_news_report import generate_news_report, load_cached_report
    NEWS_REPORT_AVAILABLE = True
except ImportError:
    NEWS_REPORT_AVAILABLE = False

@app.route('/api/news-report', methods=['GET'])
def get_news_report():
    """Returns the latest cached news report."""
    if not NEWS_REPORT_AVAILABLE:
        return jsonify({"error": "News report module not available"}), 503
    try:
        report = load_cached_report()
        if not report:
            return jsonify({"status": "no_data", "message": "No report generated yet. Trigger via POST."}), 200
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/news-report', methods=['POST'])
def trigger_news_report():
    """Generates a fresh market news intelligence report."""
    if not NEWS_REPORT_AVAILABLE:
        return jsonify({"error": "News report module not available"}), 503
    try:
        # Fetch live snapshot if Loki is available
        snapshot = None
        if Loki:
            try:
                loki = Loki()
                snapshot = loki.get_market_snapshot()
            except Exception:
                pass
        report = generate_news_report(market_snapshot=snapshot)
        return jsonify(report)
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

# ── N8N Workflow Health Guard ─────────────────────────────────
# Critical Alpha workflow IDs that must be active for intelligence
ALPHA_N8N_WORKFLOWS = {
    "Q36ImsxRy4by47kw": "Alpha Architect - Genesis (v3)",
    "S8KVkRMA56B21MXs": "Alpha Architect - Research (v2 Robust)",
    "VkE0dmwynRPMIyjdmiONL": "Alpha_V2_Macro_Event_Tracker",
    "tbQnSD6n9JHHvZ3D": "Alpha Ledger Daily Cron",
}

def ensure_n8n_workflows_active():
    """Auto-activates any deactivated Alpha N8N workflows on startup."""
    if not N8N_API_KEY:
        print("⚠️ N8N Health Guard: No API key — skipping workflow check.")
        return
    
    headers = {"X-N8N-API-KEY": N8N_API_KEY}
    base = "https://humanresource.app.n8n.cloud/api/v1"
    activated = 0
    already_ok = 0
    failed = 0
    
    for wid, name in ALPHA_N8N_WORKFLOWS.items():
        try:
            # Check current status
            r = requests.get(f"{base}/workflows/{wid}", headers=headers, timeout=10)
            if r.status_code != 200:
                print(f"  [N8N Guard] Could not check {name}: HTTP {r.status_code}")
                failed += 1
                continue
            
            wf = r.json()
            if wf.get("active"):
                already_ok += 1
                continue
            
            # Activate it
            r = requests.post(f"{base}/workflows/{wid}/activate", headers=headers, timeout=10)
            if r.status_code == 200:
                print(f"  [N8N Guard] Re-activated: {name}")
                activated += 1
            else:
                print(f"  [N8N Guard] Failed to activate {name}: {r.status_code}")
                failed += 1
        except Exception as e:
            print(f"  [N8N Guard] Error checking {name}: {e}")
            failed += 1
    
    if activated > 0:
        print(f"🛡️ N8N Health Guard: {activated} workflow(s) re-activated, {already_ok} already online, {failed} failed.")
    else:
        print(f"🛡️ N8N Health Guard: All {already_ok} Alpha workflows online.")


if __name__ == '__main__':
    public_url = None

    if not NGROK_TOKEN:
        print("⚠️ WARNING: NGROK_AUTH_TOKEN missing from vault/.env — running in LOCAL-ONLY mode.")
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
            conn_info_path  = os.path.join(RUNTIME_DIR, "connection_info.json")
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

        except Exception as e:
            print(f"⚠️ Ngrok tunnel failed: {e}")
            print("   Continuing in LOCAL-ONLY mode (no remote access).")

    # CHECK N8N WORKFLOW HEALTH (auto-activate any offline workflows)
    ensure_n8n_workflows_active()

    # PERFORM WARM-UP (runs regardless of ngrok status)
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


# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
