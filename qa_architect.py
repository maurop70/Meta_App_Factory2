import os
import ast
import subprocess
import logging
from typing import Dict, Any

logger = logging.getLogger("QA_Architect")
logging.basicConfig(level=logging.INFO)

FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))
STAGING_DIR = os.path.join(FACTORY_DIR, "staging_environment")

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

    def execute_staging_script(self, filename: str) -> Dict[str, Any]:
        """
        Executes a python file located in the staging_environment securely.
        Returns a dict with execution status, stdout, and stderr.
        """
        script_path = os.path.join(STAGING_DIR, filename)
        
        if not os.path.exists(script_path):
            return {
                "status": "error",
                "error": "File not found",
                "stdout": "",
                "stderr": f"{script_path} does not exist."
            }

        try:
            # Pre-flight safety check
            self._verify_safety(script_path)
        except SecurityViolation as e:
            return {
                "status": "security_block",
                "error": "Security Violation",
                "stdout": "",
                "stderr": str(e)
            }
        except Exception as e:
            return {
                "status": "error",
                "error": "Parsing Error",
                "stdout": "",
                "stderr": str(e)
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
                return {
                    "status": "pass",
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "returncode": 0
                }
            else:
                logger.warning(f"[QAArchitect] {filename} execution FAILED (return code {process.returncode}).")
                return {
                    "status": "fail",
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "returncode": process.returncode
                }
                
        except subprocess.TimeoutExpired as e:
            logger.error(f"[QAArchitect] Execution TIMED OUT for {filename}.")
            return {
                "status": "timeout",
                "error": "Execution exceeded 15 seconds.",
                "stdout": e.stdout.decode() if e.stdout else "",
                "stderr": e.stderr.decode() if e.stderr else "Timeout reached."
            }
        except Exception as e:
            logger.error(f"[QAArchitect] Execution Exception: {e}")
            return {
                "status": "error",
                "error": "Runtime Host Error",
                "stdout": "",
                "stderr": str(e)
            }

if __name__ == "__main__":
    # Smoke test structure
    qa = QAArchitect()
    logger.info("QA Architect stands ready.")
