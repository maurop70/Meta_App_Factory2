from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import shutil
import uuid
from pathlib import Path

router = APIRouter(prefix="/api/ingest", tags=["Ingestion"])

# Absolute path resolution to the staging vault
BASE_DIR = Path.cwd()
STAGING_VAULT = BASE_DIR / "vault" / "staging"
STAGING_VAULT.mkdir(parents=True, exist_ok=True)

# Strict extension validation matrix
ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".csv", ".docx", ".txt", ".md", ".json"}

@router.post("/document")
async def ingest_document(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported media type. Allowed: {ALLOWED_EXTENSIONS}")
    
    # Generate unique cryptographic ID to prevent naming collisions
    safe_id = str(uuid.uuid4())[:8]
    safe_filename = f"{safe_id}_{file.filename}"
    file_path = STAGING_VAULT / safe_filename
    
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vault write fracture: {str(e)}")
    finally:
        file.file.close()
        
    return {
        "status": "STAGED",
        "document_id": safe_filename,
        "original_name": file.filename,
        "path": str(file_path),
        "size_bytes": file_path.stat().st_size
    }
