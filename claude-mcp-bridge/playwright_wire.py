"""
Playwright Wire — Phase 6 ClaudeAY Autonomy
---------------------------------------------
Headless Chromium browser automation with the same safety model as shell_wire/git_wire.

Safety model:
  - URL allowlist: only APPROVED_URL_PREFIXES accepted; everything else blocked.
  - Evaluate blocklist: cookie/localStorage/fetch scripts refused before execution.
  - Session TTL: sessions auto-closed after SESSION_TTL seconds.
  - Zombie prevention (Gemini Patch): atexit + SIGTERM/SIGINT cleanup.
  - Per-session threading.Lock: prevents concurrent page mutations.
    (threading.Lock used instead of asyncio.Lock so sessions persist across
    asyncio.run() call boundaries in the sync execute() path.)
  - Audit log: logs/playwright_wire_audit.jsonl.

Served on both planes:
  - MCP plane  : playwright_operation tool in mcp_server/server.py
                 (calls execute_async — runs execute() in executor)
  - Gemini plane: playwright_operation() in ay_client.py
                 (calls execute() sync directly)

Linux note: requires 'playwright install-deps chromium' on headless Ubuntu VPS
for OS-level shared libraries (libnss3, libgbm1, etc.).
"""

import atexit
import asyncio
import json
import logging
import os
import signal
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

log = logging.getLogger("PlaywrightWire")

MAF_ROOT       = Path(__file__).parent.parent.resolve()
AUDIT_LOG      = Path(__file__).parent / "logs" / "playwright_wire_audit.jsonl"
SCREENSHOT_DIR = Path(__file__).parent / "logs" / "playwright_screenshots"
SESSION_TTL    = 300  # seconds — auto-close after this

APPROVED_URL_PREFIXES: list[str] = [
    "http://localhost",
    "http://127.0.0.1",
    "http://68.183.30.128",
    "http://104.248.233.220",
    "http://localhost:5173",
    "http://localhost:5175",
    "http://localhost:8000",
    "http://localhost:5000",
]

_BLOCKED_SCRIPT_PATTERNS: list[str] = [
    "document.cookie",
    "localStorage",
    "sessionStorage",
    "fetch(",
    "XMLHttpRequest",
    "eval(",
]


# ── Session store ─────────────────────────────────────────────────────────────
# Each entry: {pw, browser, page, lock, created_at, console_errors, network_errors}

_SESSIONS: dict[str, dict] = {}
_SESSIONS_LOCK = threading.Lock()  # protects _SESSIONS dict mutations


# ── Zombie prevention (Gemini Patch) ──────────────────────────────────────────

def _cleanup_all_sessions() -> None:
    """Close all active browser sessions. Called by atexit and signal handlers."""
    with _SESSIONS_LOCK:
        if not _SESSIONS:
            return
        for _sid, session in list(_SESSIONS.items()):
            try:
                session["browser"].close()
            except Exception:
                pass
            try:
                session["pw"].stop()
            except Exception:
                pass
        _SESSIONS.clear()
    _audit({"event": "cleanup_all_sessions"})


def _signal_cleanup(signum, frame) -> None:
    _cleanup_all_sessions()
    sys.exit(0)


atexit.register(_cleanup_all_sessions)
if threading.current_thread() is threading.main_thread():
    try:
        signal.signal(signal.SIGTERM, _signal_cleanup)
        signal.signal(signal.SIGINT, _signal_cleanup)
    except (AttributeError, OSError, ValueError):
        pass  # Not all signals available on all platforms or interpreter contexts


# ── Audit ─────────────────────────────────────────────────────────────────────

def _audit(entry: dict) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Result factories ──────────────────────────────────────────────────────────

def _blocked_result(operation: str, reason: str) -> dict:
    _audit({"event": "blocked", "operation": operation, "reason": reason})
    return {
        "stdout":          "",
        "stderr":          "",
        "exit_code":       -1,
        "duration_ms":     0,
        "timed_out":       False,
        "blocked":         True,
        "block_reason":    reason,
        "operation":       operation,
        "screenshot_path": None,
        "console_errors":  [],
        "network_errors":  [],
        "session_id":      None,
    }


# ── Safety checks ─────────────────────────────────────────────────────────────

def _check_url(url: str) -> str | None:
    if not any(url.startswith(p) for p in APPROVED_URL_PREFIXES):
        return "unapproved URL"
    return None


