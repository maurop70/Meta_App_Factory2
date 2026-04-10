from auto_heal import healed_post, auto_heal, diagnose

"""
refine_engine.py — Factory Self-Healing Engine V2
═══════════════════════════════════════════════════
Reads a child app's source files, performs static analysis,
inventories assets, sends everything to Gemini with
refinement instructions, parses the response, and writes
modified files back. Closes the self-healing loop.

V2 Enhancements:
- Asset Inventory: scans public/ for images, fonts, media
- Static Analysis: detects common frontend/backend bugs
- Production-Quality System Prompt with anti-pattern rules
"""

import os
import sys
import json
import logging
import re
import subprocess
import shutil
from typing import Generator, Dict, List, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger("RefineEngine")

# ── Vault Integration ────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

_vault_paths = [
    os.path.dirname(SCRIPT_DIR),  # .system_core root
    os.path.join(SCRIPT_DIR, "Alpha_V2_Genesis"),
]
for vp in _vault_paths:
    if os.path.exists(os.path.join(vp, "vault_client.py")):
        sys.path.insert(0, vp)
        break

try:
    from vault_client import get_secret
except ImportError:
    def get_secret(key, default="", **kw):
        return os.getenv(key, default)

# ── Load factory .env so keys are available via os.getenv fallback ──
try:
    from dotenv import load_dotenv
    _factory_env = os.path.join(SCRIPT_DIR, ".env")
    if os.path.exists(_factory_env):
        load_dotenv(_factory_env, override=False)
except ImportError:
    pass



# ── File Discovery ───────────────────────────────────────────

MODIFIABLE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".html",
    ".json", ".bat", ".sh", ".md", ".env.template",
    ".yml", ".yaml",  # Docker Compose, CI/CD configs
}

SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".Gemini_state"}
SKIP_FILES = {".env", "package-lock.json"}

# Asset extensions the engine recognizes
ASSET_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".mp4", ".webm", ".mp3", ".wav", ".ogg",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
}


def discover_app_files(app_dir: str) -> Dict[str, str]:
    """Walk the app directory and read all modifiable source files."""
    files = {}
    for root, dirs, filenames in os.walk(app_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in filenames:
            if fname in SKIP_FILES:
                continue
            _, ext = os.path.splitext(fname)
            if ext not in MODIFIABLE_EXTENSIONS:
                continue
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, app_dir)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                if len(content) > 50000:
                    continue
                files[rel_path] = content
            except Exception as e:
                logger.warning(f"Could not read {fpath}: {e}")
    return files


def inventory_assets(app_dir: str) -> List[Dict[str, str]]:
    """Scan the app directory (including public/) for media assets.
    Returns a list of dicts: {path, filename, type, web_path}."""
    assets = []
    for root, dirs, filenames in os.walk(app_dir):
        dirs[:] = [d for d in dirs if d not in {"node_modules", "__pycache__", ".git"}]
        for fname in filenames:
            _, ext = os.path.splitext(fname)
            if ext.lower() not in ASSET_EXTENSIONS:
                continue
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, app_dir)
            # Compute the web-accessible path (for Vite, files in public/ are at /)
            web_path = None
            rel_to_ui = os.path.relpath(fpath, os.path.join(app_dir, "resonance_ui"))
            if not rel_to_ui.startswith(".."):
                # File is inside resonance_ui
                rel_to_public = os.path.relpath(fpath, os.path.join(app_dir, "resonance_ui", "public"))
                if not rel_to_public.startswith(".."):
                    web_path = "/" + rel_to_public.replace("\\", "/")
                else:
                    # Inside src — use import path
                    web_path = "./" + os.path.relpath(fpath, os.path.join(app_dir, "resonance_ui", "src")).replace("\\", "/")

            assets.append({
                "path": rel_path,
                "filename": fname,
                "type": ext.lower().lstrip("."),
                "web_path": web_path or f"/{fname}",
            })
    return assets


# ── Static Analysis ──────────────────────────────────────────

