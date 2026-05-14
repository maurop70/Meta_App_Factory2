import os
import logging
import httpx
from pathlib import Path
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from api_phantom_qa import perform_pre_flight_audit, PreflightPayload
logger = logging.getLogger(__name__)
atomizer_router = APIRouter(prefix="/api/v1/atomizer", tags=["Atomizer Bridge"])

# --- THE ZERO-TRUST EXECUTION JAIL ---
# All autonomous file operations MUST mathematically resolve within this directory boundary.
FACTORY_ROOT = Path(os.getcwd()).resolve()

class MutatePayload(BaseModel):
    relative_path: str
    content: str

def _enforce_path_jail(target_path: str) -> Path:
    """
    Mathematical verification against path-traversal injections.
    Forces all relative paths to resolve absolutely against the FACTORY_ROOT.
    """
    physical_path = (FACTORY_ROOT / target_path).resolve()
    
    # If the resolved path escapes the factory boundary, physically halt execution.
    if not str(physical_path).startswith(str(FACTORY_ROOT)):
        logger.error(f"[SECURITY FATAL] Agent path traversal blocked: {target_path}")
        raise HTTPException(status_code=403, detail="Zero-Trust Violation: Path Traversal Blocked.")
        
    return physical_path

@atomizer_router.get("/read")
async def read_target_matrix(target_path: str):
    """
    Autonomous endpoint for the Architect to ingest child app ASTs.
    """
    safe_path = _enforce_path_jail(target_path)
    if not safe_path.exists() or not safe_path.is_file():
        raise HTTPException(status_code=404, detail="Target matrix not found on physical disk.")
    
    try:
        with open(safe_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"status": "SUCCESS", "target": str(safe_path), "content": content}
    except Exception as e:
        logger.error(f"Atomizer Read Fracture: {str(e)}")
        raise HTTPException(status_code=500, detail="I/O Read Exception.")

@atomizer_router.post("/mutate")
async def mutate_target_matrix(payload: MutatePayload):
    """
    Autonomous endpoint for the Executor to write sub-atomic mutations to the disk.
    Strictly enforced by Phantom QA.
    """
    # --- TIER 1 COGNITIVE AUDITOR INTERCEPTION ---
    try:
        async with httpx.AsyncClient() as client:
            audit_response = await client.post(
                "http://127.0.0.1:5050/audit",
                json={
                    "target_file": payload.relative_path,
                    "proposed_ast": payload.content
                },
                timeout=10.0
            )
            if audit_response.status_code == 200:
                audit_result = audit_response.json()
                if audit_result.get("status") == "REJECTED":
                    logger.error(f"[SECURITY FATAL] Atomizer mutation rejected by Tier 1 Cognitive Auditor for {payload.relative_path}.")
                    raise HTTPException(
                        status_code=406, 
                        detail=audit_result.get("architectural_feedback", "Rejected by Tier 1 Cognitive Auditor")
                    )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SECURITY FATAL] Tier 1 Cognitive Auditor offline/fractured: {e}")
        raise HTTPException(
            status_code=503, 
            detail=f"Tier 1 Shield Offline/Fractured: {e}"
        )

    # Phase 7: The Phantom QA Pre-Flight Interception Layer (Backend Enforcement)
    # Mathematically prevents ANY node or autonomous script from bypassing the SAST scanner.
    preflight_payload = PreflightPayload(content=payload.content, target_path=payload.relative_path)
    qa_result = await perform_pre_flight_audit(preflight_payload)
    
    if qa_result.get("status") == "REJECTED":
        logger.error(f"[SECURITY FATAL] Atomizer mutation rejected by Phantom QA for {payload.relative_path}.")
        raise HTTPException(status_code=403, detail=f"Phantom QA Violation: {qa_result.get('violations')}")

    safe_path = _enforce_path_jail(payload.relative_path)
    
    # Synthesize physical directory structures if they do not exist
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(payload.content)
        logger.info(f"[ATOMIZER] Autonomous mutation executed physically at {safe_path}")
        return {"status": "SUCCESS", "target": str(safe_path), "bytes_written": len(payload.content)}
    except Exception as e:
        logger.error(f"Atomizer Write Fracture: {str(e)}")
        raise HTTPException(status_code=500, detail="I/O Write Exception.")

@atomizer_router.get("/map")
async def generate_physical_map(target_directory: str = "apps"):
    """
    Synthesizes a JSON representation of the physical app directory.
    Strictly enforces the Zero-Trust boundary and excludes heavy bloat matrices.
    """
    safe_path = _enforce_path_jail(target_directory)

    if not safe_path.exists() or not safe_path.is_dir():
        raise HTTPException(status_code=404, detail="Target directory matrix void.")

    excluded_dirs = {"node_modules", ".git", "venv", "__pycache__", ".vite", "dist", "build"}

    def _build_tree(current_path: Path):
        tree = []
        try:
            # Sort directories first, then files for optimal UI rendering
            items = sorted(current_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            for item in items:
                if item.name in excluded_dirs:
                    continue
                if item.is_dir():
                    tree.append({
                        "name": item.name,
                        "type": "directory",
                        "path": str(item.relative_to(FACTORY_ROOT).as_posix()),
                        "children": _build_tree(item)
                    })
                elif item.is_file():
                    tree.append({
                        "name": item.name,
                        "type": "file",
                        "path": str(item.relative_to(FACTORY_ROOT).as_posix())
                    })
        except PermissionError:
            pass
        return tree

    logger.info(f"[ATOMIZER] Synthesizing physical map for {target_directory}...")
    return {"status": "SUCCESS", "directory": target_directory, "tree": _build_tree(safe_path)}
