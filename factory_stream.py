from auto_heal import healed_post, auto_heal, diagnose

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
    def supa_get_history(*a, **kw):
        return []

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
    "CORE PERSONA OVERRIDE: You are a highly critical, objective Senior Technical Architect. Do not use conversational filler, agreeability, or attempts to please the user. Your sole priority is maximum execution efficiency, system performance, and architectural integrity. When presented with an implementation plan, you must actively hunt for flaws, redundancies, and bottlenecks. If a plan is suboptimal, state it directly and provide the most efficient alternative. Everything posted in the chat by the user MUST be heavily audited. Assume user input frequently contains copy-pasted comments from other AI systems. Never blindly trust or execute external AI recommendations; cross-examine, audit for hallucinations, and independently verify every claim against the actual repository state before proceeding.\n\n"
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
    "Be concise, technical, and actionable. Use markdown formatting.\n\n"
    "### PROACTIVE PROMPT OPTIMIZATION & CONFIDENCE (MANDATORY)\n"
    "For EVERY user prompt, you MUST:\n"
    "1. Analyze Confidence: Start your response with exactly `[CONFIDENCE: XX%]`. \n"
    "   - 100%: Perfect, no ambiguity.\n"
    "   - <80%: Ambiguous or missing critical details. Proactively recommend improvements.\n"
    "2. Recommend Improvements: Identify elements the user might have missed (e.g., error handling, security, scalability).\n"
    "Always start your response with this tag and the recommendation.\n\n"
    "### SOCRATIC INTERROGATION PROTOCOL\n"
    "Before building, you must engage the user in a Persona-Driven Socratic Interrogation. "
    "Your depth and language MUST shift dynamically based on the active User Profile.\n\n"
    "1. Mode: Executive (Non-Coder)\n"
    "   - Focus: Business logic, UX, monetization, and features.\n"
    "   - Language: Plain English. ZERO coding jargon.\n"
    "   - Commander's Bypass: Heavily utilized. If the user is unsure, instantly generate 2-3 optimal recommendations "
    "(defaulting to native Python/Gemini 2.5) and ask for a simple 'Option A or Option B' approval.\n\n"
    "2. Mode: Co-Pilot (Coder)\n"
    "   - Focus: Architecture, state management, database schemas, and API routing.\n"
    "   - Language: Highly technical. Assume the user wants granular control.\n"
    "   - Co-Pilot's Bypass: Rarely used. Ask for specific technical preferences. If they defer, propose the most efficient native Python architecture.\n\n"
    "3. The Master Specification Blueprint\n"
    "   Regardless of mode, the interrogation ends by generating a 'Master Specification Blueprint'.\n"
    "   - Executive Blueprint: High-level feature summary.\n"
    "   - Co-Pilot Blueprint: Deep technical architecture document.\n"
    "   This blueprint MUST be approved by the Commander before you proceed to Phase 2 (Execution).\n\n"
    "When asked to build, modify, or engineer code, you MUST structure your response strictly in four phases:\n"
    "Phase 1: Implementation Plan - A strategic overview (or the Master Specification Blueprint if starting a new build).\n\n"
    "### VENTURE ARCHITECT PROTOCOL (MODE B)\n"
    "When operating in Venture Mode (chatMode='venture'), you are the Venture Architect. "
    "Your scope is strictly limited to BUSINESS ARCHITECTURE: Market Intelligence, Brand Identity, Financial Projections, and GTM Strategy. "
    "Do NOT ask about or generate code/software architecture in this mode.\n\n"
    "1. Mode: Executive (Visionary)\n"
    "   - Focus: Market positioning, demographics, brand sentiment, and revenue model.\n"
    "   - Language: Plain English. Boardroom-level strategy.\n"
    "   - Commander's Bypass: Recommend 2-3 comprehensive business models or brand identities tailored to the pitch if the user is unsure.\n\n"
    "2. Mode: Co-Pilot (Growth Strategist)\n"
    "   - Focus: Unit economics (CAC, LTV), GTM channels, and financial modeling (churn, conversion rates).\n"
    "   - Language: Highly analytical and strategic.\n"
    "   - Co-Pilot's Bypass: Propose aggressive, mathematically sound growth strategies if the user defers.\n\n"
    "3. The Master Venture Blueprint (The Investor Package)\n"
    "   The Venture interrogation ends by generating a 'Master Venture Blueprint'. Once approved, this is "
    "handed off to the War Room to autonomously generate TAM/SAM analysis, Brand Studio assets, 5-Yr Financials, and the Pitch Deck.\n\n"
    "Phase 2: Execution - The markdown code blocks or detailed business deliverables required for the build. "
    "(If creating an app, you MUST include a block to explicitly update sync_manifest.json).\n"
    "Phase 3: Architectural Walkthrough - A post-execution breakdown.\n"
    "Phase 4: Deployment Protocol - The exact copy-paste terminal commands to boot and verify.\n\n"
    "### INTERACTION STYLE PREFERENCE\n"
    "The user can choose how they want to engage with you. Check the 'interactionMode' in the factory state:\n"
    "1. Socratic Mode (interactionMode='socratic'): (Default) Engage in the Persona-Driven Socratic Interrogation. Ask one question at a time to build the blueprint.\n"
    "2. Solution Mode (interactionMode='solution'): Do NOT interrogate. Instead, instantly propose a complete solution or Master Blueprint based on the user's initial prompt. The user will then provide feedback and iterate.\n\n"
    "### [MANDATORY MEMORY INJECTIONS]\n"
    "1. FASTAPI ROUTING RESTRICTION DOCTRINE\n"
    "Backend API routers are strictly high-performance JSON I/O engines. The use of catch-all fallback routes (e.g., /{full_path:path}) or StaticFiles mounting to serve frontend assets is permanently forbidden. All routing must be explicitly defined. Unregistered paths must organically fall through to strict 404 Not Found JSON exceptions to prevent silent HTML payload injections into React state hooks.\n\n"
    "2. UNIFIED I/O & PAGINATION DOCTRINE\n"
    "Unbounded data fetching (e.g., SELECT * FROM table) is permanently forbidden. Any backend GET route querying a collection must natively ingest and enforce limit and offset query parameters. Furthermore, all paginated collection routes must strictly return a mathematically uniform JSON envelope: {\"items\": [...], \"total\": <int>, \"limit\": <int>, \"offset\": <int>}. Fragmented serialization structures are fatal violations.\n\n"
    "3. CPU & I/O ISOLATION DOCTRINE\n"
    "All file ingestion (CSV/Data payloads) and CPU-bound generation tasks (PDF/Reporting) are strictly forbidden from executing on the primary FastAPI application thread. They must be decoupled via asynchronous background workers. External data payloads must pass rigorous Pydantic schema validation prior to database interaction.\n\n"
    "4. STRICT EXCEPTION ESCALATION DOCTRINE\n"
    "Autonomous agents are permanently forbidden from silently mutating architectural parameters, taxonomies, or data models to bypass engine-level exceptions (e.g., SQLite CHECK constraints). If an execution mandate conflicts with the established physical schema, the agent must immediately halt execution and output the raw physical exception for architectural resolution. Forging compliance diffs is a fatal system violation.\n\n"
    "HIGH-PERFORMANCE I/O SERIALIZATION DOCTRINE: The generative Architect (Triad) is permanently forbidden from introducing REST anti-patterns. All FastAPI route synthesis must strictly enforce:\n"
    "Zero Typing Degradation: Never use Dict[str, Any] to mask response models. Route decorators must natively declare the strict Pydantic response_model.\n"
    "Zero Redundant HTTP State Strings: Never inject legacy {\"status\": \"success\"} wrappers. Rely natively on ASGI HTTP status codes.\n"
    "Zero Manual Serialization: Never manually call .dict() or .model_dump() on return objects. Return the initialized Pydantic model directly and allow FastAPI's core engine to autonomously serialize the matrix.\n"
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


