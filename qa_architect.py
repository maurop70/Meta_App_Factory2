import os
import ast
import subprocess
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
        logger.info(f"[QAArchitect] Executing {filename} inside Quarantine Zone with {self.timeout}s timeout.")
        try:
            process = subprocess.run(
                ['python', script_path],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if process.returncode == 0:
                logger.info(f"[QAArchitect] {filename} executing PASS.")
                _push_qa_event(
                    "QA_Architect",
                    f"✅ PASS — {filename} executed cleanly (rc=0). Attempt {attempt}.",
                    "PASS",
                    filename=filename,
                    attempt=attempt,
                )
                return {
                    "status": "pass",
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "returncode": 0,
                }
            else:
                logger.warning(f"[QAArchitect] {filename} execution FAILED (return code {process.returncode}).")
                _push_qa_event(
                    "QA_Architect",
                    f"❌ FAIL — {filename} exited rc={process.returncode}. stderr: {process.stderr[:200]}",
                    "FAIL",
                    filename=filename,
                    attempt=attempt,
                )
                return {
                    "status": "fail",
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "returncode": process.returncode,
                }
                
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
                "stderr": str(e),
            }

if __name__ == "__main__":
    # Smoke test structure
    qa = QAArchitect()
    logger.info("QA Architect stands ready.")

