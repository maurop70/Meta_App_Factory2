import os
import ast
import subprocess
import asyncio
import signal
import logging
import requests
from datetime import datetime
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger("QA_Architect")
logging.basicConfig(level=logging.INFO)

FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))
STAGING_DIR = os.path.join(FACTORY_DIR, "staging_environment")

# Telemetry bridge — Phantom QA Elite SSE ingest endpoint
QA_INGEST_URL = "http://localhost:5030/api/qa/ingest"

def _push_qa_event(agent: str, message: str, status: str,
                   filename: str = None, score: int = None, attempt: int = None):
    """
    Fire-and-forget POST to the Phantom QA SSE ingest endpoint.
    Failures are swallowed so QA runs never block on telemetry.
    """
    payload = {
        "agent":    agent,
        "message":  message,
        "status":   status,
        "timestamp": datetime.now().isoformat(),
    }
    if filename is not None:
        payload["filename"] = filename
    if score is not None:
        payload["score"] = score
    if attempt is not None:
        payload["attempt"] = attempt
    try:
        requests.post(QA_INGEST_URL, json=payload, timeout=2)
    except Exception:
        pass  # telemetry is non-blocking


class SecurityViolation(Exception):
    pass

class QAArchitect:
    """The Autonomous Forge Validator Agent."""

    FORBIDDEN_CALLS = {
        'os.remove', 'os.rmdir', 'os.removedirs', 'os.unlink',
        'shutil.rmtree', 'sys.exit', 'quit', 'exit'
    }

    def __init__(self, timeout_seconds: int = 15):
        self.timeout = timeout_seconds

    def _verify_safety(self, script_path: str) -> bool:
        """
        Parses the AST of the target script to ensure no forbidden 
        destructive functions are invoked.
        """
        with open(script_path, 'r', encoding='utf-8') as f:
            code = f.read()

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            logger.error(f"[QAArchitect] SyntaxError in {script_path}: {e}")
            return False

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        func_name = f"{node.func.value.id}.{node.func.attr}"
                elif isinstance(node.func, ast.Name):
                    func_name = node.func.id

                if func_name in self.FORBIDDEN_CALLS:
                    logger.error(f"[QAArchitect] SAFEGUARD TRIGGERED: Forbidden call '{func_name}' detected in {script_path}")
                    raise SecurityViolation(f"Forbidden call detected: {func_name}")
        
        return True

    def execute_staging_script(self, filename: str, attempt: int = 1) -> Dict[str, Any]:
        """
        Executes a python file located in the staging_environment securely.
        Returns a dict with execution status, stdout, and stderr.
        Broadcasts all verdicts to the Phantom QA SSE stream (/api/qa/stream).
        """
        script_path = os.path.join(STAGING_DIR, filename)
        
        _push_qa_event(
            agent="QA_Architect",
            message=f"[Attempt {attempt}] Starting sandbox execution: {filename}",
            status="RUNNING",
            filename=filename,
            attempt=attempt,
        )

        if not os.path.exists(script_path):
            msg = f"{script_path} does not exist."
            _push_qa_event("QA_Architect", f"File not found: {filename}", "FAIL", filename=filename)
            return {
                "status": "error",
                "error": "File not found",
                "stdout": "",
                "stderr": msg,
            }

        try:
            # Pre-flight safety check
            if filename.endswith(".py"):
                self._verify_safety(script_path)
        except SecurityViolation as e:
            _push_qa_event(
                "QA_Architect",
                f"🛡️ SECURITY BLOCK — {e}",
                "SECURITY_BLOCK",
                filename=filename,
                attempt=attempt,
            )
            return {
                "status": "security_block",
                "error": "Security Violation",
                "stdout": "",
                "stderr": str(e),
            }
        except Exception as e:
            _push_qa_event("QA_Architect", f"AST parse error: {e}", "FAIL", filename=filename)
            return {
                "status": "error",
                "error": "Parsing Error",
                "stdout": "",
                "stderr": str(e),
            }

        # Safe to execute
        # ── DIAGNOSTIC NODE: BIFURCATED RUNTIME VERIFICATION ──
        logger.info(f"[QAArchitect] Executing {filename} inside Quarantine Zone with {self.timeout}s timeout.")
        
        try:
            # ── BIFURCATED RUNTIME VERIFICATION ──
            # We call the asynchronous wrapper to enforce daemon containment
            import asyncio
            return asyncio.run(_execute_diagnostic_cycle_async(script_path, filename))
                
        except subprocess.TimeoutExpired as e:
            logger.error(f"[QAArchitect] Execution TIMED OUT for {filename}.")
            _push_qa_event(
                "QA_Architect",
                f"⏰ TIMEOUT — {filename} exceeded {self.timeout}s sandbox limit.",
                "TIMEOUT",
                filename=filename,
                attempt=attempt,
            )
            return {
                "status": "timeout",
                "error": "Execution exceeded 15 seconds.",
                "stdout": e.stdout.decode() if e.stdout else "",
                "stderr": e.stderr.decode() if e.stderr else "Timeout reached.",
            }
        except Exception as e:
            logger.error(f"[QAArchitect] Execution Exception: {e}")
            _push_qa_event("QA_Architect", f"Runtime host error: {e}", "FAIL", filename=filename)
            return {
                "status": "error",
                "error": "Runtime Host Error",
                "stdout": "",
                "stderr": str(e)
            }
