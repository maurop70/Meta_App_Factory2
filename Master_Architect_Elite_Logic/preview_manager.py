"""Preview process manager for full-stack builds (Phase 4).

Governs the lifecycle of long-lived dev-server subprocesses (Vite, and later
uvicorn) spawned for generated apps: dynamic port allocation, launch with a
scrubbed environment, readiness health-checks, a concurrency cap, an idle
reaper, and robust Windows process-tree teardown (CTRL_BREAK -> taskkill /T ->
netstat+taskkill port force-kill).

Lifetimes are decoupled from the build's SSE connection: previews persist until
the idle reaper (default 10 min) or an explicit stop, so the "Open app" link
keeps working after the build finishes.
"""
import os
import sys
import time
import socket
import signal
import logging
import threading
import subprocess

logger = logging.getLogger("MasterArchitect.PreviewManager")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IS_WIN = os.name == "nt"

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

_previews = {}          # app_name -> {"proc","port","backend_port","started","last_active","app_dir"}
_lock = threading.RLock()


def _scrubbed_env(extra=None):
    env = {}
    for k in _ENV_ALLOWLIST:
        # match case-insensitively (Windows env keys vary in case)
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


def allocate_port():
    """Return a free TCP port in the scan range, skipping reserved/in-use ports."""
    with _lock:
        taken = {p["port"] for p in _previews.values()} | {p.get("backend_port") for p in _previews.values()}
        for port in range(_SCAN_LO, _SCAN_HI):
            if port in _RESERVED_PORTS or port in taken:
                continue
            if _port_free(port):
                return port
    raise RuntimeError("No free preview port available in range 6000-8000")


def health_check(port, timeout=0.4):
    """True if something is accepting connections on the port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def wait_ready(port, timeout_s=40):
    """Block until the port accepts connections or the timeout elapses."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if health_check(port):
            return True
        time.sleep(0.5)
    return False


def _vite_bin(frontend_dir):
    return os.path.join(frontend_dir, "node_modules", "vite", "bin", "vite.js")


def start_preview(app_name, frontend_dir, backend_port=None):
    """Launch the Vite dev server for `frontend_dir` on a freshly allocated port.

    Returns {"port", "log_path", "pid"}. Stops any existing preview for the app
    first, and enforces the concurrency cap by reaping the oldest idle preview.
    """
    stop_preview(app_name)
    _enforce_concurrency_cap()

    port = allocate_port()
    log_path = os.path.join(frontend_dir, "frontend.log")
    vite_js = _vite_bin(frontend_dir)
    if not os.path.isfile(vite_js):
        raise RuntimeError(f"vite not found in template node_modules: {vite_js}")

    env = _scrubbed_env({"BACKEND_PORT": str(backend_port or 0)})
    cmd = ["node", vite_js, "--port", str(port), "--strictPort", "--host", "127.0.0.1"]

    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if IS_WIN else 0
    logf = open(log_path, "w", encoding="utf-8", errors="ignore")
    proc = subprocess.Popen(
        cmd, cwd=frontend_dir, env=env,
        stdout=logf, stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    with _lock:
        _previews[app_name] = {
            "proc": proc, "port": port, "backend_port": backend_port,
            "started": time.time(), "last_active": time.time(),
            "app_dir": frontend_dir, "logf": logf,
        }
    logger.info(f"[Preview] started '{app_name}' (pid {proc.pid}) on :{port}")
    return {"port": port, "log_path": log_path, "pid": proc.pid}


def tail_log(app_name, max_chars=4000):
    with _lock:
        rec = _previews.get(app_name)
    path = os.path.join(rec["app_dir"], "frontend.log") if rec else None
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()[-max_chars:]
    except Exception:
        return ""


def touch(app_name):
    with _lock:
        if app_name in _previews:
            _previews[app_name]["last_active"] = time.time()


def status():
    with _lock:
        return {
            name: {
                "port": r["port"], "backend_port": r.get("backend_port"),
                "pid": r["proc"].pid, "alive": r["proc"].poll() is None,
                "idle_s": int(time.time() - r["last_active"]),
            }
            for name, r in _previews.items()
        }


def _kill_tree(proc, port):
    """Best-effort Windows-friendly teardown of a dev-server process tree."""
    if proc.poll() is not None:
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
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               capture_output=True)
            else:
                proc.kill()
        except Exception:
            pass
    # Port-level force-kill fallback (handles orphaned grandchildren still bound).
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
    _kill_tree(rec["proc"], rec["port"])
    try:
        rec["logf"].close()
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
    """Stop previews idle past IDLE_TIMEOUT_S (or whose process has died)."""
    now = time.time()
    with _lock:
        doomed = [n for n, r in _previews.items()
                  if r["proc"].poll() is not None or (now - r["last_active"]) > IDLE_TIMEOUT_S]
    for name in doomed:
        stop_preview(name)


def start_reaper(interval_s=60):
    """Launch a daemon thread that periodically reaps idle/dead previews."""
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
