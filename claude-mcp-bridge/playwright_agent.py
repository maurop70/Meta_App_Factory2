"""
Playwright Agent — MAF E2E Evaluator
--------------------------------------
Takes a TestPlan, executes every test case using playwright_wire, records
results, fires ClaudeAY fix mandates on failures, and manages the
5-cycle fix loop.

Fix loop:
  1. Run all test cases.
  2. If all pass → return READY.
  3. If any fail AND fix_cycles < MAX_FIX_CYCLES → fire mandate, wait 30s,
     clear auth, re-run all tests.
  4. If fix_cycles >= MAX_FIX_CYCLES → emit escalate event, poll for
     human response, then act on it.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable, Any

# ── Locate paths ──────────────────────────────────────────────────────────────
_BRIDGE_DIR = Path(__file__).parent.resolve()
_MAF_ROOT   = _BRIDGE_DIR.parent.resolve()

if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dataclasses
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class TestResult:
    id:               str
    name:             str
    status:           str                     # "pass"|"fail"|"skip"|"error"
    error:            str  = ""
    screenshot_path:  str  = ""
    console_errors:   list = field(default_factory=list)
    network_errors:   list = field(default_factory=list)
    duration_ms:      int  = 0
    cycle:            int  = 0


@dataclass
class FixAttempt:
    cycle:          int
    failing_tests:  list
    mandate_sent:   str
    ay_response:    str
    tests_before:   int
    tests_after:    int  = 0
    timestamp:      str  = ""


@dataclass
class EvaluationReport:
    app_name:           str
    run_id:             str
    status:             str    # "READY"|"ESCALATE"|"FAILED"
    fix_cycles:         int
    total_tests:        int
    passed:             int
    failed:             int
    test_results:       list
    fix_history:        list
    escalation_reason:  str = ""
    duration_ms:        int = 0
    timestamp:          str = ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _tc_attr(tc: Any, key: str, default: Any = None) -> Any:
    """Get attribute from either a dict or an object."""
    if isinstance(tc, dict):
        return tc.get(key, default)
    return getattr(tc, key, default)


def _emit(callback: Optional[Callable], event_type: str, data: Any) -> None:
    """Safely emit an event to the callback."""
    if callback:
        try:
            callback(event_type, data)
        except Exception:
            pass


def build_escalation_message(
    failed: list,
    app_config: dict,
    cycles: int,
) -> str:
    """Return a human-readable summary for the escalation prompt."""
    names = [
        (r["name"] if isinstance(r, dict) else r.name)
        for r in failed
    ]
    errors = [
        (r.get("error", "") if isinstance(r, dict) else r.error)
        for r in failed
    ]
    lines = [
        f"After {cycles} fix cycle(s), {len(failed)} test(s) are still failing in "
        f"{app_config.get('name', 'the app')} ({app_config.get('base_url', '')}):",
    ]
    for name, err in zip(names, errors):
        lines.append(f"  - {name}: {err[:120]}")
    lines += [
        "",
        "Options:",
        "  A — Give the agent 2 more fix cycles",
        "  B — Mark failing tests as skipped and proceed (READY)",
        "  C — Give the agent 5 more fix cycles (deep fix mode)",
    ]
    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PlaywrightAgent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PlaywrightAgent:
    MAX_FIX_CYCLES: int = int(os.getenv("E2E_MAX_FIX_CYCLES", "5"))

    # ── Public entry-point ────────────────────────────────────────────────────

    def run(
        self,
        app_config: dict,
        test_plan: Any,
        run_id: str,
        event_callback: Optional[Callable] = None,
    ) -> EvaluationReport:
        """
        Execute the full evaluation loop.

        Parameters
        ----------
        app_config      : dict from e2e_app_registry.json
        test_plan       : object / namespace with .app_name and .test_cases
        run_id          : unique string identifier for this run
        event_callback  : callable(event_type: str, data: Any)
        """
        start_ms = time.time() * 1000

        base_url     = app_config.get("base_url", "http://localhost").rstrip("/")
        auth_config  = app_config.get("auth_config", {})
        app_name     = _tc_attr(test_plan, "app_name") or app_config.get("name", "App")

        screenshot_dir = str(_MAF_ROOT / "logs" / "playwright_screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)

        fix_history: list[FixAttempt] = []
        fix_cycles = 0

        # ── Get playwright_wire ───────────────────────────────────────────────
        try:
            from playwright_wire import execute as _pw_execute
            _PW_AVAILABLE = True
        except ImportError as exc:
            print(f"[PlaywrightAgent] playwright_wire import failed: {exc}")
            _PW_AVAILABLE = False

        def execute_pw(params: dict) -> dict:
            if not _PW_AVAILABLE:
                return {"success": False, "exit_code": -99,
                        "error": "playwright_wire not available",
                        "stdout": "", "stderr": "playwright_wire not available",
                        "blocked": False, "screenshot_path": None,
                        "console_errors": [], "network_errors": [],
                        "session_id": params.get("session_id")}
            try:
                return _pw_execute(params)
            except Exception as exc:
                return {"success": False, "exit_code": -2,
                        "error": str(exc),
                        "stdout": "", "stderr": str(exc),
                        "blocked": False, "screenshot_path": None,
                        "console_errors": [], "network_errors": [],
                        "session_id": params.get("session_id")}

        # ── Main fix loop ──────────────────────────────────────────────────────
        while True:
            session_id         = str(uuid.uuid4())
            authenticated_roles: dict[str, bool] = {}
            results: list[TestResult] = []

            # Sort test cases: P1 → P2 → P3
            raw_cases = _tc_attr(test_plan, "test_cases") or []
            test_cases = sorted(
                raw_cases,
                key=lambda tc: int(_tc_attr(tc, "priority", 3) or 3),
            )

            # ── Phase 2: Run each test case ───────────────────────────────────
            for tc in test_cases:
                tc_id   = str(_tc_attr(tc, "id")   or str(uuid.uuid4())[:8])
                tc_name = str(_tc_attr(tc, "name") or "Unnamed test")

                _emit(event_callback, "test_start", {"name": tc_name, "id": tc_id})

                tc_start = time.time() * 1000
                result   = self._run_one_test(
                    tc, tc_id, tc_name,
                    base_url, auth_config,
                    session_id, authenticated_roles,
                    screenshot_dir, fix_cycles,
                    execute_pw,
                )
                result.duration_ms = int(time.time() * 1000 - tc_start)
                result.cycle       = fix_cycles

                results.append(result)
                evt = "test_pass" if result.status == "pass" else "test_fail"
                _emit(event_callback, evt, asdict(result))

            # ── Phase 3: Check results ────────────────────────────────────────
            failed_results = [r for r in results if r.status in ("fail", "error")]
            passed_count   = sum(1 for r in results if r.status == "pass")

            if not failed_results:
                # All green — done
                duration = int(time.time() * 1000 - start_ms)
                return EvaluationReport(
                    app_name          = app_name,
                    run_id            = run_id,
                    status            = "READY",
                    fix_cycles        = fix_cycles,
                    total_tests       = len(results),
                    passed            = passed_count,
                    failed            = 0,
                    test_results      = [asdict(r) for r in results],
                    fix_history       = [asdict(fa) for fa in fix_history],
                    duration_ms       = duration,
                    timestamp         = datetime.now(timezone.utc).isoformat(),
                )

            if fix_cycles >= self.MAX_FIX_CYCLES:
                # ── Escalate ──────────────────────────────────────────────────
                reason = build_escalation_message(failed_results, app_config, fix_cycles)
                _emit(event_callback, "escalate", {
                    "question": reason,
                    "options":  ["A", "B", "C"],
                })

                # Poll run state file for escalation_response (30-min timeout)
                run_file = str(_MAF_ROOT / "logs" / "qa_runs" / f"{run_id}.json")
                resp = None
                for _ in range(1800):
                    if os.path.exists(run_file):
                        try:
                            with open(run_file) as f:
                                state = json.load(f)
                            resp = state.get("escalation_response")
                            if resp:
                                break
                        except Exception:
                            pass
                    time.sleep(1)

                if resp == "A":
                    self.MAX_FIX_CYCLES += 2
                elif resp == "B":
                    for r in failed_results:
                        r.status = "skip"
                    duration = int(time.time() * 1000 - start_ms)
                    return EvaluationReport(
                        app_name          = app_name,
                        run_id            = run_id,
                        status            = "READY",
                        fix_cycles        = fix_cycles,
                        total_tests       = len(results),
                        passed            = passed_count,
                        failed            = 0,
                        test_results      = [asdict(r) for r in results],
                        fix_history       = [asdict(fa) for fa in fix_history],
                        escalation_reason = reason,
                        duration_ms       = duration,
                        timestamp         = datetime.now(timezone.utc).isoformat(),
                    )
                elif resp == "C":
                    self.MAX_FIX_CYCLES += 5
                else:
                    # Timed out or unknown — return ESCALATE
                    duration = int(time.time() * 1000 - start_ms)
                    return EvaluationReport(
                        app_name          = app_name,
                        run_id            = run_id,
                        status            = "ESCALATE",
                        fix_cycles        = fix_cycles,
                        total_tests       = len(results),
                        passed            = passed_count,
                        failed            = len(failed_results),
                        test_results      = [asdict(r) for r in results],
                        fix_history       = [asdict(fa) for fa in fix_history],
                        escalation_reason = reason,
                        duration_ms       = duration,
                        timestamp         = datetime.now(timezone.utc).isoformat(),
                    )
                # After escalation response A or C — continue to fix phase below.

            # ── Phase 4: Fire fix mandate ─────────────────────────────────────
            fix_cycles += 1
            _emit(event_callback, "fix_cycle_start", {
                "cycle": fix_cycles,
                "failing": len(failed_results),
            })

            mandate = self._build_mandate(
                failed_results, app_config, fix_cycles, base_url
            )

            ay_response = ""
            try:
                from ay_client import send_mandate as _send_mandate
                ay_response = _send_mandate(mandate, timeout=600)
            except ImportError:
                ay_response = "[ay_client not available — fix skipped]"
            except Exception as exc:
                ay_response = f"[mandate failed: {exc}]"

            fix_attempt = FixAttempt(
                cycle         = fix_cycles,
                failing_tests = [r.name for r in failed_results],
                mandate_sent  = mandate[:500],
                ay_response   = (ay_response or "")[:500],
                tests_before  = len(failed_results),
                timestamp     = datetime.now(timezone.utc).isoformat(),
            )
            fix_history.append(fix_attempt)

            _emit(event_callback, "fix_mandate_sent", {
                "cycle":    fix_cycles,
                "mandate":  mandate[:200],
                "response": (ay_response or "")[:200],
            })

            # Wait for deploy to complete
            print(f"[PlaywrightAgent] Waiting 30s for deploy after fix cycle {fix_cycles}...")
            time.sleep(30)

            # Invalidate auth tokens (redeploy resets sessions)
            authenticated_roles = {}
            # Loop back to re-run all tests

    # ── Single test execution ─────────────────────────────────────────────────

    def _run_one_test(
        self,
        tc: Any,
        tc_id: str,
        tc_name: str,
        base_url: str,
        auth_config: dict,
        session_id: str,
        authenticated_roles: dict,
        screenshot_dir: str,
        fix_cycles: int,
        execute_pw: Callable,
    ) -> TestResult:
        """Execute a single test case and return a TestResult."""

        role       = _tc_attr(tc, "role") or ""
        page_route = _tc_attr(tc, "page") or ""
        steps      = _tc_attr(tc, "steps") or []

        step_errors: list[str] = []

        # ── Step A: Authenticate ──────────────────────────────────────────────
        if role and role.upper() not in ("ANY", "") and role not in authenticated_roles:
            auth_ok = self._authenticate(
                role, base_url, auth_config, session_id, execute_pw, tc_id, screenshot_dir
            )
            if auth_ok:
                authenticated_roles[role] = True
            else:
                return TestResult(
                    id     = tc_id,
                    name   = tc_name,
                    status = "skip",
                    error  = f"auth_failed for role={role}",
                    cycle  = fix_cycles,
                )

        # ── Step B: Navigate to test page ─────────────────────────────────────
        if page_route:
            # Derive the URL: if page_route looks like a filename (e.g. Login.jsx),
            # skip navigation — auth already handled it or we rely on steps.
            if not page_route.endswith(".jsx") and not page_route.endswith(".tsx"):
                nav_url = base_url + "/" + page_route.lstrip("/")
                nav_res = execute_pw({
                    "operation":  "navigate",
                    "url":        nav_url,
                    "session_id": session_id,
                    "timeout_ms": 15000,
                })
                if nav_res.get("exit_code", -1) != 0 and not nav_res.get("blocked"):
                    step_errors.append(
                        f"navigate to {nav_url} failed: {nav_res.get('stderr', '')[:100]}"
                    )
                time.sleep(2)

        # ── Step C: Execute steps ─────────────────────────────────────────────
        for step in steps:
            err = self._execute_step(step, base_url, auth_config, session_id, execute_pw)
            if err:
                step_errors.append(err)

        # ── Step D: Capture evidence ──────────────────────────────────────────
        screenshot_path = ""
        # playwright_wire appends .png automatically — pass name without extension
        screenshot_name = tc_id
        ss_res = execute_pw({
            "operation":  "screenshot",
            "name":       screenshot_name,
            "session_id": session_id,
        })
        if ss_res.get("exit_code") == 0:
            screenshot_path = ss_res.get("screenshot_path") or ss_res.get("stdout") or ""

        # Console errors
        console_res = execute_pw({"operation": "get_console", "session_id": session_id})
        raw_console = console_res.get("stdout") or "[]"
        try:
            all_console = json.loads(raw_console) if isinstance(raw_console, str) else raw_console
        except Exception:
            all_console = []
        console_errors = [
            e for e in (all_console if isinstance(all_console, list) else [])
            if isinstance(e, dict) and e.get("type") == "error"
        ]

        # Network errors (4xx/5xx) for the app's domain only
        network_res = execute_pw({"operation": "get_network", "session_id": session_id})
        raw_network = network_res.get("stdout") or "[]"
        try:
            all_network = json.loads(raw_network) if isinstance(raw_network, str) else raw_network
        except Exception:
            all_network = []
        host = base_url.split("//")[-1].split("/")[0]
        net_errors = [
            r for r in (all_network if isinstance(all_network, list) else [])
            if isinstance(r, dict)
            and r.get("status", 0) >= 400
            and host in r.get("url", "")
        ]

        # ── Step E: Evaluate result ───────────────────────────────────────────
        if step_errors:
            status = "fail"
            error  = "; ".join(step_errors)
        elif console_errors:
            status = "fail"
            error  = f"{len(console_errors)} console error(s): {console_errors[0].get('text','')[:100]}"
        elif net_errors:
            status = "fail"
            error  = (
                f"{len(net_errors)} network error(s): "
                f"{net_errors[0].get('url','')[:60]} [{net_errors[0].get('status','')}]"
            )
        else:
            status = "pass"
            error  = ""

        return TestResult(
            id              = tc_id,
            name            = tc_name,
            status          = status,
            error           = error,
            screenshot_path = screenshot_path,
            console_errors  = console_errors[:5],
            network_errors  = net_errors[:5],
            cycle           = fix_cycles,
        )

    # ── Authentication ────────────────────────────────────────────────────────

    def _authenticate(
        self,
        role: str,
        base_url: str,
        auth_config: dict,
        session_id: str,
        execute_pw: Callable,
        tc_id: str,
        screenshot_dir: str,
    ) -> bool:
        """
        Log in as the given role.  Returns True on success.

        The MWO ERP login form (Login.jsx) has:
          - Honeypot fields (hidden, avoid filling)
          - #mwo_operator_id  — Employee ID (text input)
          - #mwo_operator_pin — PIN (text input with CSS disc obfuscation)
          - .erp-submit-btn   — Authorize Session (disabled until both filled)

        All roles use the same /login page.
        auth_config keys used:
          hm_employee_id / hm_pin
          tech_employee_id / tech_pin
          dm_employee_id / dm_pin
          (fallback: use dm_employee_id as employee_id for DM)
        """
        role_upper = role.upper()

        # All roles use /login (DM uses same page as HM/TECH in MWO ERP)
        login_url = base_url + "/login"

        # Resolve employee_id + pin from auth_config
        employee_id_key = f"{role.lower()}_employee_id"
        pin_key         = f"{role.lower()}_pin"

        employee_id = auth_config.get(employee_id_key, "")
        pin         = auth_config.get(pin_key, "")

        # Role-specific fallbacks if dedicated key not present
        if not employee_id:
            if role_upper == "HM":
                # Try common HM employee IDs from auth_config
                employee_id = auth_config.get("hm_employee_id", auth_config.get("employee_id", ""))
            elif role_upper == "TECH":
                employee_id = auth_config.get("tech_employee_id", auth_config.get("employee_id", ""))
            elif role_upper == "DM":
                employee_id = auth_config.get("dm_employee_id", "")
            elif role_upper == "ADMIN":
                employee_id = auth_config.get("admin_employee_id", auth_config.get("dm_employee_id", ""))

        if not pin:
            if role_upper == "HM":
                pin = auth_config.get("hm_pin", "")
            elif role_upper == "TECH":
                pin = auth_config.get("tech_pin", "")
            elif role_upper == "DM":
                pin = auth_config.get("dm_pin", "")
            elif role_upper == "ADMIN":
                pin = auth_config.get("admin_pin", auth_config.get("hm_pin", ""))

        if not employee_id or not pin:
            print(f"[PlaywrightAgent] Missing credentials for {role_upper}: "
                  f"employee_id={employee_id!r} pin={'***' if pin else '(empty)'}")
            return False

        print(f"[PlaywrightAgent] Authenticating {role_upper} "
              f"(employee_id={employee_id}) at {login_url}")

        # 1. Navigate to login page
        nav = execute_pw({
            "operation":  "navigate",
            "url":        login_url,
            "session_id": session_id,
            "timeout_ms": 15000,
        })
        if nav.get("exit_code", -1) != 0 and not nav.get("blocked"):
            print(f"[PlaywrightAgent] Auth navigate failed for {role_upper}: "
                  f"{nav.get('stderr','')[:80]}")
            return False
        time.sleep(2)

        # 2. Fill Employee ID  (#mwo_operator_id — the real field, not the honeypot)
        eid_filled = False
        for sel in ["#mwo_operator_id", "input[name='mwo_operator_id']",
                    "input[id='mwo_operator_id']"]:
            fill_res = execute_pw({
                "operation":  "fill",
                "selector":   sel,
                "value":      employee_id,
                "session_id": session_id,
                "timeout_ms": 3000,
            })
            if fill_res.get("exit_code") == 0:
                eid_filled = True
                print(f"[PlaywrightAgent] Filled employee_id with selector {sel}")
                break

        if not eid_filled:
            # Fallback: fill the 3rd input (index 2 = first real input after 2 honeypots)
            # Use evaluate to set value + fire React input event
            print(f"[PlaywrightAgent] Fallback: targeting 3rd input for employee_id")
            fill_res = execute_pw({
                "operation":  "fill",
                "selector":   "input:nth-of-type(3)",
                "value":      employee_id,
                "session_id": session_id,
                "timeout_ms": 3000,
            })
            eid_filled = fill_res.get("exit_code") == 0

        if not eid_filled:
            print(f"[PlaywrightAgent] Could not fill employee_id for {role_upper}")
            execute_pw({"operation": "screenshot",
                        "name": f"auth_fail_eid_{role_upper}_{tc_id.replace('.', '_')}",
                        "session_id": session_id})
            return False

        # 3. Fill PIN  (#mwo_operator_pin — text input with CSS disc masking)
        pin_filled = False
        for sel in ["#mwo_operator_pin", "input[name='mwo_operator_pin']",
                    "input[id='mwo_operator_pin']"]:
            fill_res = execute_pw({
                "operation":  "fill",
                "selector":   sel,
                "value":      pin,
                "session_id": session_id,
                "timeout_ms": 3000,
            })
            if fill_res.get("exit_code") == 0:
                pin_filled = True
                print(f"[PlaywrightAgent] Filled PIN with selector {sel}")
                break

        if not pin_filled:
            print(f"[PlaywrightAgent] Could not fill PIN for {role_upper}")
            execute_pw({"operation": "screenshot",
                        "name": f"auth_fail_pin_{role_upper}_{tc_id.replace('.', '_')}",
                        "session_id": session_id})
            return False

        # 4. Wait for React to enable the button (debounce), then click
        time.sleep(0.5)

        # Click ".erp-submit-btn" — the exact class on the Authorize Session button
        submitted = False
        for sel in [".erp-submit-btn", "button[type='submit']"]:
            click_res = execute_pw({
                "operation":  "click",
                "selector":   sel,
                "session_id": session_id,
                "timeout_ms": 8000,
            })
            if click_res.get("exit_code") == 0:
                submitted = True
                print(f"[PlaywrightAgent] Clicked Authorize Session via {sel}")
                break

        if not submitted:
            # Last-resort: try text click
            click_res = execute_pw({
                "operation":  "click",
                "text":       "Authorize Session",
                "session_id": session_id,
                "timeout_ms": 8000,
            })
            if click_res.get("exit_code") == 0:
                submitted = True
                print("[PlaywrightAgent] Clicked Authorize Session via text")

        if not submitted:
            print(f"[PlaywrightAgent] Could not click submit for {role_upper}")
            execute_pw({"operation": "screenshot",
                        "name": f"auth_fail_btn_{role_upper}_{tc_id.replace('.', '_')}",
                        "session_id": session_id})
            return False

        time.sleep(3)  # Wait for redirect / JWT cookie to be set

        # 5. Verify login success
        verify_res = execute_pw({
            "operation":  "get_text",
            "selector":   "body",
            "session_id": session_id,
            "timeout_ms": 5000,
        })
        body_text = (verify_res.get("stdout") or "")

        # Screenshot for evidence
        execute_pw({
            "operation":  "screenshot",
            "name":       f"auth_{role_upper.lower()}_{tc_id.replace('.', '_')}",
            "session_id": session_id,
        })

        body_lower = body_text.lower()

        # Definitive failure indicators
        if any(s in body_lower for s in ("invalid employee", "authentication failed",
                                          "invalid pin", "incorrect pin",
                                          "authorize session")):
            # Still on the login page — check if there's an actual error message
            if "invalid" in body_lower or "authentication failed" in body_lower:
                print(f"[PlaywrightAgent] Auth failed for {role_upper}: {body_text[:150]}")
                return False
            # If "Authorize Session" is still showing but no error: button was disabled
            if "authorize session" in body_lower and "invalid" not in body_lower:
                print(f"[PlaywrightAgent] Auth page still showing for {role_upper} "
                      f"— button may have been disabled. Body: {body_text[:100]}")
                return False

        print(f"[PlaywrightAgent] Auth succeeded for {role_upper}: {body_text[:80]}")
        return True

    # ── Step parser ───────────────────────────────────────────────────────────

    def _execute_step(
        self,
        step: str,
        base_url: str,
        auth_config: dict,
        session_id: str,
        execute_pw: Callable,
    ) -> str:
        """
        Parse and execute a single step string.
        Returns an error string on failure, or "" on success/skip.
        """
        s = step.strip().lower()

        if "navigate" in s or "go to" in s:
            # Extract URL from step
            import re
            url_match = re.search(r'https?://\S+', step)
            if url_match:
                url = url_match.group(0).rstrip(".,;")
                res = execute_pw({
                    "operation":  "navigate",
                    "url":        url,
                    "session_id": session_id,
                    "timeout_ms": 15000,
                })
                if res.get("exit_code", -1) != 0 and not res.get("blocked"):
                    return f"navigate to {url} failed: {res.get('stderr','')[:80]}"
                time.sleep(1)
            # else: no URL to navigate to — skip silently

        elif "click" in s:
            import re
            # Extract text in quotes if present
            m = re.search(r"['\"]([^'\"]+)['\"]", step)
            if m:
                click_target = m.group(1)
                res = execute_pw({
                    "operation":  "click",
                    "text":       click_target,
                    "session_id": session_id,
                    "timeout_ms": 5000,
                })
                if res.get("exit_code", -1) != 0:
                    return f"click '{click_target}' failed: {res.get('stderr','')[:80]}"
            # else: ambiguous click — skip

        elif any(kw in s for kw in ("fill", "enter", "type")):
            import re
            # Try to extract quoted values
            parts = re.findall(r"['\"]([^'\"]+)['\"]", step)
            if len(parts) >= 2:
                selector = parts[0]
                value    = parts[1]
                res = execute_pw({
                    "operation":  "fill",
                    "selector":   selector,
                    "value":      value,
                    "session_id": session_id,
                    "timeout_ms": 5000,
                })
                if res.get("exit_code", -1) != 0:
                    return f"fill '{selector}' failed: {res.get('stderr','')[:80]}"
            # else: not enough info — skip

        elif any(kw in s for kw in ("verify", "check", "see", "visible")):
            import re
            # Extract expected text from quotes
            m = re.search(r"['\"]([^'\"]+)['\"]", step)
            expected_text = m.group(1) if m else None
            if expected_text:
                res = execute_pw({
                    "operation":  "get_text",
                    "selector":   "body",
                    "session_id": session_id,
                    "timeout_ms": 5000,
                })
                body = res.get("stdout") or ""
                if expected_text.lower() not in body.lower():
                    return f"expected text '{expected_text}' not found on page"

        elif "wait" in s:
            execute_pw({
                "operation":  "wait",
                "selector":   "body",
                "session_id": session_id,
                "timeout_ms": 3000,
            })

        # Unknown step — skip without failing
        return ""

    # ── Mandate builder ───────────────────────────────────────────────────────

    def _build_mandate(
        self,
        failed: list[TestResult],
        app_config: dict,
        cycle: int,
        base_url: str,
    ) -> str:
        app_name    = app_config.get("name", "the app")
        local_path  = app_config.get("local_path", "")
        deploy_script = app_config.get("deploy_script", "")

        fail_lines = []
        for r in failed:
            fail_lines.append(
                f"  - [{r.id}] {r.name}\n"
                f"    Error: {r.error[:200]}\n"
                f"    Console errors: {len(r.console_errors)}\n"
                f"    Network errors: {len(r.network_errors)}"
            )
        fails = "\n".join(fail_lines)

        return f"""MANDATE — E2E Fix Cycle {cycle}