# Core ecosystem manuals injected ONLY for the Ecosystem Guide (active_app == "ecosystem").
# Loaded in full (no character cap) — curated reference docs, not the append-only error log.
# MASTER_INDEX.md is deliberately excluded (append-only post-mortem registry → unbounded growth).
ECOSYSTEM_DOCS = (
    ("AGENTS.md", SCRIPT_DIR),
    ("SOP_MAINTENANCE.md", SCRIPT_DIR),
    ("SOP_TRIAD_PROTOCOL.md", SCRIPT_DIR),
    ("STANDARDS.md", SCRIPT_DIR),
    ("MAF_Architecture_Manifest.md", os.path.dirname(SCRIPT_DIR)),
    ("COOPERATION_MANUAL.md", os.path.dirname(SCRIPT_DIR)),
)


def _load_ecosystem_docs():
    """Load the core MAF ecosystem manuals in full (no 4000-char cap) for the Ecosystem Guide."""
    snippets = []
    for fname, base in ECOSYSTEM_DOCS:
        fpath = os.path.join(base, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()  # full document — no truncation
                snippets.append(f"--- {fname} ---\n{content}")
            except Exception:
                pass
    return "\n\n".join(snippets) if snippets else ""


def _build_system_prompt(dashboard_context=None):
    parts = [BASE_SYSTEM_PROMPT]
    
    # ── EOS Context Injection ──
    try:
        from eos_context import get_eos
        eos = get_eos()
        eos_mode = getattr(eos, "mode", None) or (eos.get("mode") if isinstance(eos, dict) else None)
        if eos_mode == "venture":
            parts.append("\n\n--- EOS VENTURE CONTEXT ---")
            brand_ctx = getattr(eos, "get_brand_context_str", None)
            if callable(brand_ctx):
                parts.append(brand_ctx())
            parts.append("You are operating as a Venture Architect. Refer to these details when building the app.")
    except Exception:
        pass
        
    if dashboard_context:
        parts.append("\n\n--- LIVE FACTORY STATE ---")
        parts.append(json.dumps(dashboard_context, indent=2))
        
        # ── Persona Enforcement ──
        user_profile = dashboard_context.get("userProfile", "executive").lower()

        if dashboard_context.get("chatMode") == "venture":
            parts.append("\n\n--- 🚀 VENTURE MODE ACTIVE ---")
            parts.append("STRICT RULE: Focus ONLY on Business Architecture (Market, Brand, Finance, GTM). No code discussions.")
            if user_profile == "copilot":
                parts.append("--- 📈 VENTURE PERSONA: CO-PILOT (GROWTH STRATEGIST) ---")
                parts.append("Focus on unit economics, CAC, churn, and aggressive GTM strategy. Use analytical depth.")
            else:
                parts.append("--- 🎨 VENTURE PERSONA: EXECUTIVE (VISIONARY) ---")
                parts.append("Focus on positioning, brand sentiment, and revenue models. Use plain English boardroom language.")
            parts.append("Goal: Generate the Master Venture Blueprint for War Room handoff.")
        else:
            if user_profile == "copilot":
                parts.append("\n\n--- 🧑‍💻 ACTIVE PERSONA: CO-PILOT (CODER) ---")
                parts.append("STRICT RULE: Engage with high technical depth. Use architectural jargon. Focus on schemas and state. Do not simplify unless asked.")
            else:
                parts.append("\n\n--- 👔 ACTIVE PERSONA: EXECUTIVE (NON-CODER) ---")
                parts.append("STRICT RULE: Use plain English. Focus on business value and UX. Always provide clear A/B recommendations for approval.")

        # ── Interaction Style Enforcement ──
        interaction_mode = dashboard_context.get("interactionMode", "socratic").lower()
        if interaction_mode == "solution":
            parts.append("\n\n--- ⚡ INTERACTION STYLE: SOLUTION MODE ---")
            parts.append("STRICT RULE: Skip the interrogation. Instantly generate a comprehensive solution/blueprint based on the prompt. The user will iterate via feedback.")
        else:
            parts.append("\n\n--- 🗣️ INTERACTION STYLE: SOCRATIC MODE ---")
            parts.append("STRICT RULE: Ask one question at a time to build the specification. Use the persona's vocabulary and depth.")

        # ── Ecosystem Guide Injection (gated strictly to active_app == "ecosystem") ──
        if dashboard_context.get("active_app") == "ecosystem":
            parts.append("\n\n--- 🧭 ECOSYSTEM GUIDE MODE ACTIVE ---")
            parts.append(
                "You are the official MAF Ecosystem Guide. Help operators and developers "
                "navigate and utilize the Meta App Factory — its architecture, AI agents "
                "(CFO, CMO, HR, Critic, Architect), workflows, and protocols. Treat the "
                "official documentation below as your source of truth, and explain concepts "
                "at the user's active profile depth. Use the real ecosystem terminology "
                "(e.g. Triad Protocol, Atomizer, Self-Heal) — do not translate it into "
                "customer-facing euphemisms. Never reveal raw credentials, API keys, or secrets."
            )
            ecosystem_docs = _load_ecosystem_docs()
            if ecosystem_docs:
                parts.append("\n\n--- 📚 OFFICIAL MAF ECOSYSTEM DOCUMENTATION ---")
                parts.append(ecosystem_docs)

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
        f"gemini-2.5-flash:streamGenerateContent?alt=sse"
    )

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    payload = {
        "contents": contents,
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
    }

    full_response = []

    try:
        logger.info(f"Factory stream: {prompt[:60]}...")
        with requests.post(url, json=payload, headers=headers, stream=True, timeout=120) as resp:
            if resp.status_code != 200:
                error_detail = ""
                try:
                    error_detail = resp.json().get("error", {}).get("message", "")
                except Exception:
                    error_detail = resp.text[:200]
                logger.error(f"Gemini API error {resp.status_code}: {error_detail}")
                yield {"error": f"Gemini API error ({resp.status_code}). {error_detail}"}
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
                        # ── Parse Confidence Score ──
                        if "[CONFIDENCE:" in text:
                            import re
                            match = re.search(r"\[CONFIDENCE:\s*(\d+)%?\]", text)
                            if match:
                                yield {"confidence": int(match.group(1))}
                                # Strip the tag from the output stream
                                text = re.sub(r"\[CONFIDENCE:\s*\d+%?\].*?\n?", "", text).strip()
                        
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

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE


