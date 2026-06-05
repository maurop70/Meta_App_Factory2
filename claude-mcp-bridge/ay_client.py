import os
import warnings
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(Path(__file__).parent.parent / ".env")

MAF_ROOT = Path(__file__).parent.parent.resolve()
MAX_ITERATIONS = 5

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


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
    """Writes string content to a local file within the MAF workspace."""
    try:
        target_path = MAF_ROOT / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        return f"SUCCESS: Wrote {len(content)} bytes to {relative_path}"
    except Exception as e:
        return f"WRITE FAILED: {str(e)}"


def read_local_file(relative_path: str) -> str:
    """Reads the text content of a local file within the MAF workspace."""
    try:
        target_path = MAF_ROOT / relative_path
        return target_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"READ FAILED: {str(e)}"


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
            chat = client.chats.create(
                model="gemini-2.5-pro",
                config=types.GenerateContentConfig(
                    tools=[execute_local_shell, write_local_file, read_local_file,
                           execute_remote_shell],
                    temperature=0.0
                )
            )
            response = chat.send_message(mandate)

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
                    else:
                        result = f"Unknown tool: {fc.name}"
                    tool_results.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"result": result}
                        )
                    )
                response = chat.send_message(tool_results)

            final_text = getattr(response, 'text', None) or str(response)
            return final_text if final_text else "LEDGER: Execution complete. No text output returned."

    except Exception as e:
        raise RuntimeError(
            f"[AY CLIENT] Local Execution Bridge failed: {e}\n"
            f"Halting per CLAUDE_RULES.md Section 3.1 — "
            f"raw exception surfaced, not swallowed."
        )


def test_connection() -> bool:
    """Tests that the local execution bridge is operational."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            chat = client.chats.create(
                model="gemini-2.5-pro",
                config=types.GenerateContentConfig(
                    tools=[execute_local_shell],
                    temperature=0.0
                )
            )
            response = chat.send_message(
                "Run this exact command and return the output: echo BRIDGE_OK"
            )
            # Handle tool call if fired
            if getattr(response, 'function_calls', None):
                fc = response.function_calls[0]
                result = execute_local_shell(**fc.args)
                response = chat.send_message([
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
