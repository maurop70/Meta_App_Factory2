import os
import re
import sys
import json
import httpx
import asyncio
import logging
import aiofiles
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
orchestrator_router = APIRouter(prefix="/api/v1/qa/orchestrator", tags=["QA Orchestrator"])

FACTORY_ROOT = Path(os.getcwd()).resolve()
TEST_DIR = FACTORY_ROOT / "__tests__"

def _extract_failure_cause(trace: str) -> str:
    lines = [line.strip() for line in trace.splitlines() if line.strip()]
    if not lines:
        return "Unknown failure"
    for line in reversed(lines):
        if line.startswith("E ") or line.startswith("E\t"):
            return line.lstrip("E \t")
    return lines[-1]

async def _deduce_culprit_matrix(trace: str, target_url: str, app_name: str) -> str:
    """
    The Diagnostic Architect. 
    Maps a compiled DOM/Network failure back to a physical source file path via AST scanning.
    """

    import ast
    import glob
    import traceback
    from pathlib import Path

    try:
        # First, attempt to extract the failed route or function from the trace
        # This is a basic heuristic; a real trace would need more complex parsing
        failed_route = None
        for line in trace.splitlines():
            if "FAILED" in line and ("/" in line or "test_" in line):
                failed_route = line.split()[-1] # Grabbing the last word might be a route
                break
                
        # Define target directory heuristically (this would normally come from the payload)
        target_dir = os.path.join(FACTORY_ROOT, app_name) if app_name and app_name != "Auto-detect" else str(FACTORY_ROOT)
        
        # Reverse Route Lookup & Entry-Point Fallback Scanner
        entry_point = None
        
        # Scan all .py files in the target directory
        for py_file in Path(target_dir).rglob("*.py"):
            py_file_str = str(py_file)
            if "__tests__" in py_file_str or "site-packages" in py_file_str:
                continue
                
            try:
                with open(py_file_str, 'r', encoding='utf-8', errors='ignore') as f:
                    code = f.read()
                
                # Check for specific route if we deduced one (string search fallback)
                if failed_route and failed_route in code:
                    return os.path.relpath(py_file_str, FACTORY_ROOT).replace("\\", "/")

                # Prioritize files that actually run the server
                if "uvicorn.run(" in code:
                    entry_point = os.path.relpath(py_file_str, FACTORY_ROOT).replace("\\", "/")
                    break # We found the primary runner

                tree = ast.parse(code)
                
                # Check for FastAPI engine instantiation
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id == 'app':
                                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == 'FastAPI':
                                    if not entry_point:
                                        entry_point = os.path.relpath(py_file_str, FACTORY_ROOT).replace("\\", "/")

            except Exception as e:
                logger.error(f"[DIAGNOSTIC] AST scan failed on {py_file_str}: {e}")

        if entry_point:
             return entry_point

    except Exception as e:
        logger.error(f"[DIAGNOSTIC] File deduction fractured: {traceback.format_exc()}")
        
    return "Unknown/Manual Selection Required"

class OrchestrationPayload(BaseModel):
    target_url: str
    app_name: str = "Auto-detect"

