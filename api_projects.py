import os
import uuid
import json
import sqlite3
import logging
from datetime import datetime
from contextlib import closing
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional

logger = logging.getLogger("projects_router")
projects_router = APIRouter(prefix="/api/projects", tags=["Project Workspaces"])

DB_PATH = os.path.join(os.path.dirname(__file__), "factory_state.db")

def init_projects_db():
    """Verify that the project_workspaces table is physically injected into the factory database."""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_workspaces (
                id                  TEXT PRIMARY KEY,
                project_name        TEXT UNIQUE NOT NULL,
                financial_matrix    TEXT NOT NULL,
                operational_context TEXT NOT NULL,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            )
        """)
        conn.commit()
    logger.info(f"[ProjectsDB] project_workspaces table verified in {DB_PATH}")

# Physically run schema migration on load
init_projects_db()

# ── PYDANTIC SCHEMAS ──
class ProjectCreate(BaseModel):
    project_name: str
    financial_matrix: dict
    operational_context: dict

class ProjectUpdate(BaseModel):
    financial_matrix: Optional[dict] = None
    operational_context: Optional[dict] = None

# ── ROUTES ──

@projects_router.post("/")
async def create_project(payload: ProjectCreate):
    """POST /api/projects/: Ingest workspace payload and commit to SQLite."""
    project_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    try:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            conn.execute(
                """
                INSERT INTO project_workspaces 
                (id, project_name, financial_matrix, operational_context, created_at, updated_at) 
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    payload.project_name,
                    json.dumps(payload.financial_matrix),
                    json.dumps(payload.operational_context),
                    now,
                    now
                )
            )
            conn.commit()
        return {"status": "success", "id": project_id}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail=f"Project workspace '{payload.project_name}' already exists.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@projects_router.get("/")
async def list_projects(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """GET /api/projects/: Retrieve paginated collections under Unified I/O doctrine."""
    try:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            # Count total for the collection envelope
            total = conn.execute("SELECT count(*) FROM project_workspaces").fetchone()[0]
            
            # Fetch paginated list
            rows = conn.execute(
                "SELECT id, project_name, financial_matrix, operational_context, created_at, updated_at "
                "FROM project_workspaces ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            
        items = []
        for r in rows:
            items.append({
                "id": r[0],
                "project_name": r[1],
                "financial_matrix": json.loads(r[2]),
                "operational_context": json.loads(r[3]),
                "created_at": r[4],
                "updated_at": r[5]
            })
            
        # Natively enforce UNIFIED I/O SERIALIZATION ENVELOPE doctrine
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@projects_router.patch("/{project_id}/")
async def update_project(project_id: str, payload: ProjectUpdate):
    """PATCH /api/projects/{project_id}/: Update financial/operational JSON context."""
    now = datetime.utcnow().isoformat()
    try:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            # Check existence
            row = conn.execute("SELECT id FROM project_workspaces WHERE id = ?", (project_id,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Project workspace not found.")
                
            updates = []
            params = []
            if payload.financial_matrix is not None:
                updates.append("financial_matrix = ?")
                params.append(json.dumps(payload.financial_matrix))
            if payload.operational_context is not None:
                updates.append("operational_context = ?")
                params.append(json.dumps(payload.operational_context))
                
            if not updates:
                raise HTTPException(status_code=400, detail="No fields provided for update.")
                
            updates.append("updated_at = ?")
            params.append(now)
            
            query = f"UPDATE project_workspaces SET {', '.join(updates)} WHERE id = ?"
            params.append(project_id)
            
            conn.execute(query, tuple(params))
            conn.commit()
            
        return {"status": "success", "id": project_id}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@projects_router.post("/open-folder")
@projects_router.post("/open-folder/")
async def open_project_folder(payload: dict):
    """POST /api/projects/open-folder: Open Windows Explorer directly at the project workspace directory."""
    project = payload.get("project_name")
    if not project:
        raise HTTPException(status_code=400, detail="Project name required")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    pdir = os.path.join(base_dir, "projects", project)
    if os.path.isdir(pdir):
        try:
            import subprocess
            subprocess.Popen(f'explorer "{os.path.normpath(pdir)}"')
            return {"status": "ok", "message": f"Explorer opened for {project}"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=404, detail=f"Project workspace folder '{project}' does not exist on disk.")