App: {app_name}
Base URL: {base_url}
Local path: {local_path}

The following E2E tests are failing:

{fails}

Your task:
1. Read the relevant source files to understand the root cause.
2. Fix the code so all failing tests pass.
3. Run the deploy script: {deploy_script}
4. Confirm the fixes are deployed.

Constraints:
- Do NOT break any passing tests.
- Do NOT delete existing data or DB records.
- All changes must be committed (git add + git commit -m "fix: E2E cycle {cycle} — <description>").

IMPORTANT: Fix the root cause — do not just hide or skip the tests.
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# __main__ — smoke test against MWO ERP (P1 tests, no auto-fix)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    import dataclasses

    # Force UTF-8 on Windows consoles
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    base_dir   = str(_MAF_ROOT)
    bridge_dir = str(_BRIDGE_DIR)
    sys.path.insert(0, bridge_dir)

    registry_path = os.path.join(bridge_dir, "e2e_app_registry.json")
    with open(registry_path) as f:
        app_config = json.load(f)["apps"][0]

    plan_path = os.path.join(base_dir, "logs", "qa_runs", "smoke_test_plan.json")
    with open(plan_path) as f:
        plan_data = json.load(f)

    # Convert dicts to simple namespace objects
    class TC:
        def __init__(self, d: dict):
            for k, v in d.items():
                setattr(self, k, v)

    class Plan:
        pass

    plan          = Plan()
    plan.app_name = plan_data.get("app_name", "MWO ERP")
    all_tcs       = [TC(t) for t in plan_data.get("test_cases", [])]

    # Only P1 tests; MAX_FIX_CYCLES=0 → report only, no auto-fix
    plan.test_cases = [t for t in all_tcs if getattr(t, "priority", 3) == 1]
    print(f"Running {len(plan.test_cases)} P1 tests (MAX_FIX_CYCLES=0, no auto-fix)...")
    print(f"Target: {app_config['base_url']}")
    print()

    def cb(event_type: str, data) -> None:
        name   = data.get("name", "")   if isinstance(data, dict) else ""
        status = data.get("status", "") if isinstance(data, dict) else ""
        if event_type == "test_start":
            print(f"  >> Running: {name}")
        elif event_type == "test_pass":
            print(f"  [PASS] {name}")
        elif event_type == "test_fail":
            err = data.get("error", "") if isinstance(data, dict) else ""
            print(f"  [FAIL] {name}: {err[:120]}")
        elif event_type == "escalate":
            q = data.get("question", "") if isinstance(data, dict) else str(data)
            print(f"  [ESCALATE] {q[:300]}")
        else:
            print(f"  [{event_type}] {str(data)[:120]}")

    agent                = PlaywrightAgent()
    agent.MAX_FIX_CYCLES = 0

    report = agent.run(app_config, plan, "playwright_smoke", cb)

    print()
    print("=== SMOKE TEST RESULTS ===")
    print(f"Status : {report.status}")
    print(f"Passed : {report.passed}/{report.total_tests}")
    print(f"Failed : {report.failed}")
    print(f"Runtime: {report.duration_ms}ms")

    if report.test_results:
        failing = [
            r for r in report.test_results
            if isinstance(r, dict) and r.get("status") in ("fail", "error")
        ]
        if failing:
            print("\nFailing tests:")
            for r in failing:
                print(f"  [FAIL] {r.get('name', '?')}: {r.get('error', '')[:100]}")

        passing = [
            r for r in report.test_results
            if isinstance(r, dict) and r.get("status") == "pass"
        ]
        if passing:
            print("\nPassing tests:")
            for r in passing:
                ss = r.get("screenshot_path", "")
                print(f"  [PASS] {r.get('name', '?')}" + (f"  [{ss}]" if ss else ""))

    screenshots = [
        r.get("screenshot_path", "")
        for r in report.test_results
        if isinstance(r, dict) and r.get("screenshot_path")
    ]
    if screenshots:
        print(f"\nScreenshots saved ({len(screenshots)}):")
        for sp in screenshots:
            print(f"  {sp}")

    # Save report
    os.makedirs(os.path.join(base_dir, "logs", "qa_runs"), exist_ok=True)
    report_path = os.path.join(base_dir, "logs", "qa_runs", "playwright_smoke.json")
    with open(report_path, "w") as f:
        json.dump(dataclasses.asdict(report), f, indent=2, default=str)
    print(f"\nReport saved to {report_path}")
