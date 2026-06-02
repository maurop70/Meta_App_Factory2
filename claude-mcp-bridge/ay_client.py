import os
import subprocess
import warnings
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(Path(__file__).parent.parent / ".env")

MAF_ROOT = Path(__file__).parent.parent.resolve()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def execute_local_shell(command: str) -> str:
    """Executes a shell command on the local Windows OS in the MAF root directory."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(MAF_ROOT),
            timeout=120
        )
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return "EXECUTION FAILED: Command timed out after 120 seconds"
    except Exception as e:
        return f"EXECUTION FAILED: {str(e)}"


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
                    tools=[execute_local_shell, write_local_file, read_local_file],
                    temperature=0.0
                )
            )
            response = chat.send_message(mandate)

            # Tool execution loop — handle all function calls until
            # Gemini returns a final text response
            while True:
                function_calls = getattr(response, 'function_calls', None)
                if not function_calls:
                    break
                tool_results = []
                for fc in function_calls:
                    if fc.name == "execute_local_shell":
                        result = execute_local_shell(**fc.args)
                    elif fc.name == "write_local_file":
                        result = write_local_file(**fc.args)
                    elif fc.name == "read_local_file":
                        result = read_local_file(**fc.args)
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
