"""
Autonomy Trigger — Phase 5 ClaudeAY Autonomy
----------------------------------------------
Proactive self-healing loop. Monitors production conditions and
autonomously fires ClaudeAY mandates to diagnose, fix, commit,
deploy, and verify — no human approval required.

Conditions:
  C1 — TELEMETRY_CRITICAL : Same critical browser error persists across
                             3 consecutive 60s polling windows.
  C2 — PROD_HEALTH_FAIL   : Remote service health probe returns non-200
                             for 3 consecutive polls (independent per host).

Concurrency safety:
  - Per-condition cooldown: 600s between consecutive triggers.
  - Hourly max: 3 triggers per condition/host → circuit open.
  - Active session lock: blocks re-entry while send_mandate() runs.
  - Circuit stays open until process restart (operator must review log).

Dry-run: AUTONOMY_DRY_RUN=true logs what would fire, no send_mandate().
Audit log: logs/autonomy_events.jsonl

Started from loop_ui.py alongside auto_trigger.
"""

import json
import logging
import os
import socket
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

log = logging.getLogger("AutonomyTrigger")

BRIDGE_DIR     = Path(__file__).parent.resolve()
TELEMETRY_LOG  = BRIDGE_DIR / "logs" / "telemetry.jsonl"
AUDIT_LOG      = BRIDGE_DIR / "logs" / "autonomy_events.jsonl"

POLL_INTERVAL         = 60    # seconds between full evaluation cycles
C1_THRESHOLD          = 3    # consecutive windows required to fire C1
C2_THRESHOLD          = 3    # consecutive health failures required to fire C2
C1_WINDOW_SECS        = POLL_INTERVAL * C1_THRESHOLD + 30   # 210s observation window
COOLDOWN_SECONDS      = 600  # minimum seconds between triggers for same condition
MAX_TRIGGERS_PER_HOUR = 3    # triggers in 1h before circuit opens


# ── Monitored production services (C2) ───────────────────────────────────────

MONITORED_SERVICES: list[dict] = [
    {
        "host_ip":      "104.248.233.220",
        "host_name":    "maf-production-nyc1",
        "service":      "core-engine",
        "health_url":   "http://127.0.0.1:8000/api/health",
        "systemd_unit": "core-engine",
    },
    {
        "host_ip":      "68.183.30.128",
        "host_name":    "mwo-production-nyc1",
        "service":      "erp-backend",
        "health_url":   "http://127.0.0.1:8000/system/directive",
        "systemd_unit": "erp-backend",
    },
]


# ── Condition state ────────────────────────────────────────────────────────────

@dataclass
class ConditionState:
    trigger_times:  deque = field(default_factory=deque)
    active_session: threading.Event = field(default_factory=threading.Event)
    circuit_open:   bool = False


# C1 — single state + per-signature observation windows
_c1_state: ConditionState = ConditionState()
_error_windows: dict[str, deque] = {}

# C2 — one state and fail streak per host_ip
_c2_states: dict[str, ConditionState] = {
    s["host_ip"]: ConditionState() for s in MONITORED_SERVICES
}
_c2_fail_streaks: dict[str, int] = {
    s["host_ip"]: 0 for s in MONITORED_SERVICES
}


# ── Audit and circuit helpers ─────────────────────────────────────────────────

def _write_audit(entry: dict) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _open_circuit(condition_id: str, state: ConditionState, reason: str) -> None:
    state.circuit_open = True
    now = time.monotonic()
    hourly = sum(1 for t in state.trigger_times if t > now - 3600)
    log.error("[AUTONOMY] CIRCUIT OPEN — %s: %s", condition_id, reason)
    _write_audit({
        "condition":        condition_id,
        "status":           "circuit_open",
        "reason":           reason,
        "trigger_count_1h": hourly,
    })


def _can_fire(condition_id: str, state: ConditionState) -> bool:
    """All gates must pass before a trigger may fire."""
    if state.circuit_open:
        log.debug("[AUTONOMY] %s: circuit open", condition_id)
        return False
    if state.active_session.is_set():
        log.debug("[AUTONOMY] %s: active session", condition_id)
        return False
    now = time.monotonic()
    last = state.trigger_times[-1] if state.trigger_times else 0.0
    if last and (now - last) < COOLDOWN_SECONDS:
        log.debug("[AUTONOMY] %s: cooldown %ds remaining",
                  condition_id, int(COOLDOWN_SECONDS - (now - last)))
        return False
    hourly = sum(1 for t in state.trigger_times if t > now - 3600)
    if hourly >= MAX_TRIGGERS_PER_HOUR:
        _open_circuit(condition_id, state, "max triggers per hour reached")
        return False
    return True


