import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

# Plan v2 §3.1 (option A): instead of brittle keyword/symbol matching (which
# misfires on hyphens, dates, URLs, and ambiguous words like "evolution"), we
# run a single cheap classifier pass and route only genuine reasoning to Claude.
# The safety default everywhere — short input, missing keys, classifier failure,
# non-200, or any non-"YES" verdict — is the conversational model.


class IntelligentModelRouter:
    def __init__(self):
        self.fast_model = "gemini-2.5-flash"
        # §3.2: env RESONANCE_CLAUDE_MODEL -> config.json -> default. Never a
        # hardcoded dated snapshot.
        self.deep_model = self._resolve_deep_model()

    # ── Configuration ────────────────────────────────────────────────
    @staticmethod
    def _resolve_deep_model() -> str:
        """Resolve the Claude model: env var, then config.json, then default."""
        env_model = os.getenv("RESONANCE_CLAUDE_MODEL", "").strip()
        if env_model:
            return env_model
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg_model = (json.load(f).get("claude_model") or "").strip()
            if cfg_model:
                return cfg_model
        except (OSError, json.JSONDecodeError):
            pass
        return "claude-sonnet-4-6"

    @staticmethod
    def _get_secret(name: str) -> str:
        """Read a secret from the environment, falling back to the vault."""
        val = os.getenv(name, "")
        if val:
            return val
        try:
            from vault_client import get_secret
            return get_secret(name) or ""
        except Exception:
            return ""

    # ── Routing ──────────────────────────────────────────────────────
    def determine_optimal_model(self, prompt: str, system_prompt: str = "") -> str:
        """Route a user message to the deep model only when a cheap classifier
        pass says it genuinely needs step-by-step reasoning.

        Returns the conversational (fast) model on every ambiguous or failing
        path: trivially short input, no Gemini key, no Anthropic key, classifier
        error, non-200 status, or any verdict that is not an unambiguous YES.
        """
        if not prompt or len(prompt.strip()) < 3:
            return self.fast_model

        gemini_key = self._get_secret("GEMINI_API_KEY")
        if not gemini_key:
            return self.fast_model

        # No point routing to Claude if we can't authenticate to it.
        if not self._get_secret("ANTHROPIC_API_KEY"):
            return self.fast_model

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        headers = {"x-goog-api-key": gemini_key, "Content-Type": "application/json"}
        classification_prompt = (
            "Does answering the following user message require step-by-step math, "
            "logic, or scientific reasoning? Answer only YES or NO.\n\n"
            f"User message: \"{prompt}\""
        )
        payload = {
            "contents": [{"parts": [{"text": classification_prompt}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 2},
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                candidate = (data.get("candidates") or [{}])[0]
                parts = candidate.get("content", {}).get("parts", [])
                verdict = "".join(p.get("text", "") for p in parts).strip().upper()
                # Route to Claude ONLY on an unambiguous YES; anything else
                # (NO, blank, "MAYBE", garbage) stays conversational.
                if verdict.startswith("YES"):
                    print(f"[ROUTER] Reasoning task detected. Routing to Claude ({self.deep_model})")
                    return self.deep_model
        except Exception as e:
            print(f"[ROUTER] Classification failed ({e}). Defaulting to conversational model.")

        # Ambiguity / failure default is ALWAYS the conversational model.
        return self.fast_model

    def execute(self, task_type: str, instruction: str, context: dict):
        # The user's actual message is the instruction; classify on that.
        model = self.determine_optimal_model(instruction, task_type)
        return {
            "status": "success",
            "routed_via": model,
            "data": f"Executed '{task_type}' natively on {model}",
        }


if __name__ == "__main__":
    router = IntelligentModelRouter()
    print(router.execute("Deconstruction", "Solve a partial differential equation", {}))
    print(router.execute("Chat", "Tell Leo hello!", {}))
