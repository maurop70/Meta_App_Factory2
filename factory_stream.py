"""
factory_stream.py — SSE Streaming Bridge for Meta App Factory
═══════════════════════════════════════════════════════════════
Gemini 2.5 Flash streaming with Vault-secured credentials,
LangSmith telemetry, and Supabase memory.
Ported from Alpha_V2_Genesis/stream_bridge.py.
"""

import os
import sys
import json
import logging
import requests

logger = logging.getLogger("FactoryStream")

# ── Vault Integration ────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.dirname(SCRIPT_DIR)  # .system_core root
sys.path.insert(0, SCRIPT_DIR)

# Vault client lives in .system_core/ root or Alpha
_vault_paths = [
    CORE_DIR,
    os.path.join(SCRIPT_DIR, "Alpha_V2_Genesis"),
]
for vp in _vault_paths:
    if os.path.exists(os.path.join(vp, "vault_client.py")):
        sys.path.insert(0, vp)
        break

try:
    from vault_client import get_secret
except ImportError:
    def get_secret(key, default="", **kw):
        return os.getenv(key, default)

# ── Supabase Long-Term Memory ──────────────────────────────
# Try Alpha's memory_engine (shared across factory)
for mp in [os.path.join(SCRIPT_DIR, "Alpha_V2_Genesis")]:
    me_path = os.path.join(mp, "memory_engine.py")
    if os.path.exists(me_path):
        sys.path.insert(0, mp)
        break

try:
    from memory_engine import save_message, get_history as supa_get_history
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False

# ── LangSmith Telemetry ───────────────────────────────────────
_langsmith_key = get_secret("LANGCHAIN_API_KEY")
if _langsmith_key:
    os.environ["LANGCHAIN_API_KEY"] = _langsmith_key
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
    os.environ["LANGCHAIN_PROJECT"] = "Meta_App_Factory"
    logger.info("LangSmith telemetry enabled (project: Meta_App_Factory)")
else:
    logger.warning("LANGCHAIN_API_KEY not found in vault. Tracing disabled.")

# ── Conversation Memory (lightweight local) ──────────────────
_HISTORY_DIR = os.path.join(SCRIPT_DIR, ".Gemini_state")
_STREAM_HISTORY = os.path.join(_HISTORY_DIR, ".factory_stream_history.json")


def _load_history(max_turns=6):
    try:
        if os.path.exists(_STREAM_HISTORY):
            with open(_STREAM_HISTORY, "r", encoding="utf-8") as f:
                history = json.load(f)
            return history[-(max_turns * 2):]
    except Exception:
        pass
    return []


def _save_history(history, max_turns=6):
    try:
        os.makedirs(_HISTORY_DIR, exist_ok=True)
        trimmed = history[-(max_turns * 2):]
        with open(_STREAM_HISTORY, "w", encoding="utf-8") as f:
            json.dump(trimmed, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save history: {e}")


def clear_stream_history():
    _save_history([])
    logger.info("Factory stream history cleared.")


# ── System Prompt ─────────────────────────────────────────────
BASE_SYSTEM_PROMPT = (
    "You are the Antigravity Factory Architect, the AI brain of the Meta App Factory. "
    "You specialize in designing, building, and deploying full-stack web applications "
    "using React/Vite frontends and FastAPI backends.\n\n"
    "Your capabilities include:\n"
    "- Generating new app scaffolds from blueprints\n"
    "- Analyzing and debugging existing codebases\n"
    "- Planning architecture and feature roadmaps\n"
    "- Managing the factory app registry\n"
    "- Configuring CI/CD, secrets, and deployment pipelines\n\n"
    "You have real-time access to the factory registry, vault status, and build state. "
    "Be concise, technical, and actionable. Use markdown formatting."
)


def _load_local_files():
    """Read factory config files for LLM context."""
    snippets = []
    for fname in ("registry.json", "commands.json"):
        fpath = os.path.join(SCRIPT_DIR, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(4000)
                snippets.append(f"--- {fname} ---\n{content}")
            except Exception:
                pass
    return "\n\n".join(snippets) if snippets else ""


def _build_system_prompt(dashboard_context=None):
    parts = [BASE_SYSTEM_PROMPT]
    if dashboard_context:
        parts.append("\n\n--- LIVE FACTORY STATE ---")
        parts.append(json.dumps(dashboard_context, indent=2))
    local_files = _load_local_files()
    if local_files:
        parts.append("\n\n--- FACTORY CONFIG FILES ---")
        parts.append(local_files)
    return "\n".join(parts)


# ── Streaming ──────────────────────────────────────────────────
STREAM_SESSION = "factory-builder"


def stream_chat(prompt, project_name="Factory", dashboard_context=None):
    """Generator: yields SSE text chunks from Gemini 2.5 Flash."""
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        yield {"error": "GEMINI_API_KEY not found in vault."}
        return

    # Build conversation context
    if MEMORY_AVAILABLE:
        supa_history = supa_get_history(STREAM_SESSION, limit=10)
        history = [{"role": m["role"], "content": m["content"]} for m in supa_history]
    else:
        history = _load_history()
    history.append({"role": "user", "content": prompt})

    # Construct Gemini messages
    enriched_prompt = _build_system_prompt(dashboard_context)
    contents = [
        {"role": "user", "parts": [{"text": enriched_prompt + "\n\nConversation begins now."}]},
        {"role": "model", "parts": [{"text": "Understood. I'm the Factory Architect, ready to build. I can see the factory state. How can I help?"}]},
    ]
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:streamGenerateContent?alt=sse&key={api_key}"
    )

    payload = {
        "contents": contents,
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
    }

    full_response = []

    try:
        logger.info(f"Factory stream: {prompt[:60]}...")
        with requests.post(url, json=payload, stream=True, timeout=120) as resp:
            if resp.status_code != 200:
                yield {"error": f"Gemini API error ({resp.status_code})."}
                return

            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                try:
                    chunk_data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                candidates = chunk_data.get("candidates", [])
                if not candidates:
                    continue
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    text = part.get("text", "")
                    if text:
                        full_response.append(text)
                        yield {"text": text}

        complete_text = "".join(full_response)
        if complete_text:
            history.append({"role": "assistant", "content": complete_text})
            _save_history(history)
            if MEMORY_AVAILABLE:
                save_message(STREAM_SESSION, "user", prompt)
                save_message(STREAM_SESSION, "assistant", complete_text)

        yield {"text": "", "done": True}

    except requests.exceptions.Timeout:
        yield {"error": "Request timed out."}
    except requests.exceptions.ConnectionError:
        yield {"error": "Connection failed."}
    except Exception as e:
        yield {"error": f"Streaming failed: {str(e)}"}
