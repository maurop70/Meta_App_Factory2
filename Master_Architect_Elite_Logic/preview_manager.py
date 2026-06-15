"""Preview process manager for full-stack builds (Phase 4).

Governs the lifecycle of long-lived dev-server subprocesses for generated apps:
a Vite frontend and (optionally) a FastAPI backend run from a shared, pre-built
Python venv. Handles dynamic port allocation, launch with a scrubbed environment,
readiness health-checks, a concurrency cap, an idle reaper, and robust Windows
process-tree teardown (CTRL_BREAK -> taskkill /T -> netstat+taskkill port kill).

Lifetimes are decoupled from the build's SSE connection: previews persist until
the idle reaper (default 10 min) or an explicit stop, so the "Open app" link
keeps working after the build finishes.
"""
import os
import time
import socket
import signal
import logging
import threading
import subprocess

logger = logging.getLogger("MasterArchitect.PreviewManager")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IS_WIN = os.name == "nt"

# Shared, pre-installed backend venv (FastAPI + uvicorn). No per-build pip install.
_VENV_PY = os.path.join(
    _SCRIPT_DIR, "templates", "shared_backend_venv",
    "Scripts" if IS_WIN else "bin", "python.exe" if IS_WIN else "python",
)

# Ports owned by the MAF ecosystem — never hand these out.
_RESERVED_PORTS = {5000, 5050, 5173, 8000, 9000}
_RESERVED_PORTS |= set(range(5020, 5091))  # server.py fleet
# Chromium refuses to navigate to its "unsafe ports" (net::ERR_UNSAFE_PORT), so the
# headless verifier can't render apps served there. Exclude the ones in our range.
_RESERVED_PORTS |= {6000, 6566, 6665, 6666, 6667, 6668, 6669, 6697}
_SCAN_LO, _SCAN_HI = 6001, 8000

MAX_PREVIEWS = 3
IDLE_TIMEOUT_S = 600  # 10 minutes

# Minimal env allowlist so child processes can launch on Windows without
# inheriting secrets (GEMINI_API_KEY etc.).
_ENV_ALLOWLIST = (
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR",
    "TEMP", "TMP", "COMSPEC", "USERNAME", "APPDATA", "LOCALAPPDATA",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "HOMEDRIVE", "HOMEPATH",
)

_previews = {}   # app_name -> dict (procs, ports, dirs, logfs, timestamps)
_lock = threading.RLock()


def _scrubbed_env(extra=None):
    env = {}
    for k in _ENV_ALLOWLIST:
        for ek, ev in os.environ.items():
            if ek.upper() == k:
                env[ek] = ev
                break
    if extra:
        env.update(extra)
    return env


def _port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def allocate_port(extra_taken=None):
    """Return a free TCP port in the scan range, skipping reserved/in-use ports."""
    with _lock:
        taken = {p["port"] for p in _previews.values()}
        taken |= {p.get("backend_port") for p in _previews.values()}
        taken |= set(extra_taken or [])
        for port in range(_SCAN_LO, _SCAN_HI):
            if port in _RESERVED_PORTS or port in taken:
                continue
            if _port_free(port):
                return port
    raise RuntimeError("No free preview port available in range 6001-8000")


def health_check(port, timeout=0.4):
    if not port:
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def wait_ready(port, timeout_s=40):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if health_check(port):
            return True
        time.sleep(0.5)
    return False


def _spawn(cmd, cwd, log_path, env):
    logf = open(log_path, "w", encoding="utf-8", errors="ignore")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if IS_WIN else 0
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env,
        stdout=logf, stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    return proc, logf


