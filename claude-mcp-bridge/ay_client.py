"""
Antigravity Client
------------------
Programmatic wrapper around the Antigravity Agent API.
Sends mandates from Claude Code to Antigravity and returns ledgers.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

# Load .env from MAF root
load_dotenv(Path(__file__).parent.parent / ".env")

GEMINI_API_KEY = os.getenv( "GEMINI_API_KEY" )
if not GEMINI_API_KEY:
    raise RuntimeError(
        "[AY CLIENT] FATAL: GEMINI_API_KEY not found in .env — "
        "halting per CLAUDE_RULES.md Section 0.3"
    )

client = genai.Client(api_key=GEMINI_API_KEY)



def send_mandate(mandate: str, timeout: int = 300) -> str:
    """
    Sends a structured mandate to Antigravity and returns the ledger.

    Args:
        mandate: Full mandate text including SYSTEM_RULES and USER_REQUEST
        timeout: Max seconds to wait for AY response (default 300)

    Returns:
        Ledger string returned by Antigravity
    """
    try:
        interaction = client.interactions.create(
            agent="antigravity-preview-05-2026",
            input=mandate,
            extra_body={"environment": "local"},
            tools=[
                {"type": "code_edit"},
                {"type": "shell"},
            ],
            timeout=timeout,
        )
        if hasattr(interaction, "output_text"):
            return interaction.output_text
        elif hasattr(interaction, "outputs") and interaction.outputs:
            return interaction.outputs[0].text
        return str(interaction)

    except Exception as e:
        raise RuntimeError(
            f"[AY CLIENT] Antigravity API call failed: {e}\n"
            f"Halting per CLAUDE_RULES.md Section 3.1 — "
            f"raw exception surfaced, not swallowed."
        )


def test_connection() -> bool:
    """Quick handshake to verify API key and AY connectivity."""
    try:
        interaction = client.interactions.create(
            agent="antigravity-preview-05-2026",
            input="Reply with exactly: AY CONNECTION OK",
            extra_body={"environment": "local"},
            tools=[],
            timeout=30,
        )
        if hasattr(interaction, "output_text"):
            out = interaction.output_text
        elif hasattr(interaction, "outputs") and interaction.outputs:
            out = interaction.outputs[0].text
        else:
            out = ""
        return "AY CONNECTION OK" in out
    except Exception:
        return False



if __name__ == "__main__":
    print("Testing Antigravity connection...")
    if test_connection():
        print("[OK] Antigravity API is reachable and responding.")
    else:
        print("[FAILED] Could not reach Antigravity API. Check GEMINI_API_KEY.")