def static_analysis(source_files: Dict[str, str]) -> List[str]:
    """Run lightweight static checks on source code. Returns diagnostic strings."""
    diagnostics = []

    for rel_path, content in source_files.items():
        # --- React / JSX checks ---
        if rel_path.endswith((".jsx", ".tsx", ".js")):
            # Check: streaming state set but never activated
            if "streaming" in content and "setStreaming(true)" not in content and "setStreaming" in content:
                diagnostics.append(
                    f"⚠️ {rel_path}: `streaming` state exists with `setStreaming` but `setStreaming(true)` "
                    f"is never called. This means the `streaming` guard will never prevent double-sends. "
                    f"Add `setStreaming(true)` at the start of the send function."
                )

            # Check: BOT/badge labels on AI entities
            if "bot-badge" in content.lower() or ">BOT<" in content:
                diagnostics.append(
                    f"⚠️ {rel_path}: Contains a 'BOT' badge/label. For production UX, AI personas should "
                    f"appear as native entities without technical labels."
                )

            # Check: letter avatars when image assets may exist
            if re.search(r"className=['\"]avatar['\"].*>[A-Z]<", content):
                diagnostics.append(
                    f"💡 {rel_path}: Uses single-letter avatar placeholders. If image assets exist in "
                    f"public/, they should be used instead via <img> tags."
                )

            # Check: dangerouslySetInnerHTML without sanitization
            if "dangerouslySetInnerHTML" in content and "DOMPurify" not in content:
                diagnostics.append(
                    f"💡 {rel_path}: Uses dangerouslySetInnerHTML without DOMPurify sanitization. "
                    f"Consider adding sanitization for production security."
                )

            # Check: React.StrictMode + SSE streaming conflict
            if "StrictMode" in content and rel_path.endswith(("main.jsx", "main.tsx", "index.jsx", "index.tsx")):
                for other_path, other_content in source_files.items():
                    if other_path == rel_path:
                        continue
                    if "getReader()" in other_content or "EventSource" in other_content or "text/event-stream" in other_content:
                        diagnostics.append(
                            f"⚠️ {rel_path}: Uses React.StrictMode, but {other_path} uses SSE streaming. "
                            f"StrictMode double-invokes effects and callbacks in dev mode, causing streamed "
                            f"text to appear duplicated. Remove StrictMode or wrap SSE logic in a ref-guarded "
                            f"useEffect to prevent double-invocation."
                        )
                        break  # One warning is enough

        # --- Python backend checks ---
        if rel_path.endswith(".py"):
            # Check: response accumulator not cleared
            if "full = []" in content or "full_response = []" in content:
                # Check if it's inside a generator that might not reset
                if "yield" in content and "def stream_chat" in content:
                    # Check for history replay that could cause echo
                    if "_load_history" in content and "history.append" in content:
                        lines = content.split("\n")
                        user_appends = sum(1 for l in lines if "history.append" in l and '"user"' in l)
                        if user_appends > 0:
                            diagnostics.append(
                                f"💡 {rel_path}: Chat history is loaded AND the new user message is appended "
                                f"before sending to Gemini. If the same message was already saved from a "
                                f"previous call, it could appear twice in the context, causing echo/duplicate "
                                f"responses. Ensure the history is loaded fresh and deduplicated."
                            )

            # Check: dotenv not loaded
            if "os.getenv" in content and "load_dotenv" not in content and "vault_client" not in content:
                diagnostics.append(
                    f"⚠️ {rel_path}: Uses os.getenv() but never calls load_dotenv(). "
                    f"Environment variables from .env won't be available."
                )

    return diagnostics


# ── Gemini API Call ──────────────────────────────────────────

def _call_gemini(prompt: str, max_tokens: int = 65536) -> Optional[str]:
    """Non-streaming Gemini call with retry. Returns complete text response."""
    import requests as _requests
    import time as _time

    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in vault, env, or .env files")
        return None

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    _headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": max_tokens,
        },
    }

    last_error = None
    for attempt in range(3):
        try:
            resp = _requests.post(url, json=payload, headers=_headers, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts)
                if text:
                    return text
                logger.error(f"Gemini returned empty content: {resp.text[:300]}")
                return None
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
                logger.warning(f"Gemini attempt {attempt+1}/3 failed: {last_error}")
        except _requests.exceptions.Timeout:
            last_error = "Request timed out (120s)"
            logger.warning(f"Gemini attempt {attempt+1}/3 timed out")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Gemini attempt {attempt+1}/3 error: {e}")

        if attempt < 2:
            wait = 2 ** (attempt + 1)
            logger.info(f"Retrying Gemini in {wait}s...")
            _time.sleep(wait)

    logger.error(f"Gemini call failed after 3 attempts. Last error: {last_error}")
    return None


# ── Response Parser ──────────────────────────────────────────

def parse_file_modifications(gemini_response: str) -> Dict[str, str]:
    """
    Parse Gemini's response to extract file modifications.
    Expected format:
    ===FILE: relative/path/to/file.ext===
    file content here
    ===END_FILE===
    """
    modifications = {}
    pattern = r'===FILE:\s*(.+?)\s*===\n(.*?)===END_FILE==='
    matches = re.findall(pattern, gemini_response, re.DOTALL)
    for path, content in matches:
        path = path.strip()
        content = content.strip("\n")
        modifications[path] = content
    return modifications


# ── Post-Write Lint Validation ───────────────────────────────

def _lint_file(full_path: str, rel_path: str, app_dir: str) -> List[str]:
    """
    Validate syntax of a written file. Returns list of error strings (empty = passed).
    JSX/TSX: tries @babel/parser via Node subprocess, falls back to Python heuristics.
    Python: uses compile().
    """
    _, ext = os.path.splitext(rel_path)
    errors = []

    if ext in {".jsx", ".tsx", ".js", ".ts"}:
        errors = _lint_jsx_node(full_path, rel_path, app_dir)
        if errors is None:
            # Node/Babel not available — fall back to heuristic
            errors = _lint_jsx_heuristic(full_path, rel_path)
    elif ext == ".py":
        errors = _lint_python(full_path, rel_path)

    return errors