def _check_script(script: str) -> str | None:
    for pattern in _BLOCKED_SCRIPT_PATTERNS:
        if pattern in script:
            return f"forbidden script pattern: {pattern!r}"
    return None


# ── Session management ────────────────────────────────────────────────────────

def _expire_old_sessions() -> None:
    """Must be called with _SESSIONS_LOCK held."""
    now = time.monotonic()
    expired = [
        sid for sid, s in _SESSIONS.items()
        if now - s["created_at"] > SESSION_TTL
    ]
    for sid in expired:
        try:
            _SESSIONS[sid]["browser"].close()
        except Exception:
            pass
        try:
            _SESSIONS[sid]["pw"].stop()
        except Exception:
            pass
        del _SESSIONS[sid]
        _audit({"event": "session_expired", "session_id": sid})


def _get_or_create_session(session_id: str | None) -> tuple[str, dict]:
    """
    Returns (session_id, session_data).
    Reuses existing session if session_id given and alive; creates new otherwise.
    Callers must acquire session["lock"] before touching page/browser.
    """
    from playwright.sync_api import sync_playwright

    with _SESSIONS_LOCK:
        _expire_old_sessions()

        if session_id and session_id in _SESSIONS:
            return session_id, _SESSIONS[session_id]

        pw = sync_playwright().start()
        try:
            browser = pw.chromium.launch(headless=True)
            page    = browser.new_page()
        except Exception:
            # A started-but-unstopped sync_playwright leaves its event loop
            # registered as "running" in this thread, which makes every later
            # sync_playwright().start() here fail with the misleading
            # "Sync API inside the asyncio loop" error. Stop it before re-raising.
            try:
                pw.stop()
            except Exception:
                pass
            raise

        console_errors: list[dict] = []
        network_errors: list[dict] = []

        def _on_console(msg) -> None:
            if msg.type == "error":
                console_errors.append({"type": msg.type, "text": msg.text})

        def _on_response(resp) -> None:
            if resp.status >= 400:
                network_errors.append({"url": resp.url, "status": resp.status})

        page.on("console", _on_console)
        page.on("response", _on_response)

        new_id  = session_id or str(uuid.uuid4())
        session = {
            "pw":             pw,
            "browser":        browser,
            "page":           page,
            "lock":           threading.Lock(),
            "created_at":     time.monotonic(),
            "console_errors": console_errors,
            "network_errors": network_errors,
        }
        _SESSIONS[new_id] = session
        _audit({"event": "session_created", "session_id": new_id})
        return new_id, session


# ── Core execute() ────────────────────────────────────────────────────────────

