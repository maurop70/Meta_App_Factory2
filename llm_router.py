import sqlite3
import uuid
import json
import time
from datetime import datetime, timedelta, timezone
from contextlib import closing
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import asyncio

from model_router import CLAUDE_SONNET

router = APIRouter()

DATABASE_FILE = "factory_ephemeral.db"

def init_db():
    """Initializes the SQLite database and the ephemeral_streams table."""
    with closing(sqlite3.connect(DATABASE_FILE)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ephemeral_streams (
                session_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()

# Ensure DB is initialized on startup
init_db()

async def cleanup_ephemeral_streams():
    """Asynchronously purges expired sessions from the ephemeral_streams table."""
    while True:
        await asyncio.sleep(3600)  # Run every hour
        try:
            with closing(sqlite3.connect(DATABASE_FILE)) as conn:
                cursor = conn.cursor()
                one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
                cursor.execute("DELETE FROM ephemeral_streams WHERE created_at < ?", (one_hour_ago,))
                conn.commit()
                print(f"[CLEANUP] Purged ephemeral_streams older than {one_hour_ago}")
        except Exception as e:
            print(f"[FATAL] Ephemeral stream cleanup failed: {e}")

@router.on_event("startup")
async def startup_event():
    """Schedule the cleanup routine on application startup."""
    asyncio.create_task(cleanup_ephemeral_streams())


@router.post("/builder/initiate-stream")
async def initiate_builder_stream(request: Request):
    """
    Initiates a new stream session by storing the prompt payload and returning a session_id.
    """
    try:
        data = await request.json()
        prompt = data.get("prompt")
        cognitive_engine = data.get("cognitive_engine", data.get("model", "gemini-2.5-flash"))
        
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt is required.")

        session_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        
        # Store as JSON to hold both prompt and engine
        payload_data = json.dumps({"prompt": prompt, "cognitive_engine": cognitive_engine})

        with closing(sqlite3.connect(DATABASE_FILE)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO ephemeral_streams (session_id, payload, created_at) VALUES (?, ?, ?)",
                (session_id, payload_data, created_at)
            )
            conn.commit()

        return {"session_id": session_id, "status": "STREAM_INITIATED"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate stream: {e}")

@router.get("/builder/stream")
async def builder_stream(session_id: str, request: Request):
    """
    Streams generation results based on a previously initiated session_id.
    """
    with closing(sqlite3.connect(DATABASE_FILE)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT payload FROM ephemeral_streams WHERE session_id = ?", (session_id,))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Stream session not found or expired.")
        
        raw_payload = result[0]
        try:
            payload_dict = json.loads(raw_payload)
            prompt_payload = payload_dict.get("prompt", raw_payload)
            cognitive_engine = payload_dict.get("cognitive_engine", "gemini-2.5-flash")
        except:
            prompt_payload = raw_payload
            cognitive_engine = "gemini-2.5-flash"

    async def event_generator():
        import os
        import httpx
        import anthropic
        from dotenv import load_dotenv

        load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

        async def stream_claude():
            anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
            if not anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not loaded.")
            client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
            async with client.messages.stream(
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt_payload}],
                model=CLAUDE_SONNET,
            ) as stream:
                async for text in stream.text_stream:
                    yield text

        async def stream_gemini(engine):
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY not loaded.")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{engine}:streamGenerateContent?alt=sse&key={api_key}"
            req_payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt_payload}]}],
                "generationConfig": {"temperature": 0.3}
            }
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, json=req_payload, timeout=60.0) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line[6:]
                        if raw.strip() == "[DONE]":
                            break
                        chunk = json.loads(raw)
                        text = chunk.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text:
                            yield text

        # Determine start strategy
        is_claude_preferred = "claude" in cognitive_engine.lower()

        emitted_any = False

        if is_claude_preferred:
            yield f"data: {json.dumps({'agent': 'Architect', 'status': 'PROCESSING', 'payload': 'Dispatching to Claude...'})}\n\n"
            try:
                async for text in stream_claude():
                    if text:
                        emitted_any = True
                    yield f"data: {json.dumps({'agent': 'Claude', 'status': 'STREAMING', 'payload': text})}\n\n"
            except Exception as e:
                if emitted_any:
                    yield f"data: {json.dumps({'agent': 'System', 'status': 'ERROR', 'payload': f'Claude stream interrupted: {str(e)[:100]}'})}\n\n"
                    return

                yield f"data: {json.dumps({'agent': 'System', 'status': 'WARNING', 'payload': 'Claude stream failed. Falling back to Gemini...'})}\n\n"
                try:
                    async for text in stream_gemini("gemini-2.5-flash"):
                        yield f"data: {json.dumps({'agent': 'Gemini', 'status': 'STREAMING', 'payload': text})}\n\n"
                except Exception as ex:
                    yield f"data: {json.dumps({'agent': 'System', 'status': 'ERROR', 'payload': f'All streams failed: {str(ex)[:100]}'})}\n\n"
        else:
            yield f"data: {json.dumps({'agent': 'Architect', 'status': 'PROCESSING', 'payload': 'Dispatching to Gemini...'})}\n\n"
            try:
                async for text in stream_gemini(cognitive_engine):
                    if text:
                        emitted_any = True
                    yield f"data: {json.dumps({'agent': 'Gemini', 'status': 'STREAMING', 'payload': text})}\n\n"
            except Exception as e:
                if emitted_any:
                    yield f"data: {json.dumps({'agent': 'System', 'status': 'ERROR', 'payload': f'Gemini stream interrupted: {str(e)[:100]}'})}\n\n"
                    return

                yield f"data: {json.dumps({'agent': 'System', 'status': 'WARNING', 'payload': 'Gemini stream failed. Falling back to Claude...'})}\n\n"
                try:
                    async for text in stream_claude():
                        yield f"data: {json.dumps({'agent': 'Claude', 'status': 'STREAMING', 'payload': text})}\n\n"
                except Exception as ex:
                    yield f"data: {json.dumps({'agent': 'System', 'status': 'ERROR', 'payload': f'All streams failed: {str(ex)[:100]}'})}\n\n"

        yield f"data: {json.dumps({'agent': 'System', 'status': 'COMPLETE', 'payload': 'Cognitive stream terminated.'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