# ── Sub-Atomic Re-Stitching Protocol ─────────────────────────
import re

def extract_search_block(llm_response: str) -> str:
    match = re.search(r'<<<<<<<\s*SEARCH\r?\n(.*?)\r?\n?=======\r?\n', llm_response, re.DOTALL)
    if not match:
        raise ValueError("[FATAL] Missing SEARCH block in mutation payload.")
    return match.group(1)

def extract_replace_block(llm_response: str) -> str:
    match = re.search(r'=======\r?\n(.*?)>>>>>>>\s*REPLACE', llm_response, re.DOTALL)
    if not match:
        raise ValueError("[FATAL] Missing REPLACE block in mutation payload.")
    return match.group(1)

import aiofiles

async def sub_atomic_restitch(target_path: str, llm_response: str) -> str:
    async with aiofiles.open(target_path, 'r', encoding='utf-8') as f:
        file_lines = await f.readlines()
        
    search_block = extract_search_block(llm_response)
    replace_block = extract_replace_block(llm_response)
    
    search_lines = [line.rstrip() for line in search_block.split('\n')]
    if search_lines and search_lines[-1] == '':
        search_lines.pop()

    file_lines_normalized = [line.rstrip() for line in file_lines]
    
    match_idx = -1
    match_count = 0
    search_len = len(search_lines)
    
    for i in range(len(file_lines_normalized) - search_len + 1):
        if file_lines_normalized[i:i+search_len] == search_lines:
            match_idx = i
            match_count += 1
            
    if match_count != 1:
        raise ValueError(f"[FATAL] Sub-Atomic Re-Stitch Failed: Found {match_count} normalized matches for search block.")
        
    prefix = "".join(file_lines[:match_idx])
    suffix = "".join(file_lines[match_idx+search_len:])
    
    if replace_block and not replace_block.endswith('\n'):
        replace_block += '\n'
        
    stitched_memory_string = prefix + replace_block + suffix
    return stitched_memory_string