def start_preview(app_name, app_dir, backend_port=None):
    """Boot the dev server(s) for a generated app under `app_dir`.

    Always starts Vite (frontend/). If backend/app.py exists, also starts uvicorn
    from the shared venv on a second port and points Vite's /api proxy at it via
    the BACKEND_PORT env. Returns {"port","backend_port","pid","log_path"}.
    """
    stop_preview(app_name)
    _enforce_concurrency_cap()

    frontend_dir = os.path.join(app_dir, "frontend")
    backend_dir = os.path.join(app_dir, "backend")
    vite_js = os.path.join(frontend_dir, "node_modules", "vite", "bin", "vite.js")
    if not os.path.isfile(vite_js):
        raise RuntimeError(f"vite not found in template node_modules: {vite_js}")
    has_backend = os.path.isfile(os.path.join(backend_dir, "app.py"))

    fe_port = allocate_port()
    be_port = allocate_port(extra_taken=[fe_port]) if has_backend else None

    backend_proc = be_logf = None
    if has_backend:
        if not os.path.isfile(_VENV_PY):
            raise RuntimeError(f"shared backend venv missing: {_VENV_PY}")
        be_log = os.path.join(backend_dir, "backend.log")
        # --reload so a self-heal rewrite of app.py auto-restarts the backend
        # (the frontend gets the same effect from Vite HMR).
        be_cmd = [_VENV_PY, "-m", "uvicorn", "app:app", "--port", str(be_port),
                  "--host", "127.0.0.1", "--reload"]
        backend_proc, be_logf = _spawn(be_cmd, backend_dir, be_log, _scrubbed_env())
        logger.info(f"[Preview] backend uvicorn '{app_name}' (pid {backend_proc.pid}) on :{be_port}")

    fe_log = os.path.join(frontend_dir, "frontend.log")
    fe_env = _scrubbed_env({"BACKEND_PORT": str(be_port or 0)})
    fe_cmd = ["node", vite_js, "--port", str(fe_port), "--strictPort", "--host", "127.0.0.1"]
    proc, fe_logf = _spawn(fe_cmd, frontend_dir, fe_log, fe_env)

    with _lock:
        _previews[app_name] = {
            "proc": proc, "backend_proc": backend_proc,
            "port": fe_port, "backend_port": be_port,
            "frontend_dir": frontend_dir, "backend_dir": backend_dir,
            "fe_logf": fe_logf, "be_logf": be_logf,
            "started": time.time(), "last_active": time.time(),
        }
    logger.info(f"[Preview] started '{app_name}' (pid {proc.pid}) on :{fe_port}")

    # Give the backend a head start so /api works when the frontend is verified.
    if has_backend:
        wait_ready(be_port, 25)
    return {"port": fe_port, "backend_port": be_port, "pid": proc.pid, "log_path": fe_log}


def tail_log(app_name, max_chars=4000):
    """Combined tail of the Vite and backend logs (for the self-heal prompt)."""
    with _lock:
        rec = _previews.get(app_name)
    if not rec:
        return ""
    out = []
    for label, path in (("vite", os.path.join(rec["frontend_dir"], "frontend.log")),
                        ("backend", os.path.join(rec["backend_dir"], "backend.log"))):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    body = f.read()[-max_chars:]
                if body.strip():
                    out.append(f"--- {label}.log ---\n{body}")
            except Exception:
                pass
    return "\n".join(out)


def touch(app_name):
    with _lock:
        if app_name in _previews:
            _previews[app_name]["last_active"] = time.time()


def status():
    with _lock:
        return {
            name: {
                "port": r["port"], "backend_port": r.get("backend_port"),
                "pid": r["proc"].pid,
                "backend_pid": r["backend_proc"].pid if r.get("backend_proc") else None,
                "alive": r["proc"].poll() is None,
                "idle_s": int(time.time() - r["last_active"]),
            }
            for name, r in _previews.items()
        }


def _kill_tree(proc, port):
    if proc is None or proc.poll() is not None:
        return
    try:
        if IS_WIN:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()
        try:
            proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            pass
    except Exception:
        pass
    if proc.poll() is None:
        try:
            if IS_WIN:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            else:
                proc.kill()
        except Exception:
            pass
    if port and health_check(port):
        try:
            from chaos_kill import kill_port_process
            kill_port_process(port)
        except Exception as e:
            logger.warning(f"[Preview] port force-kill failed for :{port}: {e}")


def stop_preview(app_name):
    with _lock:
        rec = _previews.pop(app_name, None)
    if not rec:
        return False
    _kill_tree(rec.get("backend_proc"), rec.get("backend_port"))
    _kill_tree(rec["proc"], rec["port"])
    for key in ("fe_logf", "be_logf"):
        try:
            if rec.get(key):
                rec[key].close()
        except Exception:
            pass
    logger.info(f"[Preview] stopped '{app_name}'")
    return True


def _enforce_concurrency_cap():
    with _lock:
        if len(_previews) < MAX_PREVIEWS:
            return
        oldest = min(_previews.items(), key=lambda kv: kv[1]["last_active"])[0]
    stop_preview(oldest)


def reap_idle():
    now = time.time()
    with _lock:
        doomed = [n for n, r in _previews.items()
                  if r["proc"].poll() is not None or (now - r["last_active"]) > IDLE_TIMEOUT_S]
    for name in doomed:
        stop_preview(name)


def start_reaper(interval_s=60):
    def _loop():
        while True:
            time.sleep(interval_s)
            try:
                reap_idle()
            except Exception as e:
                logger.error(f"[Preview] reaper fault: {e}")
    t = threading.Thread(target=_loop, daemon=True, name="preview-reaper")
    t.start()
    return t
