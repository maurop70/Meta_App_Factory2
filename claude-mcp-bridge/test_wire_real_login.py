"""
Hard verification for the QA Lab Playwright path.

Simulates the uvicorn context exactly: the MAIN thread runs a live asyncio
loop while a background threading.Thread (like _run_qa_background) drives
playwright_wire against the real MWO ERP login at http://68.183.30.128.

Bar: navigate -> fill employee id + PIN -> click submit -> authenticated
page renders real content, with zero sync-in-asyncio errors.
"""

import asyncio
import sys
import threading

BASE_URL = "http://68.183.30.128"
EMPLOYEE_ID = "ERP-1000"  # ADMIN
PIN = "1234"

result: dict = {"ok": False, "steps": []}


def step(name: str, res: dict) -> bool:
    ok = res.get("exit_code") == 0 and not res.get("blocked")
    result["steps"].append(
        f"{'PASS' if ok else 'FAIL'} {name}"
        + ("" if ok else f" :: {res.get('stderr', '')[:120]}")
    )
    return ok


def qa_thread() -> None:
    from playwright_wire import execute

    sid = "real-login-verify"
    try:
        if not step("navigate login", execute({
            "operation": "navigate", "url": BASE_URL,
            "session_id": sid, "timeout_ms": 20000,
        })):
            return

        execute({"operation": "wait", "selector": "input",
                 "session_id": sid, "timeout_ms": 10000})

        inputs_res = execute({
            "operation": "evaluate",
            "script": "document.querySelectorAll('input').length",
            "session_id": sid,
        })
        step(f"login form inputs found ({inputs_res.get('stdout')})", inputs_res)

        filled = execute({
            "operation": "evaluate",
            "script": (
                "(() => {"
                "  const ins = Array.from(document.querySelectorAll('input'));"
                "  if (ins.length < 2) return 'not enough inputs';"
                "  const setVal = (el, v) => {"
                "    const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;"
                "    s.call(el, v);"
                "    el.dispatchEvent(new Event('input', {bubbles: true}));"
                "  };"
                f"  setVal(ins[ins.length - 2], '{EMPLOYEE_ID}');"
                f"  setVal(ins[ins.length - 1], '{PIN}');"
                "  return 'filled';"
                "})()"
            ),
            "session_id": sid,
        })
        if not step(f"fill credentials ({filled.get('stdout')})", filled):
            return

        if not step("click submit", execute({
            "operation": "evaluate",
            "script": (
                "(() => {"
                "  const btn = Array.from(document.querySelectorAll('button'))"
                "    .find(b => /login|sign in|submit/i.test(b.textContent)) "
                "    || document.querySelector('button[type=submit], button');"
                "  if (!btn) return 'no button';"
                "  btn.click();"
                "  return 'clicked ' + btn.textContent.trim();"
                "})()"
            ),
            "session_id": sid,
        })):
            return

        execute({"operation": "wait", "selector": "body",
                 "session_id": sid, "timeout_ms": 5000})
        import time as _t
        _t.sleep(3)

        page_text = execute({
            "operation": "evaluate",
            "script": "document.body.innerText.slice(0, 600)",
            "session_id": sid,
        })
        body = page_text.get("stdout", "")
        step("read authenticated page", page_text)

        on_login = "PIN" in body and "Employee" in body and "Logout" not in body
        has_content = len(body) > 50
        result["page_excerpt"] = body[:400]
        result["ok"] = has_content and not on_login

    finally:
        execute({"operation": "close", "session_id": sid})


async def main() -> None:
    # Live asyncio loop in the main thread, like uvicorn's
    t = threading.Thread(target=qa_thread, daemon=True)
    t.start()
    while t.is_alive():
        await asyncio.sleep(0.2)


if __name__ == "__main__":
    asyncio.run(main())
    print("\n".join(result["steps"]))
    print("--- page excerpt ---")
    print(result.get("page_excerpt", "(none)"))
    print("RESULT:", "PASS" if result["ok"] else "FAIL")
    sys.exit(0 if result["ok"] else 1)
