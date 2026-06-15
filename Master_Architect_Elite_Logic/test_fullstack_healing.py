"""test_fullstack_healing.py — Phase 4 full-stack build / run / self-heal suite.

NEW suite (does not mutate existing regression suites). Verifies the live Phase 4
machinery in `preview_manager.py` + `mock_antigravity.py` + `verify_app.mjs`:

  • PYTHONUNBUFFERED is injected into spawned dev-server env (immediate tracebacks)
  • dynamic port allocation avoids reserved/unsafe ports and binds loopback only
  • the actuator scaffolds a full-stack app and JUNCTIONS node_modules (no slow copy)
  • the concurrency cap and idle reaper stop/free previews
  • [e2e] a real full-stack build boots on 127.0.0.1, the headless verifier DETECTS
    an injected runtime bug, and a re-actuated (corrected) blueprint RECOVERS clean
    — i.e. the self-heal LOOP mechanics, end to end.

Two stages:
  1. Deterministic — always run (no node/chromium/LLM). Fast.
  2. End-to-end — gated behind  RUN_FULLSTACK_E2E=1  (needs node + the local
     playwright/chromium install in factory_ui). Boots Vite + uvicorn for real.

The e2e stage deliberately substitutes a known-good corrected blueprint for the
LLM's fix: it proves the detect → re-actuate → re-verify loop recovers, WITHOUT
depending on gemini-2.5-pro output (non-deterministic and bills credits). The real
LLM repair path (server._request_fix) is exercised only in live builds, not here.
"""

import os
import sys
import json
import time
import shutil
import socket
import subprocess

import pytest

_MAE_DIR = os.path.dirname(os.path.abspath(__file__))
_FACTORY_ROOT = os.path.dirname(_MAE_DIR)
_FACTORY_UI = os.path.join(_FACTORY_ROOT, "factory_ui")
if _MAE_DIR not in sys.path:
    sys.path.insert(0, _MAE_DIR)

import preview_manager as pm  # noqa: E402

APP_NAME = "maf-e2e-counter-heal"
_APP_ROOT = os.path.join(pm._SCRIPT_DIR, "generated_builds", APP_NAME)

_E2E = os.environ.get("RUN_FULLSTACK_E2E") == "1"
_HAVE_NODE = shutil.which("node") is not None


# ─────────────────────────────────────────────────────────────────────────────
# Blueprint helpers (the envelope mock_antigravity.py consumes)
# ─────────────────────────────────────────────────────────────────────────────

# Reliable runtime fault: dereferencing an undefined value throws at render time,
# which Playwright surfaces as a 'pageerror' — more deterministic than a Vite
# parse-overlay. This is the "deliberate syntax/runtime bug" the heal loop must see.
_BROKEN_APP_JSX = """\
export default function App() {
  const boom = undefined;
  return <h1>Count: {boom.value}</h1>;
}
"""

_FIXED_APP_JSX = """\
import { useState } from 'react';
export default function App() {
  const [count, setCount] = useState(0);
  return (
    <div>
      <h1>Count: {count}</h1>
      <button onClick={() => setCount((c) => c + 1)}>increment</button>
    </div>
  );
}
"""

_BACKEND_APP_PY = """\
from fastapi import FastAPI
app = FastAPI()

@app.get("/api/count")
def count():
    return {"count": 0}
"""


def _blueprint_envelope(app_jsx: str) -> dict:
    return {
        "blueprint_data": json.dumps({
            "app_name": APP_NAME,
            "summary": "Full-stack counter (Phase 4 self-heal e2e fixture).",
            "ast_mutations": [
                {"target_file": "frontend/src/App.jsx", "code_payload": app_jsx},
                {"target_file": "backend/app.py", "code_payload": _BACKEND_APP_PY},
            ],
        }),
        "Strategic_Pause": False,
        "Strategic_Fail": False,
        "timestamp": int(time.time()),
    }


