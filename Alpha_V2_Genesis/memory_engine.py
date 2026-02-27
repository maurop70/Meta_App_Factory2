"""
memory_engine.py — Supabase Long-Term Memory for Alpha V2 Genesis
═════════════════════════════════════════════════════════════════════
Stores and retrieves conversation history from a Supabase `chat_history`
table for persistent, cross-session memory.

Security: Credentials fetched from vault_client at runtime.

Table schema (create in Supabase SQL editor):
    CREATE TABLE chat_history (
      id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      session_id  text    NOT NULL,
      role        text    NOT NULL,     -- 'user' or 'assistant'
      content     text    NOT NULL,
      created_at  timestamptz DEFAULT now()
    );
    CREATE INDEX idx_chat_session ON chat_history (session_id, created_at DESC);
"""

import os
import sys
import logging
import threading
from datetime import datetime

logger = logging.getLogger("MemoryEngine")

# ── Vault Integration ────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

try:
    from vault_client import get_secret
except ImportError:
    def get_secret(key, default="", **kw):
        return os.getenv(key, default)

# ── Supabase Client (lazy singleton) ─────────────────────────
_client = None
_client_lock = threading.Lock()


def _get_client():
    """Lazy-init Supabase REST client. Returns None on failure (graceful degradation)."""
    global _client
    if _client is not None:
        return _client

    with _client_lock:
        if _client is not None:
            return _client

        url = get_secret("SUPABASE_URL")
        key = get_secret("SUPABASE_KEY")

        if not url or not key:
            logger.warning("Supabase credentials not found in vault. Memory engine disabled.")
            return None

        try:
            from postgrest import SyncPostgrestClient
            rest_url = f"{url.rstrip('/')}/rest/v1"
            _client = SyncPostgrestClient(
                base_url=rest_url,
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                }
            )
            logger.info("Supabase memory engine connected (postgrest).")
            return _client
        except ImportError:
            logger.warning("postgrest package not installed. Run: pip install postgrest")
            return None
        except Exception as e:
            logger.error(f"Supabase connection failed: {e}")
            return None


# ── Public API ────────────────────────────────────────────────

def save_message(session_id: str, role: str, content: str) -> bool:
    """
    Inserts a message into the chat_history table.

    Args:
        session_id: Conversation session identifier (e.g., "alpha-stream")
        role:       "user" or "assistant"
        content:    Message text

    Returns:
        True on success, False on failure (never raises)
    """
    client = _get_client()
    if not client:
        return False

    try:
        client.table("chat_history").insert({
            "session_id": session_id,
            "role": role,
            "content": content,
        }).execute()
        return True
    except Exception as e:
        logger.error(f"save_message failed: {e}")
        return False


def save_message_async(session_id: str, role: str, content: str):
    """Fire-and-forget version of save_message for non-blocking writes."""
    thread = threading.Thread(
        target=save_message,
        args=(session_id, role, content),
        daemon=True,
    )
    thread.start()


def get_history(session_id: str, limit: int = 10) -> list[dict]:
    """
    Retrieves the last N messages for a session, ordered oldest-first.

    Args:
        session_id: Conversation session identifier
        limit:      Max number of messages to retrieve (default 10)

    Returns:
        List of dicts: [{"role": "user", "content": "..."}, ...]
        Returns empty list on failure (never raises)
    """
    client = _get_client()
    if not client:
        return []

    try:
        response = (
            client.table("chat_history")
            .select("role, content")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        # Reverse so oldest is first (natural conversation order)
        messages = list(reversed(response.data)) if response.data else []
        return messages
    except Exception as e:
        logger.error(f"get_history failed: {e}")
        return []


def format_history_for_llm(session_id: str, limit: int = 10) -> str:
    """
    Retrieves history and formats it as a context string for the LLM.

    Returns:
        Formatted string like:
        --- CONVERSATION HISTORY ---
        USER: Hello
        ASSISTANT: Hi there
        ----------------------------
    """
    history = get_history(session_id, limit)
    if not history:
        return ""

    lines = ["--- CONVERSATION HISTORY ---"]
    for msg in history:
        role = msg["role"].upper()
        lines.append(f"{role}: {msg['content']}")
    lines.append("----------------------------")
    return "\n".join(lines)


def clear_history(session_id: str) -> bool:
    """Deletes all messages for a given session."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("chat_history").delete().eq("session_id", session_id).execute()
        logger.info(f"Cleared history for session: {session_id}")
        return True
    except Exception as e:
        logger.error(f"clear_history failed: {e}")
        return False
