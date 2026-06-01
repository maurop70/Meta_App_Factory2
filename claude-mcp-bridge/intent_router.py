"""
Intent Router — ClaudeAY Dual Engine Classifier
-------------------------------------------------
Classifies Builder Chat conversational queries as:
  CLAUDE  → code, build, debug, fix, ERP, architect tasks
  GEMINI  → strategy, business, brand, financial, C-Suite tasks

Sits inside the CONVERSATIONAL_QUERY branch of server.py.
STRUCTURAL_MANDATE and /genesis paths bypass this entirely.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger("IntentRouter")

CLAUDE_KEYWORDS = [
    "build", "fix", "debug", "code", "module", "deploy",
    "architect", "refactor", "error", "crash", "erp",
    "endpoint", "database", "migration", "test", "playwright",
    "bug", "broken", "not working", "fails", "exception",
    "traceback", "patch", "repair", "implement", "create",
    "add feature", "new route", "maintenance", "work order",
    "backend", "frontend", "component", "schema", "function",
    "syntax", "import", "install", "dependency", "port",
    "server", "fastapi", "react", "vite", "uvicorn",
    "404", "500", "503", "health", "diagnose", "diagnosis",
    "endpoint", "route", "not found", "traceback", "stderr",
    "stdout", "log", "watchdog", "monitor", "check", "verify",
    "curl", "ping", "socket", "connection refused", "timeout",
    "restart", "kill", "process", "pid", "daemon", "service",
]

GEMINI_KEYWORDS = [
    "strategy", "market", "brand", "financial", "legal",
    "pitch", "investor", "cmo", "cfo", "clo", "cto",
    "war room", "venture", "tam", "sam", "som",
    "competition", "persona", "gtm", "go-to-market",
    "revenue", "funding", "valuation", "cap table",
    "marketing", "audience", "sentiment", "scout",
    "business plan", "feasibility", "swot", "campaign",
]


def classify_intent_keywords(prompt: str) -> str:
    """
    Fast keyword classifier. Returns 'CLAUDE' or 'GEMINI'.
    Default is GEMINI when ambiguous (preserves existing behaviour).
    """
    prompt_lower = prompt.lower()
    claude_score = sum(1 for kw in CLAUDE_KEYWORDS if kw in prompt_lower)
    gemini_score = sum(1 for kw in GEMINI_KEYWORDS if kw in prompt_lower)
    logger.info(f"[ROUTER] Scores — Claude:{claude_score} Gemini:{gemini_score}")
    if claude_score > gemini_score:
        return "CLAUDE"
    return "GEMINI"  # Default preserves existing Gemini behaviour


async def classify_intent(prompt: str) -> str:
    """
    Classifies intent using Gemini Flash (~300ms, ~50 tokens).
    Falls back to keyword matching on any failure.
    Always defaults to GEMINI on ambiguity — preserves MAF behaviour.
    """
    try:
        api_key = os.getenv("GEMINI_API_KEY", "").strip("'\"")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY missing")

        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        classification_prompt = (
            "You are a routing classifier. Reply with exactly one word: CLAUDE or GEMINI.\n\n"
            "CLAUDE: code building, debugging, fixing bugs, implementing features, "
            "database work, API endpoints, ERP tasks, testing, architectural code tasks.\n\n"
            "GEMINI: business strategy, market research, brand, financials, legal, "
            "investor pitches, C-Suite debates, war room, competitive analysis, marketing.\n\n"
            f"Request: {prompt[:400]}\n\n"
            "One word only:"
        )

        response = model.generate_content(classification_prompt)
        result = response.text.strip().upper()

        if result in ("CLAUDE", "GEMINI"):
            logger.info(f"[ROUTER] LLM → {result}")
            return result
        return classify_intent_keywords(prompt)

    except Exception as e:
        logger.warning(f"[ROUTER] LLM failed ({e}). Keyword fallback.")
        return classify_intent_keywords(prompt)


if __name__ == "__main__":
    import asyncio

    tests = [
        ("Fix the ERP crash on port 8000", "CLAUDE"),
        ("Build an inventory module", "CLAUDE"),
        ("Debug the SSE streaming error", "CLAUDE"),
        ("Analyze our market position", "GEMINI"),
        ("Generate a Series A pitch deck", "GEMINI"),
        ("Create a GTM strategy", "GEMINI"),
    ]

    async def run():
        print("Intent Router — Test\n")
        passed = 0
        for prompt, expected in tests:
            result = classify_intent_keywords(prompt)
            ok = "PASS" if result == expected else "FAIL"
            print(f"[{ok}] [{result:6}] {prompt}")
            if result == expected:
                passed += 1
        print(f"\n{passed}/{len(tests)} passed")

    asyncio.run(run())