# ── Telemetry helpers (C1) ────────────────────────────────────────────────────

def _error_signature(event: dict) -> str:
    return (f"{event.get('type')}::"
            f"{event.get('message', '')[:80]}::"
            f"{event.get('url', '')}")


def _is_local_url(url: str) -> bool:
    return not url or any(h in url for h in ("localhost", "127.0.0.1", "::1"))


def _read_critical_events(n: int = 20) -> list[dict]:
    if not TELEMETRY_LOG.exists():
        return []
    try:
        lines = TELEMETRY_LOG.read_text(encoding="utf-8").strip().splitlines()
        events = [json.loads(l) for l in lines[-n:] if l.strip()]
        return [
            e for e in events
            if e.get("type") in ("console_error", "page_error", "request_failed")
            and _is_local_url(e.get("url", ""))
        ]
    except Exception:
        return []


# ── Remote health probe (C2) ─────────────────────────────────────────────────

def _find_ssh_key() -> Optional[str]:
    kp = os.getenv("SSH_KEY_PATH", "").strip()
    if kp and Path(kp).exists():
        return kp
    for name in ("id_ed25519", "id_rsa", "id_ecdsa"):
        cand = Path.home() / ".ssh" / name
        if cand.exists():
            return str(cand)
    return None


def _probe_remote_health(host_ip: str, health_url: str) -> tuple[bool, str]:
    """
    SSH to host_ip, curl health_url on the loopback.
    Returns (is_healthy, detail).  is_healthy == True only when HTTP 200.
    """
    try:
        from ssh_wire import pinned_ssh_client
        client, _save_host_key = pinned_ssh_client(host_ip)
        kw: dict = {"hostname": host_ip, "username": "root",
                    "timeout": 10, "look_for_keys": True, "allow_agent": True}
        sk = _find_ssh_key()
        if sk:
            kw["key_filename"] = sk
        client.connect(**kw)
        _save_host_key()  # TOFU pinning — key changes are rejected thereafter
        cmd = f'curl -s -o /dev/null -w "%{{http_code}}" --max-time 5 {health_url}'
        _, stdout, _ = client.exec_command(cmd)
        stdout.channel.settimeout(15)
        code = stdout.read().decode("utf-8", errors="replace").strip()
        client.close()
        return code == "200", code
    except (paramiko.SSHException, socket.error, OSError, TimeoutError) as exc:
        return False, f"SSH error: {exc}"
    except Exception as exc:
        return False, f"probe error: {exc}"


# ── Mandate payload builders ─────────────────────────────────────────────────

def _fmt_errors(errors: list[dict], n: int = 5) -> str:
    return "\n".join(
        f"  [{e.get('type','?')}] {e.get('message','?')[:120]}"
        f" | line {e.get('lineNumber','?')} | {e.get('url','?')}"
        for e in errors[:n]
    )


def _build_c1_payload(errors: list[dict], window_count: int) -> str:
    ts      = datetime.now(timezone.utc).isoformat()
    elapsed = int(window_count * POLL_INTERVAL / 60)
    return f"""AUTONOMOUS SYSTEM MANDATE — CONDITION: TELEMETRY_CRITICAL
Triggered: {ts}
Consecutive polling windows with error: {window_count} ({elapsed}+ minutes)

PERSISTING ERRORS (up to 5):
{_fmt_errors(errors)}

YOUR MANDATE — FULL AUTONOMOUS EXECUTION. NO HUMAN APPROVAL REQUIRED.

STEP 1 — DIAGNOSE
  Use file_operation(read) to inspect source files implicated by the error
  stack traces and URLs. Read related modules as needed.
  State the root cause in one sentence before proceeding.

STEP 2 — FIX
  Use file_operation(write) to apply the minimal correct fix.
  Change only what the bug requires. No refactoring, no cleanup.

STEP 3 — VERIFY LOCALLY
  Use execute_shell to run tests or lint:
    python -m pytest --tb=short -q
  If tests fail after your fix, revise and re-run.
  Do NOT proceed to commit if tests fail.

STEP 4 — COMMIT (specific files only — git add "." is blocked)
  Use git_operation(add, paths=[<files you changed>]) then
  git_operation(commit) with message:
    "fix(autonomy): <error_type> -- <one_line_root_cause> [auto]"
  Then git_operation(push).

STEP 5 — DO NOT DEPLOY (Tier 3-R cap, CLAUDE_RULES Section 15)
  Autonomous self-healing is capped below production deployment.
  The fix is committed and pushed; deployment requires the operator.
  End your ledger with:
  LEDGER_JSON: {{"status": "ESCALATE", "summary": "<root cause + fix>",
   "files_changed": [...], "tests_run": [...],
   "next_step": "operator: review commit and deploy",
   "needs_human": "Tier 3: production deploy of committed autonomy fix"}}

STEP 6 — REPORT (required even on failure)
  ROOT_CAUSE: <one sentence>
  FILES_CHANGED: <list>
  COMMIT: <hash or "none">
  NOTES: <anything the operator must know>
"""