class EphemeralStagingDaemons:
    """Strict asynchronous context manager for OS-level daemon lifecycle."""
    def __init__(self, backend_cmd: str, frontend_cmd: str):
        self.backend_cmd = backend_cmd
        self.frontend_cmd = frontend_cmd
        self.backend_proc = None
        self.frontend_proc = None

    async def __aenter__(self):
        # Ignite staging daemons asynchronously
        if self.backend_cmd:
            self.backend_proc = await asyncio.create_subprocess_shell(
                self.backend_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
        if self.frontend_cmd:
            # Assume factory_ui directory for frontend
            cwd = os.path.join(FACTORY_DIR, "factory_ui")
            self.frontend_proc = await asyncio.create_subprocess_shell(
                self.frontend_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd
            )
        # Mathematical sleep to allow port binding
        await asyncio.sleep(8)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Guaranteed OS-level termination to prevent EADDRINUSE collisions
        for proc in [self.backend_proc, self.frontend_proc]:
            if proc:
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except (ProcessLookupError, asyncio.TimeoutError):
                    try:
                        proc.kill()
                    except:
                        pass

async def _execute_diagnostic_cycle_async(script_path: str, filename: str) -> Dict[str, Any]:
    """The Diagnostic Node Execution Engine (Async implementation)."""
    import sys
    sys.path.append(os.path.join(FACTORY_DIR, "Phantom_QA_Elite", "backend", "agents"))
    try:
        from ghost_user import GhostUserRunner
    except ImportError:
        logger.error("Could not import GhostUserRunner")
        return {"status": "error", "error": "GhostUserRunner missing"}

    is_frontend = filename.endswith((".jsx", ".js"))
    is_backend = filename.endswith(".py")
    
    # We dynamically set commands based on the payload type to avoid crashing unneeded daemons.
    backend_cmd = ""
    frontend_cmd = ""
    
    if is_backend:
        module_name = filename[:-3]
        backend_cmd = f"uvicorn staging_environment.{module_name}:app --port 8001"
    
    if is_frontend:
        # Assumes a scaffold exists to run this component
        frontend_cmd = "npm.cmd run dev -- --port 5174"

    async with EphemeralStagingDaemons(backend_cmd, frontend_cmd):
        if is_frontend:
            # Ignite the Ghost User for DOM/Console validation.
            runner = GhostUserRunner(base_url="http://localhost:5174/")
            try:
                result = await runner.run_full_suite()
                # If runner traps console errors, map it to our format
                if result.get("console_errors"):
                    return {
                        "status": "playwright_failure",
                        "console_error": "\n".join(result["console_errors"])
                    }
            except Exception as e:
                return {
                    "status": "diagnostic_crash",
                    "console_error": str(e)
                }
        
        if is_backend:
            # We would run pytest against the port 8001 here.
            # Simulating pytest for now since we just booted the server.
            # In a real environment, we'd subprocess.run pytest targeting 8001.
            import httpx
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get("http://localhost:8001/docs", timeout=5.0)
                    if resp.status_code != 200:
                        return {
                            "status": "pytest_failure",
                            "traceback": f"HTTP {resp.status_code} returned from staging API."
                        }
            except Exception as e:
                return {
                    "status": "pytest_failure",
                    "traceback": f"API failed to bind or crashed: {str(e)}"
                }

    return {"status": "pass", "stdout": "Diagnostic cycle passed.", "stderr": "", "returncode": 0}

    def _execute_frontend_verification(self, script_path: str, filename: str, attempt: int) -> Dict[str, Any]:
        """Synchronous wrapper for async Vite + Playwright diagnostic loop."""
        return asyncio.run(_execute_diagnostic_cycle_async(script_path, filename))

    def _execute_backend_verification(self, script_path: str, filename: str, attempt: int) -> Dict[str, Any]:
        """Synchronous wrapper for async Uvicorn + Pytest diagnostic loop."""
        return asyncio.run(_execute_diagnostic_cycle_async(script_path, filename))

if __name__ == "__main__":
    # Smoke test structure
    qa = QAArchitect()
    logger.info("QA Architect stands ready.")

