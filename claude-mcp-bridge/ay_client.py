import os
import json
import time
import random
import uuid
import warnings
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(Path(__file__).parent.parent / ".env")

MAF_ROOT = Path(__file__).parent.parent.resolve()
MAX_ITERATIONS = 5

BACKOFF_BASE_SECONDS = 2.0
BACKOFF_MAX_RETRIES = 5

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def _is_rate_limit_error(exc: Exception) -> bool:
    """True for HTTP 429 / quota exhaustion errors from the Gemini API."""
    if type(exc).__name__ in ("ResourceExhausted", "TooManyRequests"):
        return True
    if getattr(exc, "code", None) == 429 or getattr(exc, "status_code", None) == 429:
        return True
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "rate limit" in msg.lower()


def _execute_with_backoff(func, *args, **kwargs):
    """
    Calls func(*args, **kwargs), retrying rate-limiting failures (429 /
    ResourceExhausted) with exponential backoff and jitter. Non-rate-limit
    exceptions propagate immediately; the final rate-limit exception is
    escalated after BACKOFF_MAX_RETRIES attempts.
    """
    last_exc = None
    for attempt in range(BACKOFF_MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if not _is_rate_limit_error(exc):
                raise
            last_exc = exc
            if attempt == BACKOFF_MAX_RETRIES:
                break
            delay = BACKOFF_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 1)
            print(f"[AY CLIENT] Rate limited (attempt {attempt + 1}/"
                  f"{BACKOFF_MAX_RETRIES}); backing off {delay:.1f}s: "
                  f"{str(exc)[:120]}")
            time.sleep(delay)
    raise last_exc


def execute_local_shell(command: str) -> str:
    """
    Executes a shell command via shell_wire — the single safety layer for both
    the Gemini plane (this function) and the MCP plane (mcp_server/server.py).
    Preserves the STDOUT:/STDERR: return format expected by existing callers.
    """
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).parent))
    from shell_wire import execute as _shell_execute

    result = _shell_execute(command=command, cwd=str(MAF_ROOT), timeout_seconds=120)

    if result["blocked"]:
        return f"EXECUTION BLOCKED: {result['block_reason']}"
    if result["timed_out"]:
        return (
            f"EXECUTION FAILED: Command timed out after 120 seconds\n"
            f"STDOUT:\n{result['stdout']}\nSTDERR:\n{result['stderr']}"
        )
    return f"STDOUT:\n{result['stdout']}\nSTDERR:\n{result['stderr']}"


def write_local_file(relative_path: str, content: str) -> str:
    """
    Writes string content to a local file within the MAF workspace.
    Delegates to fs_wire so path sandbox and write blocklist are enforced.
    """
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).parent))
    from fs_wire import execute as _fs_execute

    result = _fs_execute(
        operation="write",
        path=relative_path,
        content=content,
        cwd=str(MAF_ROOT),
    )
    if result["blocked"]:
        return f"WRITE BLOCKED: {result['block_reason']}"
    if result["exit_code"] != 0:
        return f"WRITE FAILED: {result['stderr']}"
    return f"SUCCESS: {result['content']} to {relative_path}"


def read_local_file(relative_path: str) -> str:
    """
    Reads the text content of a local file within the MAF workspace.
    Delegates to fs_wire so path sandbox and size limits are enforced.
    """
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).parent))
    from fs_wire import execute as _fs_execute

    result = _fs_execute(
        operation="read",
        path=relative_path,
        cwd=str(MAF_ROOT),
    )
    if result["blocked"]:
        return f"READ BLOCKED: {result['block_reason']}"
    if result["exit_code"] != 0:
        return f"READ FAILED: {result['stderr']}"
    return result["content"]


def playwright_operation(
    operation: str,
    url: str = "",
    selector: str = "",
    text: str = "",
    value: str = "",
    script: str = "",
    css_property: str = "",
    timeout_ms: int = 5000,
    session_id: str = "",
    name: str = "",
) -> str:
    """
    Execute a headless Chromium browser operation via playwright_wire.
    URL allowlist and evaluate blocklist enforced inside playwright_wire.
    Returns the JSON response envelope as a string for Gemini function calling.
    """
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).parent))
    from playwright_wire import execute as _pw_execute

    result = _pw_execute({
        "operation":    operation,
        "url":          url,
        "selector":     selector,
        "text":         text,
        "value":        value,
        "script":       script,
        "css_property": css_property,
        "timeout_ms":   timeout_ms,
        "session_id":   session_id or None,
        "name":         name,
    })

    if result["blocked"]:
        return f"PLAYWRIGHT BLOCKED: {result['block_reason']}"
    if result["timed_out"]:
        return (
            f"PLAYWRIGHT TIMEOUT: operation={operation}\n"
            f"STDOUT:\n{result['stdout']}\nSTDERR:\n{result['stderr']}"
        )
    return (
        f"PLAYWRIGHT [{operation}] exit={result['exit_code']} "
        f"session={result['session_id']}\n"
        f"STDOUT:\n{result['stdout']}\nSTDERR:\n{result['stderr']}"
    )