def _build_c2_payload(svc: dict, fail_streak: int, last_detail: str) -> str:
    ts         = datetime.now(timezone.utc).isoformat()
    elapsed    = int(fail_streak * POLL_INTERVAL / 60)
    host_ip    = svc["host_ip"]
    host_name  = svc["host_name"]
    service    = svc["service"]
    unit       = svc["systemd_unit"]
    health_url = svc["health_url"]
    # Choose deploy script hint based on which host
    deploy_hint = ("python deploy_maf.py" if "maf" in host_name
                   else "python deploy_erp.py")
    return f"""AUTONOMOUS SYSTEM MANDATE — CONDITION: PROD_HEALTH_FAIL
Triggered: {ts}
Host: {host_name} ({host_ip})
Service: {service} (systemd unit: {unit})
Consecutive health check failures: {fail_streak} ({elapsed}+ minutes)
Last health probe response: {last_detail}
Health URL: {health_url}

YOUR MANDATE — FULL AUTONOMOUS EXECUTION. NO HUMAN APPROVAL REQUIRED.

STEP 1 — DIAGNOSE REMOTE
  Use execute_remote_shell on {host_ip} to gather context:
    a. systemctl status {unit} --no-pager | head -8
    b. journalctl -u {unit} -n 30 --no-pager
    c. df -h && free -m

  Classify the failure as one of:
    (A) Code crash   — Python exception in service log
    (B) Resource     — disk full or OOM
    (C) Dependency   — another service it calls is down
    (D) Unknown

STEP 2 — FIX
  Case A (code crash):
    Use file_operation(read) to locate the defect in local source.
    Use file_operation(write) to apply the fix.
    Use git_operation(add, paths=[<files>]) + git_operation(commit):
      "fix(autonomy): {host_name} crash -- <root_cause> [auto]"
    Then git_operation(push). DO NOT run {deploy_hint} — deployment is
    Tier 3 (CLAUDE_RULES Section 15): end with LEDGER_JSON status=ESCALATE,
    needs_human="Tier 3: deploy committed crash fix to {host_name}".
    Service restart alone (without new code) IS authorized if it restores
    health while the fix awaits deployment.

  Case B (resource exhaustion):
    Use execute_remote_shell to clear logs/temp files as needed.
    Use execute_remote_shell: systemctl restart {unit}

  Case C (dependency failure):
    Use execute_remote_shell to restart the failing dependency.
    Use execute_remote_shell: systemctl restart {unit}

  Case D (unknown):
    Use execute_remote_shell: systemctl restart {unit}
    Document in NOTES that root cause is unknown.

STEP 3 — VERIFY ON PROD
  Use execute_remote_shell on {host_ip}:
    curl -s -o /dev/null -w "%{{http_code}}" --max-time 5 {health_url}
  Expected: 200. Report PROD_STATUS=FAIL if not.

STEP 4 — REPORT (required even on failure)
  ROOT_CAUSE: <one sentence or "unknown">
  ACTION_TAKEN: <what you did>
  COMMIT: <hash or "none -- service restart only">
  PROD_STATUS: PASS | FAIL
  NOTES: <anything the operator must know>
"""


# ── Trigger execution ─────────────────────────────────────────────────────────