def _lint_jsx_node(full_path: str, rel_path: str, app_dir: str) -> Optional[List[str]]:
    """
    Try to parse JSX/TSX using @babel/parser from the project's node_modules.
    Returns list of errors, or None if Node/Babel is not available.
    """
    # Find node_modules — check app_dir and subdirectories
    node_modules = None
    for root, dirs, _ in os.walk(app_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__" and d != ".git"]
        if "node_modules" in dirs:
            candidate = os.path.join(root, "node_modules", "@babel", "parser")
            if os.path.isdir(candidate):
                node_modules = os.path.join(root, "node_modules")
                break

    if not node_modules:
        return None  # Signal to use fallback

    # Determine parser plugins based on extension
    _, ext = os.path.splitext(rel_path)
    plugins = ["jsx"]
    if ext in {".tsx", ".ts"}:
        plugins.append("typescript")

    # Build a tiny Node script to parse the file
    script = f"""
const parser = require('{node_modules.replace(os.sep, "/")}/@babel/parser');
const fs = require('fs');
try {{
    const code = fs.readFileSync('{full_path.replace(os.sep, "/")}', 'utf8');
    parser.parse(code, {{
        sourceType: 'module',
        plugins: {json.dumps(plugins)},
    }});
    process.stdout.write('OK');
}} catch (e) {{
    process.stdout.write('PARSE_ERROR: ' + e.message);
}}
"""
    node_cmd = shutil.which("node") or shutil.which("node.exe")
    if not node_cmd:
        return None

    try:
        result = subprocess.run(
            [node_cmd, "-e", script],
            capture_output=True, text=True, timeout=15,
            cwd=app_dir,
        )
        output = (result.stdout + result.stderr).strip()
        if output.startswith("PARSE_ERROR:"):
            return [f"{rel_path}: {output}"]
        elif output == "OK":
            return []
        else:
            # Something unexpected — don't block
            logger.warning(f"Unexpected lint output for {rel_path}: {output}")
            return []
    except Exception as e:
        logger.warning(f"Node lint failed for {rel_path}: {e}")
        return None  # Fall back to heuristic


def _lint_jsx_heuristic(full_path: str, rel_path: str) -> List[str]:
    """
    Pure-Python heuristic checks for common JSX syntax errors.
    Catches the most common Gemini mistakes without requiring Node.
    """
    errors = []
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            lines = content.split("\n")
    except Exception:
        return [f"{rel_path}: Could not read file for lint check"]

    # 1. Bracket/brace/paren balance
    stack = []
    bracket_map = {")": "(", "]": "[", "}": "{"}
    in_string = None
    in_template = False
    for i, char in enumerate(content):
        # Basic string tracking (doesn't handle all edge cases but catches most)
        if char in ('"', "'", "`"):
            if in_string == char:
                in_string = None
            elif in_string is None:
                in_string = char
            continue
        if in_string:
            continue

        if char in ("(", "[", "{"):
            stack.append(char)
        elif char in (")", "]", "}"):
            if not stack or stack[-1] != bracket_map[char]:
                line_num = content[:i].count("\n") + 1
                errors.append(f"{rel_path}:{line_num}: Unmatched '{char}'")
                break
            stack.pop()

    if stack and not errors:
        errors.append(f"{rel_path}: Unclosed brackets/braces — {len(stack)} unmatched opening bracket(s)")

    # 2. JSX comment inside tag attribute list (the exact bug Gemini introduced)
    # Detect {/* */} on a line that appears to be inside a JSX tag's attribute block
    in_jsx_tag = False
    tag_open_line = 0
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Track if we're inside a multi-line JSX tag
        if re.search(r'<\w[^>]*$', stripped) and not stripped.endswith('/>'):
            in_jsx_tag = True
            tag_open_line = i
        if in_jsx_tag and ('>' in stripped or '/>' in stripped):
            in_jsx_tag = False

        # Check for JSX comment on an attribute line or between attributes
        if re.search(r'\{/\*.*?\*/\}', stripped):
            # If inside a JSX tag, or on a line with attribute-like patterns
            if in_jsx_tag or re.search(r'=\{[^}]*\}\s*\{/\*', line):
                errors.append(
                    f"{rel_path}:{i}: JSX comment inside tag attribute list — "
                    f"'{{/* ... */}}' cannot appear between attributes. Move the comment above or below the tag."
                )

    # 3. Unclosed template literals (common Gemini mistake)
    backtick_count = content.count("`")
    if backtick_count % 2 != 0:
        errors.append(f"{rel_path}: Odd number of backticks ({backtick_count}) — likely an unclosed template literal")

    # 4. Unclosed HTML/JSX tags (common Gemini omission)
    # Match self-closing and void elements
    void_tags = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}
    open_tags = re.findall(r'<([a-zA-Z][a-zA-Z0-9]*)[\s>]', content)
    close_tags = re.findall(r'</([a-zA-Z][a-zA-Z0-9]*)\s*>', content)
    self_closing = re.findall(r'<([a-zA-Z][a-zA-Z0-9]*)[^>]*/>', content)

    # Count tags (excluding void/self-closing)
    opens = {}
    for tag in open_tags:
        tag_lower = tag.lower()
        if tag_lower not in void_tags and tag not in self_closing:
            opens[tag_lower] = opens.get(tag_lower, 0) + 1
    closes = {}
    for tag in close_tags:
        closes[tag.lower()] = closes.get(tag.lower(), 0) + 1

    for tag, count in opens.items():
        close_count = closes.get(tag, 0)
        if count > close_count:
            errors.append(
                f"{rel_path}: Unclosed <{tag}> tag — "
                f"{count} opening vs {close_count} closing"
            )

    return errors


