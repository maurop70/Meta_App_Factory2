"""
Auditor — independent read-only verifier (CLAUDE_RULES.md §15, §13.3)
----------------------------------------------------------------------
The third role in the triad: Architect plans, Executor acts, Auditor
verifies. The loop engine refuses to accept a COMPLETE ledger for any
Tier ≥ 1 mandate until the Auditor confirms the executor's claims
against ground truth — never against the ledger's own prose.

Checks (all read-only, or isolated suite re-runs):
  1. files_changed claims  → paths exist on disk
  2. git claims            → `git status --porcelain` (read-only) is consistent:
                             a ledger claiming commits must not leave its
                             changed files dirty in the tree
  3. verification contracts→ re-run contract suites named in tests_run and
                             compare pass counts to rules/verification_contracts.json
  4. health probes         → contract URLs return their expected status

Every audit is logged to logs/audit_reports.jsonl with the run trace_id.
"""

import base64
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

BRIDGE_ROOT   = Path(__file__).parent
MAF_ROOT      = BRIDGE_ROOT.parent
CONTRACTS     = BRIDGE_ROOT / "rules" / "verification_contracts.json"
AUDIT_REPORTS = BRIDGE_ROOT / "logs" / "audit_reports.jsonl"

SUITE_TIMEOUT = 300  # seconds per suite

# ── Visual critic (multimodal layout review) ─────────────────────────────────
SCREENSHOT_DIR     = BRIDGE_ROOT / "logs" / "playwright_screenshots"
_FRONTEND_EXTS     = (".jsx", ".tsx", ".css", ".html", ".vue")
_MAX_SCREENSHOT_MB = 4
# Strict mode: critic unavailable (no key / no response) fails the audit.
# Default lenient: unavailability is reported loudly but does not block.
VISUAL_STRICT_ENV  = "CLAUDEAY_VISUAL_STRICT"

DESIGN_GUIDELINES = (
    "Audit this UI screenshot against these design rules: "
    "(1) no overlapping or clipped elements; (2) no horizontal overflow or "
    "content escaping its container; (3) consistent spacing and alignment "
    "within sections; (4) readable text contrast; (5) tables >5 columns must "
    "reflow, not shrink to illegibility; (6) modals/overlays must cover and "
    "dim background content; (7) no raw placeholder text, broken icons, or "
    "unstyled native widgets in styled contexts."
)

_VISUAL_PROMPT = (
    f"{DESIGN_GUIDELINES}\n\n"
    "Respond with EXACTLY one JSON object and nothing else:\n"
    '{"verdict": "PASS" or "FAIL", "violations": ["<short description>", ...]}\n'
    "Only report clear violations visible in the screenshot; cosmetic taste "
    "preferences are not violations."
)


def _parse_visual_verdict(response: str) -> tuple[bool, list[str]]:
    """Parse the critic's JSON verdict; fall back to token scan."""
    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        obj = json.loads(response[start:end])
        verdict = str(obj.get("verdict", "")).strip().upper()
        violations = [str(v)[:160] for v in (obj.get("violations") or [])][:8]
        if verdict in ("PASS", "FAIL"):
            return verdict == "PASS", violations
    except (ValueError, json.JSONDecodeError):
        pass
    # Fallback: explicit FAIL token anywhere in a non-JSON response
    return ("FAIL" not in response.upper()), []


