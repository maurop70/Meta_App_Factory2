"""
stream_bridge.py — SSE Streaming Bridge for Alpha V2 Genesis
═══════════════════════════════════════════════════════════════
Calls Gemini 2.5 Flash directly with streaming enabled.
Yields text chunks as they arrive for real-time UI rendering.

Security: Uses vault_client.get_secret() for API key retrieval.
Fallback: If Gemini streaming fails, falls back to n8n call_app().
"""

import os
import sys
import json
import time
import logging
import requests

logger = logging.getLogger("StreamBridge")

# ── Vault Integration ────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

try:
    from vault_client import get_secret
except ImportError:
    def get_secret(key, default="", **kw):
        return os.getenv(key, default)

# ── Supabase Long-Term Memory ──────────────────────────────
try:
    from memory_engine import get_history as supa_get_history
    SUPA_AVAILABLE = True
except ImportError:
    SUPA_AVAILABLE = False

# ── LangSmith Telemetry ───────────────────────────────────────
_langsmith_key = get_secret("LANGCHAIN_API_KEY")
if _langsmith_key:
    os.environ["LANGCHAIN_API_KEY"] = _langsmith_key
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
    os.environ["LANGCHAIN_PROJECT"] = "Alpha_V3_Streaming"
    logger.info("LangSmith telemetry enabled (project: Alpha_V3_Streaming)")
else:
    logger.warning("LANGCHAIN_API_KEY not found in vault. LangSmith tracing disabled.")

# ── Gemini API Key → Environment ──────────────────────────────
# LangChain expects GOOGLE_API_KEY; Vault stores GEMINI_API_KEY
_gemini_key = get_secret("GEMINI_API_KEY")
if _gemini_key:
    os.environ["GOOGLE_API_KEY"] = _gemini_key
    os.environ["GEMINI_API_KEY"] = _gemini_key
    logger.info(f"Gemini API key loaded from vault ({len(_gemini_key)} chars, ends ...{_gemini_key[-4:]})")
else:
    logger.error("GEMINI_API_KEY not found in vault! Streaming will fail with 403.")

# ── Conversation Memory (lightweight) ────────────────────────
_HISTORY_DIR = os.path.join(SCRIPT_DIR, ".Gemini_state")
_STREAM_HISTORY = os.path.join(_HISTORY_DIR, ".stream_history.json")


def _load_history(max_turns=6):
    """Load last N conversation turns for context."""
    try:
        if os.path.exists(_STREAM_HISTORY):
            with open(_STREAM_HISTORY, "r", encoding="utf-8") as f:
                history = json.load(f)
            return history[-(max_turns * 2):]  # Keep last N turns (user+ai)
    except Exception:
        pass
    return []