def _actuate(app_jsx: str):
    """Run the real actuator over a spooled blueprint (as the IPC bridge would)."""
    spool = os.path.join(_MAE_DIR, f"_spool_{APP_NAME}.json")
    with open(spool, "w", encoding="utf-8") as f:
        json.dump(_blueprint_envelope(app_jsx), f)
    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(_MAE_DIR, "mock_antigravity.py"),
             "--execute-blueprint", spool],
            capture_output=True, text=True, timeout=120,
        )
        assert proc.returncode == 0, f"actuator failed: {proc.stderr or proc.stdout}"
    finally:
        if os.path.exists(spool):
            os.remove(spool)


def _run_verifier(port: int) -> dict:
    """Invoke the headless verifier exactly as server.py does and parse its report."""
    shot = os.path.join(_MAE_DIR, f"_verify_{APP_NAME}.png")
    report = os.path.join(_MAE_DIR, f"_verify_{APP_NAME}.json")
    for p in (shot, report):
        if os.path.exists(p):
            os.remove(p)
    subprocess.run(
        ["node", os.path.join(_FACTORY_UI, "verify_app.mjs"),
         f"http://127.0.0.1:{port}/", shot, report],
        cwd=_FACTORY_UI, capture_output=True, text=True, timeout=90,
    )
    assert os.path.exists(report), "verifier produced no report"
    with open(report, encoding="utf-8") as f:
        data = json.load(f)
    for p in (shot, report):
        if os.path.exists(p):
            os.remove(p)
    return data


@pytest.fixture
def cleanup_app():
    yield
    try:
        pm.stop_preview(APP_NAME)
    except Exception:
        pass
    # Remove the generated app, but never follow the node_modules junction when
    # deleting (that would walk into the shared template install).
    if os.path.isdir(_APP_ROOT):
        nm = os.path.join(_APP_ROOT, "frontend", "node_modules")
        if os.path.exists(nm):
            try:
                os.rmdir(nm) if os.path.islink(nm) else subprocess.run(
                    ["cmd", "/c", "rmdir", nm], capture_output=True)
            except Exception:
                pass
        shutil.rmtree(_APP_ROOT, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — deterministic (always run)
# ─────────────────────────────────────────────────────────────────────────────

def test_pythonunbuffered_injected_into_child_env():
    """The Phase-4 fix: spawned dev servers must flush tracebacks immediately."""
    base = pm._scrubbed_env()
    assert base.get("PYTHONUNBUFFERED") == "1"
    # Caller-supplied extras must not clobber the unbuffered flag.
    with_extra = pm._scrubbed_env({"BACKEND_PORT": "6543"})
    assert with_extra.get("PYTHONUNBUFFERED") == "1"
    assert with_extra.get("BACKEND_PORT") == "6543"


def test_child_env_is_scrubbed_of_secrets():
    """Allowlist scrub: secrets like GEMINI_API_KEY never reach generated code."""
    os.environ["GEMINI_API_KEY"] = "should-not-leak"
    try:
        env = pm._scrubbed_env()
        assert "GEMINI_API_KEY" not in env
    finally:
        os.environ.pop("GEMINI_API_KEY", None)


def test_allocate_port_avoids_reserved_and_unsafe():
    allocated = []
    for _ in range(5):
        p = pm.allocate_port(extra_taken=allocated)
        assert pm._SCAN_LO <= p <= pm._SCAN_HI
        assert p not in pm._RESERVED_PORTS
        assert p not in allocated
        # Nothing is listening yet -> loopback health check is false.
        assert pm.health_check(p) is False
        allocated.append(p)


class _FakeProc:
    """Stand-in for a dev-server Popen so we can drive the reaper/cap with no OS."""
    def __init__(self, alive=True):
        self.pid = -1
        self._alive = alive
    def poll(self):
        return None if self._alive else 0
    def send_signal(self, *_):  # CTRL_BREAK path
        self._alive = False
    def terminate(self):
        self._alive = False
    def wait(self, timeout=None):
        return 0
    def kill(self):
        self._alive = False


def _inject_fake_preview(name, last_active, alive=True, port=6543):
    with pm._lock:
        pm._previews[name] = {
            "proc": _FakeProc(alive), "backend_proc": None,
            "port": port, "backend_port": None,
            "frontend_dir": _MAE_DIR, "backend_dir": _MAE_DIR,
            "fe_logf": None, "be_logf": None,
            "started": last_active, "last_active": last_active,
        }


def test_idle_reaper_stops_and_frees(monkeypatch):
    monkeypatch.setattr(pm, "IDLE_TIMEOUT_S", 1)
    _inject_fake_preview("reap-me", last_active=time.time() - 999, alive=True)
    try:
        pm.reap_idle()
        assert "reap-me" not in pm.status()
    finally:
        pm.stop_preview("reap-me")


def test_concurrency_cap_evicts_oldest(monkeypatch):
    monkeypatch.setattr(pm, "MAX_PREVIEWS", 2)
    now = time.time()
    _inject_fake_preview("oldest", last_active=now - 100, port=6543)
    _inject_fake_preview("newest", last_active=now - 1, port=6544)
    try:
        pm._enforce_concurrency_cap()  # at cap -> must evict the oldest
        names = pm.status()
        assert "oldest" not in names
        assert "newest" in names
    finally:
        for n in ("oldest", "newest"):
            pm.stop_preview(n)


def test_actuator_scaffolds_fullstack_and_junctions_node_modules(cleanup_app):
    _actuate(_FIXED_APP_JSX)
    fe = os.path.join(_APP_ROOT, "frontend")
    # Model source overlaid on top of the scaffolded template.
    assert os.path.isfile(os.path.join(fe, "src", "App.jsx"))
    assert os.path.isfile(os.path.join(fe, "package.json"))          # from template
    assert os.path.isfile(os.path.join(_APP_ROOT, "backend", "app.py"))
    # node_modules must be a LINK to the template install, not a fresh copy.
    nm = os.path.join(fe, "node_modules")
    assert os.path.exists(os.path.join(nm, "vite", "bin", "vite.js"))
    tpl_nm = os.path.join(pm._SCRIPT_DIR, "templates", "dev_frontend", "node_modules")
    assert os.path.realpath(nm) == os.path.realpath(tpl_nm), \
        "node_modules should junction to the template (instant), not be copied"


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — end-to-end (gated; boots real dev servers + headless chromium)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not (_E2E and _HAVE_NODE),
                    reason="set RUN_FULLSTACK_E2E=1 (needs node + factory_ui playwright)")