def _check_visual(files_changed: list) -> list:
    """
    Multimodal layout critique: when frontend files changed, send the most
    recent Playwright screenshot to the vision model with design guidelines.
    Returns [] when not applicable (no frontend files / no screenshots).
    """
    frontend = [f for f in (files_changed or [])
                if str(f).lower().endswith(_FRONTEND_EXTS)]
    if not frontend:
        return []
    strict = os.getenv(VISUAL_STRICT_ENV, "false").lower() == "true"

    if not SCREENSHOT_DIR.exists():
        return [AuditCheck("visual_critic", not strict,
                           "no screenshots directory — layout not evaluated")]
    shots = sorted(SCREENSHOT_DIR.glob("*.png"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    if not shots:
        return [AuditCheck("visual_critic", not strict,
                           "no screenshots found — layout not evaluated")]
    shot = shots[0]
    if shot.stat().st_size > _MAX_SCREENSHOT_MB * 1024 * 1024:
        return [AuditCheck("visual_critic", not strict,
                           f"screenshot {shot.name} exceeds {_MAX_SCREENSHOT_MB}MB — skipped")]

    try:
        sys.path.insert(0, str(MAF_ROOT))
        from model_router import route_multimodal
        b64 = base64.b64encode(shot.read_bytes()).decode("ascii")
        response = route_multimodal("visual_critic", _VISUAL_PROMPT, b64)
    except Exception as e:
        return [AuditCheck("visual_critic", not strict,
                           f"visual critic error: {str(e)[:120]}")]

    if not response:
        # Loud, never silent (CLAUDE_RULES 0.3) — but only blocking in strict mode
        return [AuditCheck("visual_critic", not strict,
                           "visual critic unavailable (no API key or empty "
                           "response) — layout NOT evaluated")]

    passed, violations = _parse_visual_verdict(response)
    detail = (f"{shot.name}: " +
              ("; ".join(violations) if violations
               else ("clean" if passed else response[:160])))
    return [AuditCheck("visual_critic", passed, detail[:300])]


@dataclass
class AuditCheck:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class AuditReport:
    verified: bool
    checks: list = field(default_factory=list)

    def summary(self) -> str:
        failed = [c for c in self.checks if not c.ok]
        if not failed:
            return f"audit passed ({len(self.checks)} checks)"
        return ("audit FAILED: "
                + "; ".join(f"{c.name}: {c.detail}"[:120] for c in failed[:3]))


def _load_contracts() -> dict:
    try:
        data = json.loads(CONTRACTS.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {}


def _infer_app(instruction: str, files_changed: list) -> str | None:
    """Pick the contract app whose cwd appears in the instruction or files."""
    contracts = _load_contracts()
    haystack = (instruction or "").lower() + " " + " ".join(
        str(f).lower() for f in (files_changed or []))
    for app, cfg in contracts.items():
        cwd = str(cfg.get("cwd", "")).lower().replace("\\", "/")
        if cwd and cwd in haystack.replace("\\", "/"):
            return app
    if "erp" in haystack:
        return "erp_maintenance" if "erp_maintenance" in contracts else None
    return None


def _check_files_exist(files_changed: list) -> list[AuditCheck]:
    checks = []
    for f in (files_changed or [])[:20]:
        p = Path(f)
        if not p.is_absolute():
            p = MAF_ROOT / f
        checks.append(AuditCheck(
            name=f"file_exists:{f}",
            ok=p.exists(),
            detail="" if p.exists() else "claimed changed but not found on disk",
        ))
    return checks


def _check_git_consistency(files_changed: list, claims_commit: bool) -> list[AuditCheck]:
    """Read-only: if the ledger claims a commit, its files must not be dirty."""
    if not claims_commit or not files_changed:
        return []
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(MAF_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        if proc.returncode != 0:
            return [AuditCheck("git_status", False, proc.stderr.strip()[:120])]
        dirty = {line[3:].strip().replace("\\", "/")
                 for line in proc.stdout.splitlines() if line.strip()}
        checks = []
        for f in files_changed[:20]:
            rel = str(f).replace("\\", "/")
            is_dirty = any(rel.endswith(d) or d.endswith(rel) for d in dirty)
            checks.append(AuditCheck(
                name=f"committed:{f}",
                ok=not is_dirty,
                detail="" if not is_dirty else "still dirty despite claimed commit",
            ))
        return checks
    except Exception as e:
        return [AuditCheck("git_status", False, str(e)[:120])]


def _run_suite(suite: str, cwd: Path) -> tuple[int | None, int | None, str]:
    """Run one suite, parse 'RESULT: N passed, M failed' or 'N/N passed'."""
    try:
        proc = subprocess.run(
            [sys.executable, suite],
            cwd=str(cwd), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=SUITE_TIMEOUT,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        import re
        m = re.search(r"RESULT:\s*(\d+)\s+passed,\s*(\d+)\s+failed", out)
        if m:
            return int(m.group(1)), int(m.group(2)), out[-300:]
        m = re.search(r"(\d+)/(\d+)\s+passed", out)
        if m:
            passed, total = int(m.group(1)), int(m.group(2))
            return passed, total - passed, out[-300:]
        return None, None, f"unparseable output (exit {proc.returncode}): {out[-200:]}"
    except subprocess.TimeoutExpired:
        return None, None, f"suite timed out after {SUITE_TIMEOUT}s"
    except Exception as e:
        return None, None, str(e)[:200]


def _check_contracts(app: str, tests_claimed: list) -> list[AuditCheck]:
    """Re-run contract suites the ledger claims, compare against registry."""
    contracts = _load_contracts()
    cfg = contracts.get(app)
    if not cfg:
        return []
    cwd = MAF_ROOT / cfg.get("cwd", ".")
    suites_contract: dict = cfg.get("suites", {})
    claimed_names = {str(t.get("suite", "")) for t in (tests_claimed or [])
                     if isinstance(t, dict)}

    checks = []
    for suite, expected in suites_contract.items():
        if claimed_names and suite not in claimed_names:
            continue  # only re-verify what the ledger claims it ran
        if not (cwd / suite).exists():
            checks.append(AuditCheck(f"suite:{suite}", False, "suite file missing"))
            continue
        passed, failed, detail = _run_suite(suite, cwd)
        if passed is None:
            checks.append(AuditCheck(f"suite:{suite}", False, detail))
        elif failed and failed > 0:
            checks.append(AuditCheck(f"suite:{suite}", False,
                                     f"{failed} failing (got {passed} passed)"))
        elif expected is not None and passed != expected:
            checks.append(AuditCheck(
                f"suite:{suite}", False,
                f"CONTRACT DRIFT: {passed} passed, contract expects {expected}"))
        else:
            checks.append(AuditCheck(f"suite:{suite}", True,
                                     f"{passed} passed (contract {expected or 'any'})"))
    return checks


def _check_health(app: str) -> list[AuditCheck]:
    contracts = _load_contracts()
    cfg = contracts.get(app) or {}
    checks = []
    for probe in cfg.get("health", []):
        try:
            import httpx
            r = httpx.get(probe["url"], timeout=10, follow_redirects=True)
            ok = r.status_code == probe.get("expect", 200)
            checks.append(AuditCheck(
                f"health:{probe.get('name', probe['url'])}", ok,
                f"HTTP {r.status_code} (expect {probe.get('expect', 200)})"))
        except Exception as e:
            checks.append(AuditCheck(
                f"health:{probe.get('name', probe.get('url','?'))}", False, str(e)[:120]))
    return checks


def audit(instruction: str, ledger_result, trace_id: str = "",
          run_suites: bool = True, probe_health: bool = False,
          check_visual: bool = True) -> AuditReport:
    """
    Verify an executor's COMPLETE/ITERATE claims against ground truth.
    ledger_result: LedgerResult from ledger_evaluator (structured fields used).
    """
    files_changed = getattr(ledger_result, "files_changed", []) or []
    tests_run     = getattr(ledger_result, "tests_run", []) or []
    summary_text  = (getattr(ledger_result, "summary", "") or "").lower()
    claims_commit = any(w in summary_text for w in ("commit", "pushed", "sealed"))

    checks: list[AuditCheck] = []
    checks += _check_files_exist(files_changed)
    checks += _check_git_consistency(files_changed, claims_commit)

    app = _infer_app(instruction, files_changed)
    if app and run_suites and tests_run:
        checks += _check_contracts(app, tests_run)
    if app and probe_health:
        checks += _check_health(app)
    if check_visual:
        checks += _check_visual(files_changed)

    if not checks:
        # Nothing auditable claimed — pass with an explicit note so the
        # loop engine can decide whether "no claims" is acceptable.
        checks.append(AuditCheck("no_verifiable_claims", True,
                                 "ledger made no claims the auditor can check"))

    report = AuditReport(verified=all(c.ok for c in checks), checks=checks)
    try:
        AUDIT_REPORTS.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_REPORTS, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
                "verified": report.verified,
                "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail}
                           for c in report.checks],
            }) + "\n")
    except Exception:
        pass
    return report