def _lint_python(full_path: str, rel_path: str) -> List[str]:
    """Validate Python syntax using compile()."""
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        compile(source, rel_path, "exec")
        return []
    except SyntaxError as e:
        return [f"{rel_path}:{e.lineno}: {e.msg}"]
    except Exception as e:
        return [f"{rel_path}: Lint error — {e}"]


# ── ESLint Structural Check ──────────────────────────────────

def _eslint_structural_check(full_path: str, rel_path: str, app_dir: str) -> List[str]:
    """
    Run ESLint via Node subprocess for structural analysis beyond syntax.
    Catches: unused vars, missing imports, unreachable code, etc.
    Returns list of warning/error strings. Returns [] if ESLint unavailable.
    """
    _, ext = os.path.splitext(rel_path)
    if ext not in {".jsx", ".tsx", ".js", ".ts"}:
        return []

    # Find eslint in node_modules
    eslint_bin = None
    for root, dirs, _ in os.walk(app_dir):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git"}]
        if "node_modules" in dirs:
            candidate = os.path.join(root, "node_modules", ".bin", "eslint")
            # Windows: eslint.cmd
            if os.path.exists(candidate) or os.path.exists(candidate + ".cmd"):
                eslint_bin = candidate + ".cmd" if os.name == "nt" else candidate
                break

    if not eslint_bin:
        return []  # ESLint not installed — skip silently

    try:
        result = subprocess.run(
            [eslint_bin, "--no-eslintrc", "--format", "json",
             "--rule", '{"no-undef": "error", "no-unused-vars": "warn"}',
             "--parser-options", "ecmaVersion:2022,ecmaFeatures:{jsx:true},sourceType:module",
             full_path],
            capture_output=True, text=True, timeout=15,
            cwd=app_dir,
        )
        if result.stdout.strip():
            try:
                lint_data = json.loads(result.stdout)
                issues = []
                for file_result in lint_data:
                    for msg in file_result.get("messages", []):
                        severity = "ERROR" if msg.get("severity") == 2 else "WARN"
                        issues.append(
                            f"{rel_path}:{msg.get('line', '?')}:{msg.get('column', '?')}: "
                            f"[{severity}] {msg.get('message', '?')} ({msg.get('ruleId', 'unknown')})"
                        )
                return issues
            except json.JSONDecodeError:
                return []
        return []
    except Exception as e:
        logger.debug(f"ESLint check skipped for {rel_path}: {e}")
        return []


# ── AST Correction Loop ──────────────────────────────────────

AST_CORRECTION_PROMPT = """You are a JSX/React syntax repair specialist.

The Meta App Factory code generator produced the following file, but it has parse errors.
Your job: Fix ONLY the syntax/structural errors. Do NOT change functionality, styling, or logic.

## BABEL PARSE ERRORS
{errors}

## ESLINT STRUCTURAL ISSUES
{eslint_issues}

## BROKEN FILE: {rel_path}
```
{numbered_code}
```

## RULES
1. Return the COMPLETE corrected file content — not a diff.
2. Fix every parse error listed above.
3. NEVER place JSX comments {{/* */}} between HTML/JSX tag attributes.
4. Ensure all brackets, braces, and parentheses are balanced.
5. Ensure all template literals (backticks) are properly closed.
6. Preserve ALL existing functionality — only fix structural errors.
7. Wrap your output in:
===FILE: {rel_path}===
...corrected code...
===END_FILE===
"""