def _fire_trigger(condition_id: str, state: ConditionState,
                  mandate: str, context: dict) -> None:
    now = time.monotonic()
    state.trigger_times.append(now)

    # Safety net: if somehow we're over the hourly limit, open circuit and abort
    hourly = sum(1 for t in state.trigger_times if t > now - 3600)
    if hourly > MAX_TRIGGERS_PER_HOUR:
        _open_circuit(condition_id, state, "max triggers per hour exceeded")
        return

    dry_run = os.getenv("AUTONOMY_DRY_RUN", "").lower() in ("1", "true", "yes")

    if dry_run:
        log.warning("[AUTONOMY] DRY RUN — would fire %s | %s",
                    condition_id, json.dumps(context))
        _write_audit({
            "condition":        condition_id,
            "status":           "dry_run",
            "would_have_fired": True,
            "context":          context,
            "payload_preview":  mandate[:400],
        })
        return

    log.warning("[AUTONOMY] FIRING %s | %s", condition_id, json.dumps(context))
    _write_audit({"condition": condition_id, "status": "triggered", "context": context})

    state.active_session.set()
    try:
        sys.path.insert(0, str(BRIDGE_DIR))
        # Cascade executor: Claude Code primary, Antigravity fallback
        # on quota errors — handled inside claude_code_client.
        from claude_code_client import send_mandate
        result = send_mandate(mandate)
        log.info("[AUTONOMY] %s completed: %.200s", condition_id, result)
        _write_audit({
            "condition":      condition_id,
            "status":         "completed",
            "result_preview": result[:500],
        })
    except Exception as exc:
        log.error("[AUTONOMY] %s mandate failed: %s", condition_id, exc)
        _write_audit({
            "condition": condition_id,
            "status":    "mandate_failed",
            "error":     str(exc),
        })
    finally:
        state.active_session.clear()


# ── C1: TELEMETRY_CRITICAL ────────────────────────────────────────────────────

def _check_c1() -> None:
    if not _can_fire("TELEMETRY_CRITICAL", _c1_state):
        return

    try:
        events = _read_critical_events()
    except Exception as exc:
        log.warning("[AUTONOMY] C1 read error: %s", exc)
        return

    now    = time.monotonic()
    cutoff = now - C1_WINDOW_SECS

    # Prune signatures whose last observation is older than the window
    for sig in list(_error_windows):
        dq = _error_windows[sig]
        while dq and dq[0] < cutoff:
            dq.popleft()
        if not dq:
            del _error_windows[sig]

    if not events:
        return

    triggered: list[dict] = []
    seen: set[str] = set()

    for event in events:
        sig = _error_signature(event)
        if sig in seen:
            continue
        seen.add(sig)

        if sig not in _error_windows:
            _error_windows[sig] = deque()
        _error_windows[sig].append(now)

        # Prune stale entries within this signature's window
        while _error_windows[sig] and _error_windows[sig][0] < cutoff:
            _error_windows[sig].popleft()

        if len(_error_windows[sig]) >= C1_THRESHOLD:
            triggered.append(event)

    if triggered:
        context = {
            "error_count":         len(triggered),
            "consecutive_windows": C1_THRESHOLD,
            "signatures":          [_error_signature(e) for e in triggered[:3]],
        }
        _fire_trigger("TELEMETRY_CRITICAL", _c1_state,
                      _build_c1_payload(triggered, C1_THRESHOLD), context)


# ── C2: PROD_HEALTH_FAIL ──────────────────────────────────────────────────────

def _check_c2() -> None:
    for svc in MONITORED_SERVICES:
        host_ip      = svc["host_ip"]
        condition_id = f"PROD_HEALTH_FAIL:{host_ip}"
        state        = _c2_states[host_ip]

        if not _can_fire(condition_id, state):
            continue

        is_healthy, detail = _probe_remote_health(host_ip, svc["health_url"])

        if is_healthy:
            if _c2_fail_streaks[host_ip] > 0:
                log.info("[AUTONOMY] C2 %s recovered — streak reset", host_ip)
            _c2_fail_streaks[host_ip] = 0
        else:
            _c2_fail_streaks[host_ip] += 1
            log.warning("[AUTONOMY] C2 FAIL %s (%s) streak=%d detail=%s",
                        host_ip, svc["service"],
                        _c2_fail_streaks[host_ip], detail)

            if _c2_fail_streaks[host_ip] >= C2_THRESHOLD:
                context = {
                    "host_ip":     host_ip,
                    "host_name":   svc["host_name"],
                    "service":     svc["service"],
                    "fail_streak": _c2_fail_streaks[host_ip],
                    "last_detail": detail,
                }
                _fire_trigger(condition_id, state,
                              _build_c2_payload(svc, _c2_fail_streaks[host_ip], detail),
                              context)