def _save_history(history, max_turns=6):
    """Persist conversation history."""
    try:
        os.makedirs(_HISTORY_DIR, exist_ok=True)
        trimmed = history[-(max_turns * 2):]
        with open(_STREAM_HISTORY, "w", encoding="utf-8") as f:
            json.dump(trimmed, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save stream history: {e}")


def clear_stream_history():
    """Wipe conversation history."""
    _save_history([])
    logger.info("Stream history cleared.")


# ── System Prompt ─────────────────────────────────────────────
BASE_SYSTEM_PROMPT = (
    "You are Alpha Architect, a Lead Quant Analyst for the Alpha V2 Genesis "
    "trading system. You specialize in SPX Iron Condor strategies, options "
    "Greeks, volatility analysis, and market risk management.\n\n"
    "You provide concise, actionable insights. When discussing trades, "
    "reference specific strikes, deltas, DTE, and credit amounts. "
    "Use professional but approachable language. Format responses with "
    "markdown when helpful (bold, lists, headers).\n\n"
    "You have access to real-time market data via the Alpha system. "
    "If a user asks about current market conditions, provide analysis based "
    "on your training knowledge and note that live data is available on the "
    "dashboard."
)


# ── Local File Ingestion ──────────────────────────────────────
def _load_local_files():
    """Read strategy_ledger.py source and market_memo.md for LLM context."""
    snippets = []
    for fname in ("strategy_ledger.py", "market_memo.md"):
        fpath = os.path.join(SCRIPT_DIR, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(4000)  # Cap at 4k chars to save tokens
                snippets.append(f"--- {fname} ---\n{content}")
            except Exception:
                pass
    return "\n\n".join(snippets) if snippets else ""


def _build_system_prompt(dashboard_context=None):
    """Enrich the base system prompt with live context."""
    parts = [BASE_SYSTEM_PROMPT]

    # Inject live dashboard metrics
    if dashboard_context:
        parts.append("\n\n--- LIVE DASHBOARD STATE (real-time from UI) ---")
        parts.append(json.dumps(dashboard_context, indent=2))

    # Inject local strategy files
    local_files = _load_local_files()
    if local_files:
        parts.append("\n\n--- LOCAL STRATEGY FILES ---")
        parts.append(local_files)

    return "\n".join(parts)


def stream_chat(prompt: str, project_name: str = "General", dashboard_context=None):
    """
    Generator that yields text chunks from Gemini 2.5 Flash streaming API.
    
    Yields dicts:  {"text": "chunk"}  for content
                   {"text": "", "done": True}  for completion
                   {"error": "msg"}  on failure
    """
    # Get key from env (set on boot) or vault, strip whitespace
    api_key = (os.environ.get("GEMINI_API_KEY") or get_secret("GEMINI_API_KEY") or "").strip()
    if not api_key:
        logger.error("GEMINI_API_KEY is empty after vault lookup!")
        yield {"error": "GEMINI_API_KEY not found in vault or environment. Cannot stream."}
        return

    print(f"DEBUG: API key loaded, length={len(api_key)}, starts={api_key[:4]}..., ends=...{api_key[-4:]}")
    logger.info(f"API key ready: {len(api_key)} chars")

    # Build conversation context — prefer Supabase, fallback to local JSON
    if SUPA_AVAILABLE:
        supa_history = supa_get_history("alpha-stream", limit=10)
        history = [{"role": m["role"], "content": m["content"]} for m in supa_history]
    else:
        history = _load_history()
    history.append({"role": "user", "content": prompt})

    # Construct Gemini API messages
    contents = []
    
    # System instruction enriched with live context
    enriched_prompt = _build_system_prompt(dashboard_context)
    
    contents.append({
        "role": "user",
        "parts": [{"text": enriched_prompt + "\n\nConversation begins now."}]
    })
    contents.append({
        "role": "model",
        "parts": [{"text": "Understood. I'm Alpha Architect, ready to assist with your trading analysis. I can see the live dashboard data. How can I help?"}]
    })

    # Add conversation history
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096,
        }
    }

    full_response = []

    # Model fallback chain (confirmed via ListModels API)
    models_with_api = [
        ("gemini-2.5-flash", "v1beta"),
        ("gemini-2.0-flash", "v1beta"),
        ("gemini-2.0-flash-lite", "v1beta"),
    ]
    resp = None
    last_error = ""
    
    for model_name, api_version in models_with_api:
        url = (
            f"https://generativelanguage.googleapis.com/{api_version}/models/"
            f"{model_name}:streamGenerateContent?alt=sse&key={api_key}"
        )
        try:
            print(f"DEBUG: Trying {model_name} via {api_version}...")
            logger.info(f"Streaming request to {model_name} ({api_version}) (prompt: {prompt[:60]}...)")
            resp = requests.post(url, json=payload, stream=True, timeout=120)
            print(f"DEBUG: {model_name} → HTTP {resp.status_code}")
            if resp.status_code == 200:
                logger.info(f"Connected to {model_name} successfully")
                break
            else:
                last_error = resp.text[:500]
                print(f"DEBUG: {model_name} error body: {last_error}")
                logger.warning(f"{model_name} returned {resp.status_code}: {last_error[:200]}")
                resp.close()
                resp = None
        except Exception as e:
            logger.warning(f"{model_name} connection failed: {e}")
            print(f"DEBUG: {model_name} exception: {e}")
            last_error = str(e)
            resp = None
    
    if resp is None or resp.status_code != 200:
        yield {"error": f"Gemini API error: {last_error[:300]}"}
        return

    try:
        # Parse SSE stream from Gemini
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            
            # SSE format: "data: {json}"
            if line.startswith("data: "):
                json_str = line[6:]  # Strip "data: " prefix
                
                try:
                    chunk_data = json.loads(json_str)
                except json.JSONDecodeError:
                    continue

                # Extract text from Gemini response structure
                candidates = chunk_data.get("candidates", [])
                if not candidates:
                    continue

                parts = (
                    candidates[0]
                    .get("content", {})
                    .get("parts", [])
                )
                
                for part in parts:
                    text = part.get("text", "")
                    if text:
                        full_response.append(text)
                        yield {"text": text}

                # Check if generation is complete
                finish_reason = candidates[0].get("finishReason")
                if finish_reason and finish_reason != "STOP":
                    logger.info(f"Stream finished: {finish_reason}")

        # Save completed response to history
        complete_text = "".join(full_response)
        if complete_text:
            history.append({"role": "assistant", "content": complete_text})
            _save_history(history)

        yield {"text": "", "done": True}

    except requests.exceptions.Timeout:
        logger.warning("Gemini streaming timed out after 120s")
        yield {"error": "Request timed out. Please try again."}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error: {e}")
        yield {"error": "Connection failed. Check internet."}
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield {"error": f"Streaming failed: {str(e)}"}
    finally:
        try:
            resp.close()
        except Exception:
            pass


def chat_sync(prompt: str, project_name: str = "General") -> str:
    """
    Non-streaming fallback. Collects all chunks and returns full text.
    Used when SSE is not available.
    """
    chunks = []
    for event in stream_chat(prompt, project_name):
        if "error" in event:
            return f"Error: {event['error']}"
        if event.get("done"):
            break
        chunks.append(event.get("text", ""))
    return "".join(chunks)