def test_fullstack_build_boots_loopback_detects_and_self_heals(cleanup_app):
    # 1. Build a full-stack counter with a deliberate runtime bug.
    _actuate(_BROKEN_APP_JSX)

    # 2. Boot the dev servers via the live supervisor.
    info = pm.start_preview(APP_NAME, _APP_ROOT)
    fe_port = info["port"]

    # 3. Loopback binding: the frontend answers on 127.0.0.1 ...
    assert pm.wait_ready(fe_port, 45), "Vite dev server never bound on 127.0.0.1"
    if info.get("backend_port"):
        assert pm.health_check(info["backend_port"]), "uvicorn backend not on loopback"

    # 4. Detection half of self-heal: the verifier flags the injected fault.
    broken = _run_verifier(fe_port)
    assert broken["success"] is False
    assert broken["pageErrors"] or broken["consoleErrors"], \
        "verifier failed to capture the injected runtime error"

    # 5. Loop mechanics: re-actuate a CORRECTED blueprint (stands in for a successful
    #    heal round), let Vite HMR pick it up, and re-verify clean. This proves
    #    detect -> re-actuate -> re-verify recovers, without invoking the LLM.
    _actuate(_FIXED_APP_JSX)
    time.sleep(4)  # Vite HMR + uvicorn --reload settle
    healed = _run_verifier(fe_port)
    assert healed["success"] is True, f"recovery failed: {healed}"

    # 6. Teardown frees the port (reaping / process-tree kill).
    pm.stop_preview(APP_NAME)
    assert pm.health_check(fe_port) is False, "port not freed after stop_preview"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