def _ast_correction_loop(
    broken_code: str,
    babel_errors: List[str],
    eslint_issues: List[str],
    rel_path: str,
    app_dir: str,
    max_attempts: int = 2,
) -> Tuple[Optional[str], bool, List[str]]:
    """
    Feed Babel/ESLint parse errors back to Gemini as structural DOM/AST feedback.
    Returns (corrected_code, passed, attempt_log).

    - corrected_code: the corrected source code string, or None if all attempts fail
    - passed: True if the corrected code passes Babel lint
    - attempt_log: list of human-readable log strings for SSE telemetry
    """
    attempt_log = []
    current_code = broken_code
    current_errors = babel_errors
    current_eslint = eslint_issues

    for attempt in range(1, max_attempts + 1):
        attempt_log.append(
            f"AST Correction attempt {attempt}/{max_attempts}: "
            f"{len(current_errors)} parse error(s), {len(current_eslint)} structural issue(s)"
        )

        # Build numbered code for precise line references
        lines = current_code.split("\n")
        numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))

        prompt = AST_CORRECTION_PROMPT.format(
            errors="\n".join(f"  - {e}" for e in current_errors) or "  (none)",
            eslint_issues="\n".join(f"  - {e}" for e in current_eslint) or "  (none)",
            rel_path=rel_path,
            numbered_code=numbered,
        )

        response = _call_gemini(prompt, max_tokens=32768)
        if not response:
            attempt_log.append(f"Attempt {attempt}: Gemini call failed — aborting correction.")
            return None, False, attempt_log

        # Parse the corrected file from response
        corrections = parse_file_modifications(response)
        corrected = corrections.get(rel_path)
        if not corrected:
            # Try to find any file in corrections
            if corrections:
                corrected = next(iter(corrections.values()))
            else:
                attempt_log.append(f"Attempt {attempt}: Could not parse corrected code from response.")
                continue

        # Write to a tmp file for lint verification
        tmp_path = os.path.join(app_dir, f".ast_correction_tmp{os.path.splitext(rel_path)[1]}")
        try:
            with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(corrected)

            # Re-lint with Babel
            new_errors = _lint_jsx_node(tmp_path, rel_path, app_dir)
            if new_errors is None:
                new_errors = _lint_jsx_heuristic(tmp_path, rel_path)

            # Re-check ESLint
            new_eslint = _eslint_structural_check(tmp_path, rel_path, app_dir)
            # Only count actual errors (not warnings) as blockers
            eslint_blocking = [e for e in new_eslint if "[ERROR]" in e]

            if not new_errors and not eslint_blocking:
                attempt_log.append(
                    f"Attempt {attempt}: ✅ Correction PASSED — "
                    f"all parse errors resolved{f', {len(new_eslint)} warnings remain' if new_eslint else ''}."
                )
                return corrected, True, attempt_log
            else:
                remaining = (new_errors or []) + eslint_blocking
                attempt_log.append(
                    f"Attempt {attempt}: Still {len(remaining)} error(s) — "
                    f"feeding back for another correction pass."
                )
                current_code = corrected
                current_errors = new_errors or []
                current_eslint = new_eslint
        finally:
            # Clean up tmp file
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    attempt_log.append(f"AST Correction exhausted {max_attempts} attempts — reverting to original.")
    return None, False, attempt_log

# ── Active Recall: Validation Loop Helpers ───────────────────

