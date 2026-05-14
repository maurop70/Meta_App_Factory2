import sys
import os
import asyncio
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
playwright_router = APIRouter(prefix="/api/v1/playwright", tags=["Subprocess Interrogator"])

FACTORY_ROOT = Path(os.getcwd()).resolve()

class TestPayload(BaseModel):
    test_path: str

def _enforce_test_jail(target_path: str) -> Path:
    """
    Zero-Trust enforcement. Restricts execution entirely to the Factory root.
    """
    physical_path = (FACTORY_ROOT / target_path).resolve()
    if not str(physical_path).startswith(str(FACTORY_ROOT)):
        logger.error(f"[SECURITY FATAL] Playwright path traversal blocked: {target_path}")
        raise HTTPException(status_code=403, detail="Zero-Trust Violation: Path Traversal.")
    return physical_path

@playwright_router.post("/execute")
async def execute_playwright_interrogation(payload: TestPayload):
    """
    The Dynamic Execution Engine.
    Spawns a native OS subprocess to run Playwright without blocking the ASGI event loop.
    """
    safe_path = _enforce_test_jail(payload.test_path)
    
    if not safe_path.exists() or not safe_path.is_file():
        raise HTTPException(status_code=404, detail="Target test matrix not found on physical disk.")

    logger.info(f"[INTERROGATOR] Igniting Playwright subprocess for: {safe_path.name}")

    try:
        # Asynchronously spawning the pytest-playwright worker
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pytest", str(safe_path), "--browser", "chromium",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Multiplexing standard out and standard error without thread locks
        stdout, stderr = await process.communicate()
        
        raw_output = stdout.decode('utf-8')
        raw_error = stderr.decode('utf-8')
        
        if process.returncode == 0:
            logger.info(f"[INTERROGATOR] Execution PASSED for {safe_path.name}")
            return {"status": "PASSED", "trace": raw_output}
        else:
            logger.warning(f"[INTERROGATOR] Execution FRACTURED for {safe_path.name}")
            return {"status": "FAILED", "trace": raw_output, "error": raw_error}
            
    except Exception as e:
        logger.error(f"[INTERROGATOR] Subprocess Fatal Exception: {str(e)}")
        raise HTTPException(status_code=500, detail="Playwright subprocess catastrophically failed.")