# ── Monitor loop ──────────────────────────────────────────────────────────────

def _monitor_loop() -> None:
    dry = os.getenv("AUTONOMY_DRY_RUN", "").lower() in ("1", "true", "yes")
    log.info("[AUTONOMY] Monitor started (interval=%ds dry_run=%s)", POLL_INTERVAL, dry)
    time.sleep(10)  # Let the system spin up before first check

    while True:
        try:
            _check_c1()
        except Exception as exc:
            log.error("[AUTONOMY] C1 check error: %s", exc)
        try:
            _check_c2()
        except Exception as exc:
            log.error("[AUTONOMY] C2 check error: %s", exc)
        time.sleep(POLL_INTERVAL)


def start_background() -> threading.Thread:
    t = threading.Thread(target=_monitor_loop, daemon=True, name="AutonomyTrigger")
    t.start()
    log.info("[AUTONOMY] Background trigger started")
    return t


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from unittest.mock import patch as _patch

    os.environ["AUTONOMY_DRY_RUN"] = "true"
    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    passed = failed = 0

    def _report(label: str, ok: bool, note: str = "") -> None:
        global passed, failed
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}]{(' ' + note) if note else ''}  {label}")
        if ok:
            passed += 1
        else:
            failed += 1

    print("=== Autonomy Trigger Smoke Test (DRY RUN) ===\n")

    # Snapshot audit log offset so we only read entries written during this test
    audit_offset = (AUDIT_LOG.stat().st_size
                    if AUDIT_LOG.exists() else 0)

    def _new_entries() -> list[dict]:
        if not AUDIT_LOG.exists():
            return []
        text = AUDIT_LOG.read_text(encoding="utf-8")
        result = []
        for line in text[audit_offset:].splitlines():
            if line.strip():
                try:
                    result.append(json.loads(line))
                except Exception:
                    pass
        return result

    # ── C1: TELEMETRY_CRITICAL ─────────────────────────────────────────────
    print("  --- C1: TELEMETRY_CRITICAL ---")
    fake_event = {
        "type":       "console_error",
        "message":    "TypeError: Cannot read properties of undefined (reading 'map')",
        "url":        "http://localhost:5000/builder",
        "lineNumber": "423",
    }
    fake_sig = _error_signature(fake_event)
    now_t = time.monotonic()
    # Simulate 3 prior observations so the threshold is already met
    _error_windows[fake_sig] = deque([now_t - 120, now_t - 60, now_t - 1])

    with _patch("__main__._read_critical_events", return_value=[fake_event]):
        _check_c1()

    c1_entries = [e for e in _new_entries()
                  if e.get("condition") == "TELEMETRY_CRITICAL"]
    ok1 = len(c1_entries) == 1 and c1_entries[0].get("status") == "dry_run"
    _report("C1 fires dry-run, entry written",
            ok1,
            f"[entries={len(c1_entries)} status={c1_entries[0].get('status') if c1_entries else 'none'}]")

    # ── C2: PROD_HEALTH_FAIL (both hosts) ─────────────────────────────────
    print("\n  --- C2: PROD_HEALTH_FAIL ---")
    for svc in MONITORED_SERVICES:
        _c2_fail_streaks[svc["host_ip"]] = C2_THRESHOLD - 1

    with _patch("__main__._probe_remote_health",
                return_value=(False, "simulated-503")):
        _check_c2()

    c2_entries = [e for e in _new_entries()
                  if "PROD_HEALTH_FAIL" in e.get("condition", "")
                  and e.get("status") == "dry_run"]
    fired_hosts  = {e["context"]["host_ip"] for e in c2_entries if "context" in e}
    expected     = {s["host_ip"] for s in MONITORED_SERVICES}
    ok2 = len(c2_entries) == len(MONITORED_SERVICES) and fired_hosts == expected
    _report(
        f"C2 fires dry-run for both hosts",
        ok2,
        f"[entries={len(c2_entries)} hosts={fired_hosts}]",
    )

    # ── Show audit log entries written during this test ────────────────────
    print("\n--- logs/autonomy_events.jsonl (this run) ---")
    for e in _new_entries():
        # Truncate long payload_preview for readability
        display = dict(e)
        if "payload_preview" in display:
            display["payload_preview"] = display["payload_preview"][:80] + "..."
        print(f"  {json.dumps(display)}")

    print(f"\n{passed}/{passed + failed} passed")
    if failed:
        sys.exit(1)