def execute(request: dict) -> dict:
    """
    Execute a single Playwright browser operation.

    Supported operations: navigate, screenshot, click, fill, select, get_text,
    get_console, get_network, wait, evaluate, get_computed_style, close.

    Returns the standard wire response envelope.
    """
    operation    = (request.get("operation") or "").strip()
    url          = (request.get("url") or "").strip()
    selector     = (request.get("selector") or "").strip()
    text         = (request.get("text") or "").strip()
    value        = (request.get("value") or "").strip()
    script       = (request.get("script") or "").strip()
    css_property = (request.get("css_property") or "").strip()
    timeout_ms   = int(request.get("timeout_ms") or 5000)
    session_id   = (request.get("session_id") or "").strip() or None
    name         = (request.get("name") or "").strip()

    start = time.monotonic()

    if not operation:
        return _blocked_result("", "operation is required")

    # ── URL allowlist ─────────────────────────────────────────────────────────
    if operation == "navigate":
        if not url:
            return _blocked_result(operation, "url is required for navigate")
        block = _check_url(url)
        if block:
            return _blocked_result(operation, block)

    # ── Script blocklist ──────────────────────────────────────────────────────
    if operation == "evaluate":
        block = _check_script(script)
        if block:
            return _blocked_result(operation, block)

    # ── Session ───────────────────────────────────────────────────────────────
    try:
        sid, session = _get_or_create_session(session_id)
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        log.error("[PW_WIRE] session init failed: %s", exc)
        _audit({"event": "session_error", "operation": operation, "error": str(exc)})
        return {
            "stdout":          "",
            "stderr":          str(exc),
            "exit_code":       -2,
            "duration_ms":     duration_ms,
            "timed_out":       False,
            "blocked":         False,
            "block_reason":    None,
            "operation":       operation,
            "screenshot_path": None,
            "console_errors":  [],
            "network_errors":  [],
            "session_id":      session_id,
        }

    _audit({"event": "execute", "operation": operation,
            "session_id": sid, "url": url or None})

    # ── Close: handled separately — no page operations, no session lock ───────
    if operation == "close":
        with _SESSIONS_LOCK:
            if sid in _SESSIONS:
                try:
                    session["browser"].close()
                except Exception:
                    pass
                try:
                    session["pw"].stop()
                except Exception:
                    pass
                _SESSIONS.pop(sid, None)
        _audit({"event": "session_closed", "session_id": sid})
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "stdout":          "",
            "stderr":          "",
            "exit_code":       0,
            "duration_ms":     duration_ms,
            "timed_out":       False,
            "blocked":         False,
            "block_reason":    None,
            "operation":       operation,
            "screenshot_path": None,
            "console_errors":  [],
            "network_errors":  [],
            "session_id":      sid,
        }

    page            = session["page"]
    stdout          = ""
    stderr          = ""
    exit_code       = 0
    timed_out       = False
    screenshot_path = None

    with session["lock"]:
        try:
            if operation == "navigate":
                page.goto(url, timeout=timeout_ms)

            elif operation == "screenshot":
                SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
                ts    = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                fname = f"{ts}_{name}.png" if name else f"{ts}.png"
                path  = str(SCREENSHOT_DIR / fname)
                page.screenshot(path=path, full_page=True)
                screenshot_path = path
                stdout = path

            elif operation == "click":
                target = f"text={text}" if text else selector
                if not target:
                    raise ValueError("click requires selector or text")
                page.click(target, timeout=timeout_ms)

            elif operation == "fill":
                if not selector:
                    raise ValueError("fill requires selector")
                page.fill(selector, value, timeout=timeout_ms)

            elif operation == "select":
                if not selector:
                    raise ValueError("select requires selector")
                page.select_option(selector, value=value, timeout=timeout_ms)

            elif operation == "get_text":
                if not selector:
                    raise ValueError("get_text requires selector")
                stdout = page.inner_text(selector, timeout=timeout_ms)

            elif operation == "get_console":
                stdout = json.dumps(session["console_errors"])

            elif operation == "get_network":
                stdout = json.dumps(session["network_errors"])

            elif operation == "wait":
                if not selector:
                    raise ValueError("wait requires selector")
                page.wait_for_selector(selector, timeout=timeout_ms)

            elif operation == "evaluate":
                if not script:
                    raise ValueError("evaluate requires script")
                result = page.evaluate(script)
                stdout = json.dumps(result) if result is not None else ""

            elif operation == "get_computed_style":
                if not selector or not css_property:
                    raise ValueError("get_computed_style requires selector and css_property")
                # Args passed as JSON — no string interpolation into JS, no injection risk
                result = page.evaluate(
                    """([sel, prop]) => {
                        const el = document.querySelector(sel);
                        if (!el) return null;
                        return window.getComputedStyle(el).getPropertyValue(prop);
                    }""",
                    [selector, css_property],
                )
                stdout = str(result) if result is not None else ""

            else:
                return _blocked_result(operation, f"unsupported operation: {operation!r}")

        except Exception as exc:
            err_str = str(exc)
            stderr  = err_str
            if "timeout" in err_str.lower() or "timed out" in err_str.lower():
                timed_out = True
                exit_code = -1
            else:
                exit_code = -2
            log.warning("[PW_WIRE] op=%s error: %s", operation, err_str[:200])

    duration_ms = int((time.monotonic() - start) * 1000)
    log.info("[PW_WIRE] op=%s exit=%d dur=%dms session=%s",
             operation, exit_code, duration_ms, sid)
    _audit({"event": "result", "operation": operation,
            "exit_code": exit_code, "duration_ms": duration_ms, "session_id": sid})

    return {
        "stdout":          stdout,
        "stderr":          stderr,
        "exit_code":       exit_code,
        "duration_ms":     duration_ms,
        "timed_out":       timed_out,
        "blocked":         False,
        "block_reason":    None,
        "operation":       operation,
        "screenshot_path": screenshot_path,
        "console_errors":  session.get("console_errors", []),
        "network_errors":  session.get("network_errors", []),
        "session_id":      sid,
    }


# ── Async wrapper (primary for MCP plane) ─────────────────────────────────────