@orchestrator_router.post("/execute")
async def execute_autonomous_qa_loop(payload: OrchestrationPayload):
    """
    Mode C Master Controller.
    Cognitively generates, physically writes, and dynamically executes E2E Playwright tests in a single loop.
    """
    logger.info(f"[QA ORCHESTRATOR] Igniting autonomous sequence for: {payload.target_url}")
    
    # PHASE 1: COGNITIVE SYNTHESIS (The QA Architect)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY missing from environment matrix.")

    system_prompt = (
        "You are the Mode C QA Architect. Your sole priority is generating deterministic Playwright E2E tests. "
        "Output ONLY the raw Python `pytest-playwright` code. Do not use markdown formatting or explanations. "
        "The test MUST navigate to the provided TARGET URL, assert basic DOM rendering, and check for fatal HTTP/console errors. "
        "The test MUST be named `test_auto_ghost` internally.\n"
        "Doctrine Rules for MWO ERP:\n"
        "- The app login route is strictly `/login` (not `/Login Page` or `/dm/login`).\n"
        "- The login fields are `#mwo_operator_id` (Employee ID) and `#mwo_operator_pin` (PIN).\n"
        "- The submit button is clicked using `.erp-submit-btn` class or selector `button[type='submit']` (do not look for a button with text 'Login')."
    )
    user_prompt = f"TARGET URL: {payload.target_url}\nAPP NAME: {payload.app_name}\nSynthesize the strict pytest-playwright validation script."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    gemini_payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.1}
    }

    # Fallback template (legacy CLO_Agent fuzz test) — used only if live
    # Gemini synthesis fails.
    fallback_code = f"""import os
import time
import requests
import traceback
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import Playwright

def test_auto_ghost(playwright: Playwright):
    start_time = time.time()
    
    # Load .env dynamically
    for p in [Path(__file__).parent, Path(__file__).parent.parent, Path(__file__).parent.parent.parent]:
        env_file = p / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break

    target_url = os.environ.get("CLO_AGENT_URL", "{payload.target_url}")
    qa_backend = os.environ.get("PHANTOM_QA_BACKEND")
    if not qa_backend:
        qa_port = os.environ.get("PHANTOM_QA_PORT", "5030")
        qa_backend = f"http://127.0.0.1:{{qa_port}}"

    verdict = "FAIL"
    score = 0
    resp_json = {{}}
    request_context = None

    try:
        # 1. Forcefully poll CLO_Agent health natively until an HTTP 200 is confirmed
        health_url = f"{{target_url}}/api/health"
        service_online = False
        
        for _ in range(30):
            try:
                response = requests.get(health_url, timeout=2.0)
                if response.status_code == 200 and response.json().get("status") == "online":
                    service_online = True
                    break
            except Exception:
                pass
            time.sleep(1.0)
            
        assert service_online, f"CLO_Agent's internal /api/health did not return online at {{health_url}}"

        # 2. Execute a localized API fuzzing payload directly against the agent's ingestion routers
        request_context = playwright.request.new_context(base_url=target_url)
        
        payload = {{
            "template_name": "non_existent_template_fuzz",
            "data": {{"key": "value"}},
            "output_filename": "fuzz_output.txt"
        }}
        
        response = request_context.post("/api/legal/analyze", data=payload)
        
        # Assert raw ASGI response envelope strictly matches the UNIFIED I/O SERIALIZATION ENVELOPE doctrine
        assert response.status in [200, 500]
        resp_json = response.json()
        
        if response.status == 200:
            assert resp_json.get("status") == "success"
            assert "output_path" in resp_json
        else:
            assert "detail" in resp_json or "error" in resp_json

        verdict = "PASS"
        score = 100

    except Exception as e:
        verdict = "FAIL"
        score = 0
        resp_json = {{
            "status": "FAIL",
            "error": str(e),
            "traceback": traceback.format_exc()
        }}
        raise e

    finally:
        try:
            duration = round(time.time() - start_time, 2)
            report_payload = {{
                "app_name": "CLO_Agent",
                "app_url": target_url,
                "verdict": verdict,
                "score": score,
                "duration": duration,
                "report_data": {{
                    "verdict": verdict,
                    "score": score,
                    "duration": duration,
                    "response": resp_json
                }}
            }}
            requests.post(f"{{qa_backend}}/api/reports", json=report_payload, timeout=5.0)
        except Exception as post_err:
            print(f"Failed to post E2E telemetry: {{post_err}}")
            
        if request_context:
            request_context.dispose()
"""

    # PHASE 1 (live): synthesize the test via Gemini; fall back to the
    # legacy template only if the API interaction fails.
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=gemini_payload)
            response.raise_for_status()
            resp_json = response.json()
            raw_code = resp_json['candidates'][0]['content']['parts'][0]['text']

        # Strip markdown fences if the model wrapped the code
        raw_code = raw_code.strip()
        if raw_code.startswith("```"):
            raw_code = raw_code.split("\n", 1)[1] if "\n" in raw_code else ""
        if raw_code.rstrip().endswith("```"):
            raw_code = raw_code.rstrip()[: -len("```")]
        raw_code = raw_code.strip()
        if not raw_code:
            raise ValueError("Gemini returned empty test code")
        logger.info(f"[QA ORCHESTRATOR] Live Gemini synthesis succeeded ({len(raw_code)} chars).")
    except Exception as e:
        err_msg = str(e)
        if "key=" in err_msg:
            err_msg = re.sub(r'key=[^&\s\'"]+', 'key=MASKED', err_msg)
        logger.error(f"[QA ORCHESTRATOR] Cognitive Fracture: {err_msg} — falling back to hardcoded CLO_Agent template.")
        raw_code = fallback_code.strip()

    # PHASE 2: ZERO-TRUST WRITE (The Atomizer Bridge)
    TEST_DIR.mkdir(exist_ok=True)
    test_path = TEST_DIR / "test_auto_ghost.py"
    
    try:
        # Strict adherence to async I/O doctrine
        async with aiofiles.open(test_path, 'w') as f:
            await f.write(raw_code)
        logger.info(f"[QA ORCHESTRATOR] Matrix mutated. Payload written to {test_path.name}.")
    except Exception as e:
        logger.error(f"[QA ORCHESTRATOR] I/O Fracture: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to mutate physical disk.")

    # PHASE 3: THE INTERROGATION (Dynamic Execution)
    try:
        # Incorporating your biological override for Windows PATH resolution
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pytest", str(test_path), "--browser", "chromium",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        raw_output = stdout.decode('utf-8')
        raw_error = stderr.decode('utf-8')
        
        status = "PASSED" if process.returncode == 0 else "FAILED"
        failure_cause = _extract_failure_cause(raw_output) if status == "FAILED" else ""
        
        # New Cognitive Injection: Deduce the file ONLY if the test fails
        culprit_file = ""
        if status == "FAILED":
            logger.info("[QA ORCHESTRATOR] Interrogation failed. Igniting Diagnostic Architect to map file...")
            culprit_file = await _deduce_culprit_matrix(raw_output, payload.target_url, payload.app_name)
        
        return {
            "status": status,
            "target_url": payload.target_url,
            "trace": raw_output,
            "cause": failure_cause,
            "culprit_file": culprit_file,
            "error": raw_error
        }
    except Exception as e:
        logger.error(f"[QA ORCHESTRATOR] Subprocess Fatal Exception: {str(e)}")
        raise HTTPException(status_code=500, detail="Playwright subprocess catastrophically failed.")
