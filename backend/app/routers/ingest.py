from fastapi import APIRouter, UploadFile, File, HTTPException
import aiofiles
import os
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
    
    MAX_SIZE_BYTES = 50 * 1024 * 1024  # 50MB Cap
    bytes_written = 0

    try:
        async with aiofiles.open(file_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > MAX_SIZE_BYTES:
                    # Clean up partial file on threshold breach
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="Payload Too Large: Max file size is 50MB")
                await buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await file.close()
        
    return {
        "status": "STAGED",
        "document_id": safe_filename,
        "original_name": file.filename,
        "path": str(file_path),
        "size_bytes": file_path.stat().st_size
    }