def execute_remote_shell(host_ip: str, command: str, timeout: int = 60) -> str:
    """
    Executes a shell command on an approved remote server via ssh_wire.
    Preserves the STDOUT:/STDERR: return format expected by Gemini callers.
    """
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).parent))
    from ssh_wire import execute as _ssh_execute

    result = _ssh_execute(host_ip=host_ip, command=command, timeout=timeout)

    if result["blocked"]:
        return f"EXECUTION BLOCKED: {result['block_reason']}"
    if result["exit_code"] == 502:
        return f"EXECUTION FAILED: {result['stderr']}"
    if result["timed_out"]:
        return (
            f"EXECUTION FAILED: Remote command timed out after {timeout} seconds\n"
            f"STDOUT:\n{result['stdout']}\nSTDERR:\n{result['stderr']}"
        )
    host_label = f"{result['host_name']} ({host_ip})" if result["host_name"] else host_ip
    return (
        f"REMOTE [{host_label}] exit={result['exit_code']}\n"
        f"STDOUT:\n{result['stdout']}\nSTDERR:\n{result['stderr']}"
    )


def run_e2e_evaluation(app_name: str, run_id: str = None) -> str:
    """
    Run full E2E evaluation pipeline for a registered app.
    Inspector reads code+docs → builds test plan.
    Seed Agent prepares DB.
    Playwright Agent runs all tests with autonomous fix cycles.
    Returns JSON-encoded EvaluationReport.
    """
    bridge_dir = str(Path(__file__).parent)
    import sys as _sys
    if bridge_dir not in _sys.path:
        _sys.path.insert(0, bridge_dir)
    from e2e_orchestrator import E2EOrchestrator
    orch = E2EOrchestrator()
    if not run_id:
        run_id = str(uuid.uuid4())[:8]
    report = orch.run(app_name, run_id)
    if hasattr(report, "__dict__"):
        report_dict = {k: v for k, v in report.__dict__.items()}
    elif hasattr(report, "_asdict"):
        report_dict = report._asdict()
    elif isinstance(report, dict):
        report_dict = report
    else:
        report_dict = {"raw": str(report)}
    return json.dumps(report_dict, default=str, indent=2)


def send_mandate(mandate: str, timeout: int = 300) -> str:
    """
    Sends a structured mandate to the native local execution bridge.
    Uses Gemini function calling to execute shell commands and file
    mutations directly on the local MAF filesystem.
    Returns the final ledger string.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            chat = _execute_with_backoff(
                client.chats.create,
                model="gemini-2.5-pro",
                config=types.GenerateContentConfig(
                    tools=[execute_local_shell, write_local_file, read_local_file,
                           execute_remote_shell, playwright_operation],
                    temperature=0.0
                )
            )
            response = _execute_with_backoff(chat.send_message, mandate)

            # Tool execution loop — handle all function calls until
            # Gemini returns a final text response
            iteration = 0
            while True:
                function_calls = getattr(response, 'function_calls', None)
                if not function_calls:
                    break

                iteration += 1
                if iteration > MAX_ITERATIONS:
                    raise RuntimeError(
                        f"[AY CLIENT] Circuit breaker triggered: tool execution "
                        f"exceeded {MAX_ITERATIONS} iterations. Possible hallucination "
                        f"loop detected. Halting per CLAUDE_RULES.md Section 3.1."
                    )

                tool_results = []
                for fc in function_calls:
                    if fc.name == "execute_local_shell":
                        result = execute_local_shell(**fc.args)
                    elif fc.name == "write_local_file":
                        result = write_local_file(**fc.args)
                    elif fc.name == "read_local_file":
                        result = read_local_file(**fc.args)
                    elif fc.name == "execute_remote_shell":
                        result = execute_remote_shell(**fc.args)
                    elif fc.name == "playwright_operation":
                        result = playwright_operation(**fc.args)
                    else:
                        result = f"Unknown tool: {fc.name}"
                    tool_results.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"result": result}
                        )
                    )
                response = _execute_with_backoff(chat.send_message, tool_results)

            final_text = getattr(response, 'text', None) or str(response)
            return final_text if final_text else "LEDGER: Execution complete. No text output returned."

    except Exception as e:
        return json.dumps({"error": "Gateway Unreachable", "detail": f"[AY CLIENT FRACTURE] Gemini API interaction failed: {str(e)}"})


def test_connection() -> bool:
    """Tests that the local execution bridge is operational."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            chat = _execute_with_backoff(
                client.chats.create,
                model="gemini-2.5-pro",
                config=types.GenerateContentConfig(
                    tools=[execute_local_shell],
                    temperature=0.0
                )
            )
            response = _execute_with_backoff(
                chat.send_message,
                "Run this exact command and return the output: echo BRIDGE_OK"
            )
            # Handle tool call if fired
            if getattr(response, 'function_calls', None):
                fc = response.function_calls[0]
                result = execute_local_shell(**fc.args)
                response = _execute_with_backoff(chat.send_message, [
                    types.Part.from_function_response(
                        name=fc.name,
                        response={"result": result}
                    )
                ])
            return True
    except Exception as e:
        print(f"[AY CLIENT] Connection test failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing Local Execution Bridge...")
    if test_connection():
        print("[OK] Local Execution Bridge is operational.")
    else:
        print("[FAIL] Local Execution Bridge failed.")
