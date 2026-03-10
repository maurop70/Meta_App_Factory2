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
import requests
import re
import subprocess
import shutil
from typing import Generator, Dict, List, Optional, Tuple

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
    """Non-streaming Gemini call. Returns complete text response."""
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        return None

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": max_tokens,
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=300)
        if resp.status_code != 200:
            logger.error(f"Gemini error: {resp.status_code} {resp.text[:200]}")
            return None
        data = resp.json()
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
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
    tag_attr_comment = re.compile(
        r'<\w[^>]*\{/\*.*?\*/\}[^>]*(?:/>|>)',
        re.DOTALL
    )
    for i, line in enumerate(lines, 1):
        # Simpler per-line check: attribute-like context followed by {/* */}
        if re.search(r'=\{[^}]*\}\s*\{/\*', line):
            errors.append(
                f"{rel_path}:{i}: JSX comment inside tag attribute list — "
                f"'{{/* ... */}}' cannot appear between attributes. Move the comment above or below the tag."
            )

    # 3. Unclosed template literals (common Gemini mistake)
    backtick_count = content.count("`")
    if backtick_count % 2 != 0:
        errors.append(f"{rel_path}: Odd number of backticks ({backtick_count}) — likely an unclosed template literal")

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
        + f"\n\n## USER REFINEMENT REQUEST\n\n{feedback}\n\n"
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

    # Phase 6.5: Post-write lint check
    reverted = []
    if written:
        yield {"step": "LINT", "text": "🔎 Running post-write syntax validation..."}
        lint_errors = []
        reverted = []
        for rel_path in written:
            full_path = os.path.join(app_dir, rel_path)
            errors = _lint_file(full_path, rel_path, app_dir)
            if errors:
                lint_errors.extend(errors)
                # Revert to pre-modification version if we have it
                if rel_path in source_files:
                    try:
                        with open(full_path, "w", encoding="utf-8", newline="\n") as f:
                            f.write(source_files[rel_path])
                        reverted.append(rel_path)
                        yield {"step": "LINT", "text": f"⏪ Reverted: {rel_path} (syntax errors detected)"}
                    except Exception as e:
                        yield {"step": "LINT", "text": f"⚠️ Could not revert {rel_path}: {e}"}
                else:
                    yield {"step": "LINT", "text": f"⚠️ {rel_path} has syntax errors but no original to revert to"}

        if lint_errors:
            for err in lint_errors:
                yield {"step": "LINT", "text": f"❌ {err}"}
            good_files = [f for f in written if f not in reverted]
            if reverted:
                yield {"step": "LINT", "text": f"🔧 Reverted {len(reverted)} file(s) with syntax errors: {', '.join(reverted)}"}
            if good_files:
                yield {"step": "LINT", "text": f"✅ {len(good_files)} file(s) passed validation: {', '.join(good_files)}"}
        else:
            yield {"step": "LINT", "text": f"✅ All {len(written)} file(s) passed syntax validation."}

        # Update written list to exclude reverted files
        written = [f for f in written if f not in reverted]

    # Phase 7: Summary
    if written:
        yield {"step": "COMPLETE", "text": f"🎉 Self-healing applied! Modified {len(written)} files in {app_name}: {', '.join(written)}"}
    elif reverted:
        yield {"step": "ERROR", "text": f"⚠️ All modified files had syntax errors and were reverted. The AI-generated code needs manual review."}
    else:
        yield {"step": "ERROR", "text": "⚠️ No files were written. Check the Gemini response format."}
