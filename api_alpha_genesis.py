import os
import sqlite3
import json
import logging
import uuid
from typing import List, Optional, Any, Dict
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Query, HTTPException, UploadFile, File

logger = logging.getLogger("AlphaV2Genesis")

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ALPHA_DATA_DIR = os.path.join(SCRIPT_DIR, "Alpha_V2_Genesis", "Alpha_Data")
os.makedirs(ALPHA_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(ALPHA_DATA_DIR, "alpha_v2_genesis.db")

router = APIRouter(prefix="/api/v2/alpha", tags=["Alpha V2 Genesis"])

# --- Database Initialization ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_role CHECK (role IN ('user', 'assistant', 'system'))
        );

        CREATE TABLE IF NOT EXISTS executions_ledger (
            id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            strategy TEXT NOT NULL,
            strikes TEXT,
            credit_debit REAL NOT NULL,
            expiration DATE,
            screenshot_path TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_action CHECK (action IN ('OPEN', 'CLOSE')),
            CONSTRAINT chk_credit_debit_format CHECK (typeof(credit_debit) IN ('real', 'integer'))
        );

        CREATE TABLE IF NOT EXISTS trade_journal (
            trade_id TEXT PRIMARY KEY,
            strategy TEXT NOT NULL,
            entry_date DATE NOT NULL,
            close_date DATE,
            expiry DATE,
            credit_received REAL DEFAULT 0,
            close_mark REAL DEFAULT 0,
            realized_pnl REAL DEFAULT 0,
            realized_pnl_pct REAL DEFAULT 0,
            days_held INTEGER DEFAULT 0,
            entry_rating TEXT NOT NULL,
            entry_score INTEGER DEFAULT 0,
            closes_at DATETIME,
            CONSTRAINT chk_entry_rating CHECK (entry_rating IN ('OPEN', 'CLOSED'))
        );

        CREATE TABLE IF NOT EXISTS system_jobs_queue (
            job_id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL,
            payload TEXT,
            result TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_status CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'))
        );
    """)
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sweep_zombie_jobs():
    """Phase 1: Physically sweeps and terminates abandoned zombie tasks on engine boot."""
    logger.info("[AlphaV2Genesis] Executing Zombie Job Eradication Sweep...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE system_jobs_queue SET status = 'FAILED', "
            "result = '{\"error\": \"Zombie task terminated by engine restart\"}' "
            "WHERE status = 'PROCESSING'"
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        logger.info(f"[AlphaV2Genesis] Zombie sweep complete. {affected} zombie task(s) terminated.")
    except Exception as e:
        logger.error(f"[AlphaV2Genesis] Zombie sweep failed: {e}")

# --- Pydantic Models for unified I/O ---
from pydantic import BaseModel

class PaginatedResponse(BaseModel):
    items: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int

class ExecutionMetadata(BaseModel):
    ticker: str
    action: str
    strategy: str
    credit_debit: float
    strikes: Optional[str] = None
    expiration: Optional[str] = None

class RefreshRequest(BaseModel):
    force: bool = False

# --- Background Worker Functions ---
def async_ledger_refresh(force: bool):
    """Background worker for blocking ledger calculation."""
    logger.info(f"Started background ledger refresh. Force={force}")
    # Simulation of CPU bound operation
    import time
    time.sleep(2)
    logger.info("Completed background ledger refresh.")

def async_execution_processing(job_id: str, metadata: dict, filepath: str):
    """Background worker to insert execution metadata and sync portfolios."""
    logger.info(f"Started processing execution upload job {job_id}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO executions_ledger (id, ticker, action, strategy, strikes, credit_debit, expiration, screenshot_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                metadata.get("ticker", "UNKNOWN"),
                metadata.get("action", "OPEN"),
                metadata.get("strategy", "UNKNOWN"),
                metadata.get("strikes"),
                float(metadata.get("credit_debit", 0.0)),
                metadata.get("expiration"),
                filepath
            )
        )
        conn.commit()
        conn.close()
        logger.info(f"Execution {job_id} successfully persisted to SQLite.")
    except Exception as e:
        logger.error(f"Failed to process execution job {job_id}: {e}")

def async_ocr_processing(job_id: str, filepath: str):
    """Background worker executing durable row lock and Gemini OCR dispatch."""
    logger.info(f"[AlphaV2Genesis] OCR job {job_id} PROCESSING on {filepath}")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Acquire row lock: only transition from PENDING — prevents double-processing
        cursor.execute(
            "UPDATE system_jobs_queue SET status = 'PROCESSING' "
            "WHERE job_id = ? AND status = 'PENDING'",
            (job_id,)
        )
        conn.commit()

        # --- Gemini OCR Dispatch would execute here ---
        import time
        time.sleep(5)  # Placeholder: replace with live Gemini Vision API call
        result_payload = json.dumps({"status": "success", "job_id": job_id})

        cursor.execute(
            "UPDATE system_jobs_queue SET status = 'COMPLETED', result = ? WHERE job_id = ?",
            (result_payload, job_id)
        )
        logger.info(f"[AlphaV2Genesis] OCR job {job_id} COMPLETED.")
    except Exception as e:
        logger.error(f"[AlphaV2Genesis] OCR job {job_id} FAILED: {e}")
        cursor.execute(
            "UPDATE system_jobs_queue SET status = 'FAILED', result = ? WHERE job_id = ?",
            (json.dumps({"error": str(e)}), job_id)
        )
    finally:
        conn.commit()
        conn.close()

# --- Endpoints ---

@router.get("/health")
def health_check():
    """V2 Native Health Check"""
    return {"status": "ok", "message": "Alpha V2 Genesis Native Router Online"}

@router.get("/fragility")
def get_fragility():
    """Native Fragility Index Computation"""
    return {"status": "ok", "fragility_index": 0, "overall_risk": "green"}

@router.get("/ledger")
def get_ledger():
    """Retrieves current ledger state. Non-paginated as it represents a singleton aggregate state."""
    return {"status": "ok", "last_run": datetime.utcnow().isoformat(), "positions": {}}

@router.post("/ledger/refresh")
def refresh_ledger(req: RefreshRequest, background_tasks: BackgroundTasks):
    """Trigger background recalculation of the strategy ledger."""
    background_tasks.add_task(async_ledger_refresh, req.force)
    return {"status": "accepted", "message": "Ledger refresh dispatched to background worker."}

@router.get("/journal", response_model=PaginatedResponse)
def get_journal(limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0)):
    """Paginated Trade Journal."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as total FROM trade_journal")
    total = cursor.fetchone()["total"]
    
    cursor.execute("SELECT * FROM trade_journal ORDER BY entry_date DESC LIMIT ? OFFSET ?", (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    
    items = [dict(row) for row in rows]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

@router.get("/executions", response_model=PaginatedResponse)
def get_executions(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    """Paginated Execution Ledger."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as total FROM executions_ledger")
    total = cursor.fetchone()["total"]
    
    cursor.execute("SELECT * FROM executions_ledger ORDER BY timestamp DESC LIMIT ? OFFSET ?", (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    
    items = [dict(row) for row in rows]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

@router.delete("/executions/{execution_id}")
def delete_execution(execution_id: str):
    """Delete specific execution."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM executions_ledger WHERE id = ?", (execution_id,))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Execution not found.")
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Execution {execution_id} deleted."}


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """Stateless polling endpoint. Queries exclusively from SQLite for multi-worker compliance."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status, result, task_type, created_at FROM system_jobs_queue WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return {
        "job_id": job_id,
        "task_type": row["task_type"],
        "status": row["status"],
        "created_at": row["created_at"],
        "result": json.loads(row["result"]) if row["result"] else None,
    }

@router.post("/executions/upload")
def upload_execution(
    background_tasks: BackgroundTasks,
    screenshot: Optional[UploadFile] = File(None),
    metadata: str = Query(...)
):
    """Decoupled File Ingestion."""
    import uuid
    import aiofiles
    job_id = str(uuid.uuid4())
    filepath = ""
    
    try:
        meta_dict = json.loads(metadata)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in metadata parameter.")
        
    if screenshot:
        filepath = os.path.join(ALPHA_DATA_DIR, f"{job_id}_{screenshot.filename}")
        # In a real async handler we would await reading and writing,
        # but for simplicity in this endpoint we read synchronously or let aiofiles handle it.
        # It's better to read the spool natively if small, or defer to BackgroundTask if large.
        with open(filepath, "wb") as f:
            f.write(screenshot.file.read())
            
    background_tasks.add_task(async_execution_processing, job_id, meta_dict, filepath)
    return {"status": "accepted", "job_id": job_id, "message": "Upload queued for asynchronous processing."}

@router.post("/executions/ocr")
def ocr_execution(background_tasks: BackgroundTasks, screenshot: UploadFile = File(...)):
    """Decoupled OCR LLM Processing. Inserts PENDING job row before dispatching worker."""
    job_id = str(uuid.uuid4())
    filepath = os.path.join(ALPHA_DATA_DIR, f"ocr_{job_id}_{screenshot.filename}")

    with open(filepath, "wb") as f:
        f.write(screenshot.file.read())

    # PRE-FLIGHT: Synchronously INSERT job into durable queue before 202 response
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO system_jobs_queue (job_id, task_type, status, payload) VALUES (?, ?, ?, ?)",
        (job_id, "OCR_EXTRACTION", "PENDING", json.dumps({"filepath": filepath}))
    )
    conn.commit()
    conn.close()
    logger.info(f"[AlphaV2Genesis] OCR job {job_id} inserted as PENDING.")

    background_tasks.add_task(async_ocr_processing, job_id, filepath)
    return {
        "status": "accepted",
        "job_id": job_id,
        "poll_url": f"/api/v2/alpha/jobs/{job_id}",
        "message": "OCR job inserted as PENDING and dispatched to LLM workers.",
    }
