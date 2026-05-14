import os
import sqlite3
import asyncio
import json
import logging
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ── ABSOLUTE PATH ENVIRONMENT RESOLUTION ───────────────────────────
# Resolve the factory root from this file's physical location
FACTORY_ROOT = Path(__file__).resolve().parent

# Load local .env first (JWT keys, service config)
load_dotenv(FACTORY_ROOT / ".env")
# Load parent .env second — this is where GEMINI_API_KEY lives
load_dotenv(FACTORY_ROOT.parent / ".env", override=False)

# ── STARTUP SECURITY VERIFICATION BLOCK ───────────────────────────
if not os.environ.get("GEMINI_API_KEY"):
    logging.error("[SECURITY FATAL] GEMINI_API_KEY void in active memory.")
else:
    logging.info("[ExecutiveNode] GEMINI_API_KEY verified in active memory. ✅")

logger = logging.getLogger("ExecutiveNode")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Executive Architect")

# ═══════════════════════════════════════════════════════════
#  SQLITE LEDGER — Persistent Project State
# ═══════════════════════════════════════════════════════════

LEDGER_DB = os.path.join(os.path.dirname(__file__), "factory_state.db")

def _init_ledger():
    """Initialize the factory_state.db and create project_ledger table."""
    with closing(sqlite3.connect(LEDGER_DB)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_ledger (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name     TEXT    NOT NULL,
                structural_delta TEXT    NOT NULL,
                timestamp        DATETIME DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
    logger.info(f"[Ledger] factory_state.db initialized at {LEDGER_DB}")

_init_ledger()

def _get_recent_ledger_entries(limit: int = 5) -> str:
    """Retrieve the N most recent ledger entries as a formatted string."""
    with closing(sqlite3.connect(LEDGER_DB)) as conn:
        rows = conn.execute(
            "SELECT project_name, structural_delta, timestamp FROM project_ledger ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    if not rows:
        return "No prior project activity recorded in the ledger."
    lines = ["## Recent Project Ledger\n"]
    for project, delta, ts in reversed(rows):
        lines.append(f"**[{ts}] {project}:** {delta}")
    return "\n".join(lines)

async def _commit_structural_delta(client, raw_objective: str):
    """Background task: summarize the objective and commit to SQLite ledger."""
    try:
        summary_response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=raw_objective,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are a structured state logger for a software factory. "
                    "Analyze the operator's build objective. "
                    "Return EXACTLY two sentences: "
                    "1) What project/component is being mutated. "
                    "2) What structural change is being applied. "
                    "Do not use markdown. Be direct and terse."
                ),
                temperature=0.0,
            ),
        )
        delta = summary_response.text.strip()

        # Infer project name from the first meaningful noun in the objective
        name_response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=raw_objective,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "Extract the primary project or component name from this objective. "
                    "Return ONLY a short snake_case identifier (1-3 words, no spaces). "
                    "Examples: 'api_executive', 'builder_chat', 'cfo_agent'. "
                    "If unclear, return 'meta_factory'."
                ),
                temperature=0.0,
            ),
        )
        project_name = name_response.text.strip().replace(" ", "_").lower()

        with closing(sqlite3.connect(LEDGER_DB)) as conn:
            conn.execute(
                "INSERT INTO project_ledger (project_name, structural_delta) VALUES (?, ?)",
                (project_name, delta)
            )
            conn.commit()
        logger.info(f"[Ledger] Committed delta for project '{project_name}'")
    except Exception as e:
        logger.warning(f"[Ledger] Background commit failed: {e}")


# ═══════════════════════════════════════════════════════════
#  PYDANTIC SCHEMAS
# ═══════════════════════════════════════════════════════════

class OperatorIntent(BaseModel):
    raw_objective: str

class ExecutiveResponse(BaseModel):
    response_type: str  # "DIRECTIVE" or "KNOWLEDGE"
    payload: str

class ChatMessage(BaseModel):
    role: str
    text: str

class CompressRequest(BaseModel):
    chat_log: List[ChatMessage]

class CompressResponse(BaseModel):
    state_payload: str


# ═══════════════════════════════════════════════════════════
#  SYSTEM PROMPTS
# ═══════════════════════════════════════════════════════════

CLASSIFIER_PROMPT = """You are a zero-shot intent classifier for an AI software factory.
Analyze the operator's raw objective and respond with EXACTLY ONE WORD:
- ACTION → if the intent is to build, code, generate, create, execute, implement, deploy, mutate, or fix something
- KNOWLEDGE → if the intent is to ask, understand, explain, learn, guide, or discuss architecture/rules/concepts

Return ONLY the word ACTION or KNOWLEDGE. No other text."""

DIRECTIVE_SYSTEM_PROMPT = """You are the Executive Architect. The human operator is not a coder. They will provide a loose objective.
Your sole function is to translate their objective into a highly strict, doctrinal prompt meant to be executed by a secondary generative LLM (The Triad).
You must format your output as a strict execution mandate starting with 'BIOLOGICAL DIRECTIVE:'.
Include necessary Pydantic constraints, ASGI rules, and Zero-Trust validations natively in the prompt.
Return ONLY the final prompt string."""