async def execute_async(request: dict) -> dict:
    """
    Async primary for mcp_server/server.py. Delegates to execute() via executor
    so the MCP event loop stays unblocked during browser I/O.
    Per-session threading.Lock inside execute() provides concurrency safety.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: execute(request))


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import urllib.request as _urllib

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    PRIMARY_URL  = "http://68.183.30.128"
    FALLBACK_URL = "http://localhost:5175"

    try:
        _urllib.urlopen(PRIMARY_URL, timeout=3)
        TEST_URL = PRIMARY_URL
    except Exception:
        TEST_URL = FALLBACK_URL

    print(f"=== Playwright Wire Smoke Test ===")
    print(f"    Target URL : {TEST_URL}\n")

    passed = failed = 0

    def _check(label: str, result: dict, expect_blocked: bool = False,
               expect_exit_code: int = 0) -> None:
        global passed, failed
        is_blocked = result.get("blocked", False)
        exit_code  = result.get("exit_code", -99)
        ok = (
            (is_blocked == expect_blocked) and
            (expect_blocked or exit_code == expect_exit_code)
        )
        status = "PASS" if ok else "FAIL"
        if is_blocked:
            note = f"[BLOCKED: {result.get('block_reason')}]"
        else:
            note = f"[exit={exit_code} stdout={str(result.get('stdout', ''))[:60]}]"
        print(f"  [{status}] {note}  {label}")
        if ok:
            passed += 1
        else:
            failed += 1
            if result.get("stderr"):
                print(f"         stderr: {result['stderr'][:120]}")

    # ── Case 1: navigate ──────────────────────────────────────────────────────
    r1 = execute({"operation": "navigate", "url": TEST_URL, "timeout_ms": 15000})
    first_sid = r1.get("session_id")
    _check("navigate to approved URL", r1, expect_blocked=False, expect_exit_code=0)

    # ── Case 2: screenshot ────────────────────────────────────────────────────
    r2 = execute({"operation": "screenshot", "session_id": first_sid, "name": "smoke"})
    ok2 = (not r2["blocked"] and r2["exit_code"] == 0 and
           r2.get("screenshot_path") and Path(r2["screenshot_path"]).exists())
    status2 = "PASS" if ok2 else "FAIL"
    print(f"  [{status2}] [screenshot_path={r2.get('screenshot_path')}]  screenshot saved")
    if ok2:
        passed += 1
    else:
        failed += 1

    # ── Case 3: get_console ───────────────────────────────────────────────────
    r3 = execute({"operation": "get_console", "session_id": first_sid})
    try:
        _parsed = json.loads(r3.get("stdout") or "[]")
        ok3 = not r3["blocked"] and r3["exit_code"] == 0 and isinstance(_parsed, list)
    except Exception:
        ok3 = False
    status3 = "PASS" if ok3 else "FAIL"
    print(f"  [{status3}] [console={r3.get('stdout', '')[:60]}]  get_console returns list")
    if ok3:
        passed += 1
    else:
        failed += 1

    # ── Case 4: get_computed_style ────────────────────────────────────────────
    r4 = execute({"operation": "get_computed_style", "session_id": first_sid,
                  "selector": "body", "css_property": "display"})
    ok4 = (not r4["blocked"] and r4["exit_code"] == 0 and
           isinstance(r4.get("stdout"), str) and len(r4.get("stdout", "")) > 0)
    status4 = "PASS" if ok4 else "FAIL"
    print(f"  [{status4}] [display={r4.get('stdout')}]  get_computed_style returns CSS value")
    if ok4:
        passed += 1
    else:
        failed += 1

    # ── Case 5: blocked URL ───────────────────────────────────────────────────
    r5 = execute({"operation": "navigate", "url": "http://evil.com"})
    _check("blocked URL -> evil.com", r5, expect_blocked=True)

    # ── Case 6: blocked evaluate script ──────────────────────────────────────
    r6 = execute({"operation": "evaluate", "session_id": first_sid,
                  "script": "return document.cookie"})
    _check("blocked evaluate -> document.cookie", r6, expect_blocked=True)

    # ── Case 7: session reuse ─────────────────────────────────────────────────
    r7 = execute({"operation": "navigate", "url": TEST_URL,
                  "session_id": first_sid, "timeout_ms": 15000})
    ok7 = (not r7["blocked"] and r7["exit_code"] == 0 and
           r7.get("session_id") == first_sid)
    status7 = "PASS" if ok7 else "FAIL"
    print(f"  [{status7}] [session_id={r7.get('session_id')}]  session reuse — same UUID")
    if ok7:
        passed += 1
    else:
        failed += 1

    # Cleanup
    execute({"operation": "close", "session_id": first_sid})

    print(f"\n{passed}/{passed + failed} passed")
    if failed:
        sys.exit(1)