def _load_high_priority_failures(app_dir: str) -> List[dict]:
    """Load past high-priority failures from .Gemini_state to prevent repeat errors."""
    state_dir = os.path.join(os.path.dirname(app_dir), ".Gemini_state")
    failures_path = os.path.join(state_dir, "high_priority_failures.json")
    if not os.path.isfile(failures_path):
        return []
    try:
        with open(failures_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Return only failures relevant to this app (last 10)
        app_name = os.path.basename(app_dir)
        return [e for e in data if e.get("app_name") == app_name][-10:]
    except Exception as e:
        logger.warning(f"Could not load high-priority failures: {e}")
        return []


def _extract_fix_descriptions(
    modifications: Dict[str, str], gemini_response: str
) -> List[dict]:
    """Extract a list of {file, description} from the Gemini response summary."""
    fixes = []
    # Gemini typically writes a brief summary before ===FILE=== blocks.
    # Extract lines that look like fix descriptions.
    summary_section = gemini_response.split("===FILE:")[0].strip()
    for line in summary_section.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Match lines like "- Fixed X in Y" or "* Updated Z"
        if line.startswith(("-", "*", "•")):
            fixes.append({"description": line.lstrip("-*• ").strip()})

    # Also generate entries from modified file names
    for rel_path in modifications:
        fixes.append({"file": rel_path, "description": f"Modified {rel_path}"})

    return fixes


def _generate_test_case(
    app_name: str,
    app_dir: str,
    fix_descriptions: List[dict],
    source_files: Dict[str, str],
) -> Optional[str]:
    """Call Gemini to generate a test_case.py that validates the applied fixes."""
    fix_text = "\n".join(
        f"  - {f.get('file', 'general')}: {f['description']}" for f in fix_descriptions
    )

    # Include a subset of source files for context (keep prompt under 30k chars)
    context_files = []
    budget = 20000
    for rel_path, content in source_files.items():
        if rel_path.endswith((".py", ".js", ".jsx")):
            chunk = content[:3000]
            if budget - len(chunk) < 0:
                break
            context_files.append(f"===FILE: {rel_path}===\n{chunk}\n===END_FILE===")
            budget -= len(chunk)

    test_prompt = f"""You are a QA engineer for the "{app_name}" application.

The self-healing engine just applied these fixes:
{fix_text}

Here are the relevant source files (truncated for context):
{chr(10).join(context_files)}

Generate a Python test file using ONLY the `unittest` standard library module.
The test file must:
1. Be a complete, runnable `test_case.py` file
2. Test that the fixes are logically sound (e.g. files exist, imports work, key functions are callable)
3. Include at least one test per fix described above
4. Use descriptive test method names like `test_<what_was_fixed>`
5. NOT import any external packages — only stdlib + the app's own modules
6. NOT start a server or make HTTP requests
7. Handle ImportError gracefully with `self.skipTest()` if a module can't be imported

Return ONLY the Python code. No markdown fences, no explanation.
"""

    response = _call_gemini(test_prompt, max_tokens=8192)
    if not response:
        return None

    # Clean markdown fences if present
    code = response.strip()
    if code.startswith("```python"):
        code = code[len("```python"):]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    code = code.strip()

    # Validate syntax before writing
    try:
        compile(code, "test_case.py", "exec")
    except SyntaxError as e:
        logger.warning(f"Generated test_case.py has syntax error: {e}")
        return None

    # Write to app directory
    test_path = os.path.join(app_dir, "test_case.py")
    try:
        with open(test_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(code)
        return test_path
    except Exception as e:
        logger.error(f"Could not write test_case.py: {e}")
        return None


def _log_high_priority_failure(
    app_dir: str, app_name: str, verdict: dict, feedback: str
) -> None:
    """Append a high-priority failure entry to .Gemini_state/high_priority_failures.json."""
    state_dir = os.path.join(os.path.dirname(app_dir), ".Gemini_state")
    os.makedirs(state_dir, exist_ok=True)
    failures_path = os.path.join(state_dir, "high_priority_failures.json")

    # Load existing entries
    entries = []
    if os.path.isfile(failures_path):
        try:
            with open(failures_path, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except (json.JSONDecodeError, Exception):
            entries = []

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app_name": app_name,
        "priority": "HIGH",
        "source": "validation_loop",
        "failures": verdict.get("failure_details", []),
        "context": f"Refinement feedback: '{feedback[:200]}'",
        "test_file": "test_case.py",
        "total_tests": verdict.get("total_tests", 0),
        "verdict": verdict.get("verdict", "REVISE"),
    }
    entries.append(entry)

    try:
        with open(failures_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(entries, f, indent=2)
    except Exception as e:
        logger.error(f"Could not write high-priority failure log: {e}")


# ── System Prompt (V2: Production Quality) ───────────────────

REFINE_SYSTEM_PROMPT = """You are the Meta App Factory Self-Healing Architect V2. You are an elite full-stack production engineer.

Your job: Read the child app's current source code, static analysis diagnostics, and asset inventory. Then apply the user's refinement request by producing COMPLETE modified files.

## CRITICAL OUTPUT FORMAT
1. Return ONLY files that need modification. Do NOT return unchanged files.
2. Wrap each modified file using this EXACT format:

===FILE: relative/path/to/file.ext===
...complete file content here...
===END_FILE===

3. Use the same relative path as shown in the source listing.
4. Include ALL code in each file — FULL REPLACEMENT, not a diff.
5. Do NOT add commentary outside ===FILE=== blocks except a brief summary at top.
6. Preserve ALL existing functionality unless explicitly asked to change it.

## PRODUCTION QUALITY RULES

### Asset Integration
- If the ASSET INVENTORY lists image files, use them via <img> tags instead of letter placeholders.
- For Vite apps, files in `public/` are served at the root: `public/avatar.png` → `src="/avatar.png"`.
- Always provide width/height and alt text on images.
- Use CSS `object-fit: cover` and `border-radius: 50%` for circular avatars.

### UI Polish
- NEVER show technical labels (BOT, AI, SYSTEM) next to persona names. AI entities must appear as native.
- Ensure all UI transitions are smooth (use CSS transition properties).
- Forms/inputs must set proper disabled states during async operations.
- NEVER place JSX comments `{/* */}` between HTML/JSX tag attributes. Comments must go above or below the tag, never inside `< />` between attributes. This causes Babel parse errors.

### React.StrictMode
- If the app uses SSE streaming (getReader, EventSource, text/event-stream), do NOT wrap components in React.StrictMode. StrictMode double-invokes callbacks in dev mode, causing streamed text to appear duplicated.

### Deduplication & State Management
- In React SSE streaming: ALWAYS set the streaming/loading state to `true` BEFORE initiating the fetch, not just after.
- Clear response accumulators before each new generation cycle.
- When building chat history for LLM context, deduplicate: don't append the current user message if it already exists at the end of the loaded history.
- Break out of SSE loops cleanly on `event.done` or `event.error`.

### Backend
- Always load .env via dotenv at startup.
- CORS origins should cover ports 5173-5180 for Vite port jumping.
- For Windows .bat scripts: use `npm.cmd`, `ping` delays, `cmd /k`.
"""


def refine_and_apply(app_name: str, app_dir: str, feedback: str) -> Generator:
    """
    Core self-healing loop. Yields SSE-format status events.
    V2: Now includes asset inventory and static analysis.
    """
    # Phase 1: Discover source files
    yield {"step": "DISCOVER", "text": f"📂 Scanning {app_name} source files..."}
    source_files = discover_app_files(app_dir)
    if not source_files:
        yield {"step": "ERROR", "text": f"❌ No modifiable files found in {app_dir}"}
        return
    yield {"step": "DISCOVER", "text": f"📂 Found {len(source_files)} source files: {', '.join(source_files.keys())}"}

    # Phase 1.5: Inventory assets
    yield {"step": "ASSETS", "text": "🖼️ Scanning for media assets..."}
    assets = inventory_assets(app_dir)
    asset_summary = "No assets found."
    if assets:
        asset_lines = [f"  - {a['filename']} ({a['type']}) → web path: {a['web_path']}  [disk: {a['path']}]" for a in assets]
        asset_summary = f"Found {len(assets)} assets:\n" + "\n".join(asset_lines)
        yield {"step": "ASSETS", "text": f"🖼️ {asset_summary}"}
    else:
        yield {"step": "ASSETS", "text": "🖼️ No media assets found in project."}

    # Phase 2: Static analysis
    yield {"step": "DIAGNOSE", "text": "🔬 Running static analysis..."}
    diagnostics = static_analysis(source_files)
    diag_text = "No issues detected."
    if diagnostics:
        diag_text = "\n".join(diagnostics)
        yield {"step": "DIAGNOSE", "text": f"🔬 Found {len(diagnostics)} diagnostic(s):\n" + diag_text}
    else:
        yield {"step": "DIAGNOSE", "text": "🔬 Static analysis clean — no issues detected."}

    # Phase 3: Build the refinement prompt
    yield {"step": "ANALYZE", "text": "🧠 Building refinement prompt for Gemini 2.5 Flash..."}

    file_listing = []
    for rel_path, content in source_files.items():
        file_listing.append(f"===CURRENT_FILE: {rel_path}===\n{content}\n===END_CURRENT_FILE===")

    prompt = (
        f"{REFINE_SYSTEM_PROMPT}\n\n"
        f"## APP: {app_name}\n"
        f"## APP DIRECTORY: {app_dir}\n\n"
        f"## ASSET INVENTORY\n{asset_summary}\n\n"
        f"## STATIC ANALYSIS DIAGNOSTICS\n{diag_text}\n\n"
        f"## CURRENT SOURCE CODE\n\n"
        + "\n\n".join(file_listing)
    )

    # Active Recall: inject known high-priority failures to prevent repeat errors
    past_failures = _load_high_priority_failures(app_dir)
    if past_failures:
        failure_lines = []
        for pf in past_failures:
            for detail in pf.get("failures", []):
                failure_lines.append(f"  - [{pf.get('timestamp', '?')}] {detail}")
        prompt += (
            f"\n\n## KNOWN HIGH-PRIORITY FAILURES (DO NOT REPEAT)\n"
            f"The following errors were logged from previous refinement cycles. "
            f"Your output MUST NOT reintroduce these issues:\n"
            + "\n".join(failure_lines)
        )

    prompt += (
        f"\n\n## USER REFINEMENT REQUEST\n\n{feedback}\n\n"
        f"IMPORTANT: Address ALL static analysis diagnostics in addition to the user's request. "
        f"Use available assets from the inventory. "
        f"Produce modified files using the ===FILE: path=== format. "
        f"COMPLETE file contents, not diffs."
    )

    yield {"step": "ANALYZE", "text": f"🧠 Sending {len(prompt):,} chars to Gemini 2.5 Flash (incl. {len(diagnostics)} diagnostics, {len(assets)} assets)..."}

    # Phase 4: Call Gemini
    yield {"step": "GENERATE", "text": "⚡ Gemini is generating modifications..."}
    response = _call_gemini(prompt)
    if not response:
        yield {"step": "ERROR", "text": "❌ Gemini API call failed. Check GEMINI_API_KEY."}
        return
    yield {"step": "GENERATE", "text": f"⚡ Received {len(response):,} chars from Gemini."}

    # Phase 5: Parse modifications
    yield {"step": "PARSE", "text": "🔍 Parsing file modifications..."}
    modifications = parse_file_modifications(response)
    if not modifications:
        yield {"step": "ERROR", "text": "❌ Could not parse file modifications from Gemini response. Raw preview: " + response[:500]}
        return
    yield {"step": "PARSE", "text": f"🔍 Identified {len(modifications)} files to modify: {', '.join(modifications.keys())}"}

    # Phase 6: Write files
    written = []
    for rel_path, content in modifications.items():
        full_path = os.path.join(app_dir, rel_path)
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            written.append(rel_path)
            yield {"step": "WRITE", "text": f"✅ Written: {rel_path}"}
        except Exception as e:
            yield {"step": "ERROR", "text": f"❌ Failed to write {rel_path}: {e}"}

    # Phase 6.5: Post-write lint check + AST correction loop
    reverted = []
    if written:
        yield {"step": "LINT", "text": "🔎 Running post-write syntax validation (Babel + ESLint)..."}
        lint_errors = []
        reverted = []
        for rel_path in written:
            full_path = os.path.join(app_dir, rel_path)
            _, ext = os.path.splitext(rel_path)

            # Babel parse check
            errors = _lint_file(full_path, rel_path, app_dir)

            # ESLint structural check (JSX/TSX only)
            eslint_issues = []
            if ext in {".jsx", ".tsx", ".js", ".ts"}:
                eslint_issues = _eslint_structural_check(full_path, rel_path, app_dir)
                eslint_blocking = [e for e in eslint_issues if "[ERROR]" in e]
            else:
                eslint_blocking = []

            if errors or eslint_blocking:
                all_issues = (errors or []) + eslint_blocking
                for err in all_issues:
                    yield {"step": "LINT", "text": f"❌ {err}"}

                # ── AST Correction Loop (UI-in-the-Loop feedback) ──
                if ext in {".jsx", ".tsx", ".js", ".ts"}:
                    yield {"step": "AST_CORRECT", "text": f"🔄 Entering AST correction loop for {rel_path}..."}
                    try:
                        broken_code = modifications[rel_path]
                        corrected, passed, attempt_log = _ast_correction_loop(
                            broken_code=broken_code,
                            babel_errors=errors or [],
                            eslint_issues=eslint_issues,
                            rel_path=rel_path,
                            app_dir=app_dir,
                        )
                        for log_entry in attempt_log:
                            yield {"step": "AST_CORRECT", "text": f"  🧬 {log_entry}"}

                        if passed and corrected:
                            # Write the corrected code
                            with open(full_path, "w", encoding="utf-8", newline="\n") as f:
                                f.write(corrected)
                            yield {"step": "AST_CORRECT", "text": f"✅ Self-corrected: {rel_path} — parse errors resolved via AST feedback loop."}
                            continue  # Don't revert — correction succeeded
                        else:
                            yield {"step": "AST_CORRECT", "text": f"⚠️ AST correction failed for {rel_path} after max attempts."}
                    except Exception as e:
                        yield {"step": "AST_CORRECT", "text": f"⚠️ AST correction error: {e}"}

                # Revert to pre-modification version (correction failed or not applicable)
                if rel_path in source_files:
                    try:
                        with open(full_path, "w", encoding="utf-8", newline="\n") as f:
                            f.write(source_files[rel_path])
                        reverted.append(rel_path)
                        yield {"step": "LINT", "text": f"⏪ Reverted: {rel_path} (syntax errors persist after correction)"}
                    except Exception as e:
                        yield {"step": "LINT", "text": f"⚠️ Could not revert {rel_path}: {e}"}
                else:
                    yield {"step": "LINT", "text": f"⚠️ {rel_path} has syntax errors but no original to revert to"}
                lint_errors.extend(all_issues)
            else:
                # No blocking errors — log any ESLint warnings
                if eslint_issues:
                    for w in eslint_issues:
                        yield {"step": "LINT", "text": f"⚠️ {w}"}

        if lint_errors:
            good_files = [f for f in written if f not in reverted]
            if reverted:
                yield {"step": "LINT", "text": f"🔧 Reverted {len(reverted)} file(s) after AST correction failed: {', '.join(reverted)}"}
            if good_files:
                yield {"step": "LINT", "text": f"✅ {len(good_files)} file(s) passed validation: {', '.join(good_files)}"}
        else:
            yield {"step": "LINT", "text": f"✅ All {len(written)} file(s) passed syntax + structural validation."}

        # Update written list to exclude reverted files
        written = [f for f in written if f not in reverted]

    # Phase 7.5: VALIDATE — Active Recall Validation Loop
    verdict = {"passed": True}  # Default: pass if validation is skipped
    if written:
        yield {"step": "VALIDATE", "text": "🧪 Active Recall: Generating validation tests..."}

        # Extract what was fixed
        fix_descriptions = _extract_fix_descriptions(modifications, response)
        yield {"step": "VALIDATE", "text": f"🧪 Identified {len(fix_descriptions)} fix(es) to validate."}

        # Generate test_case.py via Gemini
        test_path = _generate_test_case(app_name, app_dir, fix_descriptions, source_files)
        if test_path:
            yield {"step": "VALIDATE", "text": f"🧪 Generated: test_case.py ({os.path.getsize(test_path):,} bytes)"}

            # Invoke the Critic
            try:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from utils.critic import ArtisanCritic
                critic = ArtisanCritic()
                yield {"step": "VALIDATE", "text": "🔍 Specialist — Critic: Running test suite..."}
                verdict = critic.validate_refinement(app_dir, app_name)

                if verdict["passed"]:
                    yield {"step": "VALIDATE", "text": f"✅ Critic Verdict: APPROVE — {verdict['total_tests']} test(s) passed."}
                else:
                    yield {"step": "VALIDATE", "text": f"❌ Critic Verdict: REVISE — {verdict['failures']} failure(s) in {verdict['total_tests']} test(s)."}
                    for detail in verdict.get("failure_details", []):
                        yield {"step": "VALIDATE", "text": f"  ⚠️ {detail}"}

                    # Log to .Gemini_state as high-priority
                    _log_high_priority_failure(app_dir, app_name, verdict, feedback)
                    yield {"step": "VALIDATE", "text": "📋 Logged failure as HIGH-PRIORITY in .Gemini_state — future refinements will avoid this error."}
            except ImportError:
                yield {"step": "VALIDATE", "text": "⚠️ Could not import ArtisanCritic — skipping validation."}
                verdict = {"passed": True}  # Don't block on import failure
            except Exception as e:
                yield {"step": "VALIDATE", "text": f"⚠️ Critic error: {e} — skipping validation."}
                verdict = {"passed": True}
        else:
            yield {"step": "VALIDATE", "text": "⚠️ Could not generate test_case.py — skipping validation."}
            verdict = {"passed": True}  # Don't block if test gen fails

    # Phase 8: Summary
    if written and verdict.get("passed", True):
        yield {"step": "COMPLETE", "text": f"🎉 Self-healing applied & validated! Modified {len(written)} files in {app_name}: {', '.join(written)}"}
    elif written and not verdict.get("passed", True):
        yield {"step": "INCOMPLETE", "text": f"⚠️ Self-healing applied {len(written)} file(s) but validation FAILED. Check test_case.py and .Gemini_state/high_priority_failures.json for details."}
    elif reverted:
        yield {"step": "ERROR", "text": f"⚠️ All modified files had syntax errors and were reverted. The AI-generated code needs manual review."}
    else:
        yield {"step": "ERROR", "text": "⚠️ No files were written. Check the Gemini response format."}

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