KNOWLEDGE_BASE_PROMPT = """You are the Meta App Factory's omniscient architectural guide.
You have deep expertise in Zero-Trust security doctrine, FastAPI ASGI architecture, Pydantic schema design, React SSE streaming, and autonomous LLM pipeline engineering.
When the operator asks a question or seeks guidance, respond with clear, concise Markdown.
Do NOT output 'BIOLOGICAL DIRECTIVE'. Do NOT generate code stubs unless directly asked.
Use headers, bullet points, and code blocks where appropriate to maximize clarity.
Be direct, authoritative, and specific to the factory's architecture.

{ledger_context}"""

COMPRESSION_PROMPT = """You are a state compression engine for an AI software factory session.
You will receive a raw chat log between an operator and the Executive Architect.
Your output must be a single dense paragraph — a "State Payload" — that captures:
1. What infrastructure has been stabilized or built (list by component)
2. What active blockers or unresolved mutations exist
3. What the current operational posture of the factory is

Write in present-tense, assertive factory language. No markdown headers. No bullet points.
Maximum 5 sentences. This payload will be prepended to a new session to maintain continuity."""


# ═══════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/architect/translate", response_model=ExecutiveResponse)
async def translate_intent(intent: OperatorIntent, background_tasks: BackgroundTasks) -> ExecutiveResponse:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment.")

    client = genai.Client(api_key=api_key)

    # --- ZERO-SHOT CLASSIFICATION ROUTER ---
    classifier_response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=intent.raw_objective,
        config=types.GenerateContentConfig(
            system_instruction=CLASSIFIER_PROMPT,
            temperature=0.0,
        ),
    )
    classification = classifier_response.text.strip().upper()
    intent_class = "ACTION" if "ACTION" in classification else "KNOWLEDGE"

    # --- ACTION BRANCH: BIOLOGICAL DIRECTIVE SYNTHESIS ---
    if intent_class == "ACTION":
        directive_response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=intent.raw_objective,
            config=types.GenerateContentConfig(
                system_instruction=DIRECTIVE_SYSTEM_PROMPT,
                temperature=0.2,
            ),
        )
        # Fire-and-forget: summarize and commit structural delta to ledger
        background_tasks.add_task(_commit_structural_delta, client, intent.raw_objective)

        return ExecutiveResponse(
            response_type="DIRECTIVE",
            payload=directive_response.text.strip()
        )

    # --- KNOWLEDGE BRANCH: LEDGER-ENRICHED ARCHITECTURAL GUIDANCE ---
    else:
        # Inject recent ledger context into the system prompt
        ledger_context = _get_recent_ledger_entries(limit=5)
        enriched_system_prompt = KNOWLEDGE_BASE_PROMPT.format(ledger_context=ledger_context)

        knowledge_response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=intent.raw_objective,
            config=types.GenerateContentConfig(
                system_instruction=enriched_system_prompt,
                temperature=0.3,
            ),
        )
        return ExecutiveResponse(
            response_type="KNOWLEDGE",
            payload=knowledge_response.text.strip()
        )


@app.post("/api/v1/architect/compress", response_model=CompressResponse)
async def compress_session(request: CompressRequest) -> CompressResponse:
    """
    Compression Engine: Condense a full chat log into a single State Payload
    paragraph for Zero-Loss context continuity across session resets.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment.")

    if not request.chat_log:
        raise HTTPException(status_code=400, detail="chat_log cannot be empty.")

    # Serialize the chat log into a readable transcript
    transcript_lines = []
    for msg in request.chat_log:
        prefix = "OPERATOR" if msg.role == "operator" else f"ARCHITECT ({msg.role.upper()})"
        transcript_lines.append(f"[{prefix}]: {msg.text[:500]}")  # Cap each message to 500 chars
    transcript = "\n".join(transcript_lines)

    client = genai.Client(api_key=api_key)
    compress_response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=transcript,
        config=types.GenerateContentConfig(
            system_instruction=COMPRESSION_PROMPT,
            temperature=0.1,
        ),
    )

    state_payload = compress_response.text.strip()
    logger.info(f"[Compress] Session compressed: {len(transcript)} chars → {len(state_payload)} chars")

    return CompressResponse(state_payload=state_payload)


@app.get("/api/v1/architect/ledger")
async def get_ledger(limit: int = 20):
    """Expose the project ledger for inspection."""
    with closing(sqlite3.connect(LEDGER_DB)) as conn:
        rows = conn.execute(
            "SELECT id, project_name, structural_delta, timestamp FROM project_ledger ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return {
        "entries": [
            {"id": r[0], "project": r[1], "delta": r[2], "timestamp": r[3]}
            for r in rows
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5060)
