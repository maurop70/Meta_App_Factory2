"""
Nightly Self-Check + Weekly Digest
-----------------------------------
The heartbeat: every night ClaudeAY verifies its own world and writes a
report a human can read over coffee.

  python self_check.py          — nightly check (suites, health, backups)
  python self_check.py digest   — weekly digest (loop/autonomy/episode stats)

Nightly checks:
  1. All verification-contract suites pass at their expected counts
  2. Production health probes return their expected status
  3. The Google Drive backup mirror is fresh (< 48h)
  4. Pending rule proposals awaiting operator review (count surfaced)

Reports: logs/self_check_reports.jsonl (+ console). Failures also POST to
the QA alerts endpoint when the factory is running, and always exit 1 so
Task Scheduler records the failure.
"""

import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

BRIDGE_ROOT = Path(__file__).parent
sys.path.insert(0, str(BRIDGE_ROOT))

import auditor  # reuses contract suite runner + registry

REPORTS_LOG   = BRIDGE_ROOT / "logs" / "self_check_reports.jsonl"
# Relocated 2026-06-12: backups moved to Drive root (matches backup_dev.ps1)
BACKUP_DEST   = Path(r"C:\Users\mpetr\My Drive\backups\Dev")
BACKUP_MAX_AGE_H = 48
PENDING_RULES = BRIDGE_ROOT / "rules" / "pending_rules.jsonl"


def _check_contract_suites() -> list[dict]:
    results = []
    contracts = auditor._load_contracts()
    for app, cfg in contracts.items():
        cwd = BRIDGE_ROOT.parent / cfg.get("cwd", ".")
        for suite, expected in cfg.get("suites", {}).items():
            suite_path = cwd / suite
            if not suite_path.exists():
                results.append({"check": f"{app}/{suite}", "ok": False,
                                "detail": "suite file missing"})
                continue
            passed, failed, detail = auditor._run_suite(suite, cwd)
            if passed is None:
                results.append({"check": f"{app}/{suite}", "ok": False, "detail": detail})
            elif failed and failed > 0:
                results.append({"check": f"{app}/{suite}", "ok": False,
                                "detail": f"{failed} failing"})
            elif expected is not None and passed != expected:
                results.append({"check": f"{app}/{suite}", "ok": False,
                                "detail": f"CONTRACT DRIFT: {passed} != {expected}"})
            else:
                results.append({"check": f"{app}/{suite}", "ok": True,
                                "detail": f"{passed} passed (contract {expected or 'any'})"})
    return results


def _check_health() -> list[dict]:
    results = []
    contracts = auditor._load_contracts()
    for app, cfg in contracts.items():
        for c in auditor._check_health(app) if cfg.get("health") else []:
            results.append({"check": c.name, "ok": c.ok, "detail": c.detail})
    return results


def _check_backup_freshness() -> list[dict]:
    if not BACKUP_DEST.exists():
        return [{"check": "backup_mirror", "ok": False,
                 "detail": f"destination missing: {BACKUP_DEST}"}]
    try:
        newest = 0.0
        # Marker-based freshness: scan a bounded subtree, not 100k files
        probe = BACKUP_DEST / "Antigravity_AI_Agents" / "Meta_App_Factory"
        scan_root = probe if probe.exists() else BACKUP_DEST
        for i, p in enumerate(scan_root.rglob("*")):
            if p.is_file():
                newest = max(newest, p.stat().st_mtime)
            if i > 5000:
                break
        age_h = (time.time() - newest) / 3600 if newest else 1e9
        ok = age_h < BACKUP_MAX_AGE_H
        return [{"check": "backup_mirror", "ok": ok,
                 "detail": f"newest file {age_h:.1f}h old (max {BACKUP_MAX_AGE_H}h)"}]
    except Exception as e:
        return [{"check": "backup_mirror", "ok": False, "detail": str(e)[:120]}]


def _count_pending_rules() -> int:
    if not PENDING_RULES.exists():
        return 0
    count = 0
    for line in PENDING_RULES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                if json.loads(line).get("status") == "pending":
                    count += 1
            except json.JSONDecodeError:
                pass
    return count


def nightly() -> int:
    print(f"=== ClaudeAY Self-Check — {datetime.now(timezone.utc).isoformat()} ===\n")
    checks = []
    checks += _check_contract_suites()
    checks += _check_health()
    checks += _check_backup_freshness()

    for c in checks:
        print(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['check']}: {c['detail']}")
    pending = _count_pending_rules()
    if pending:
        print(f"\n  NOTE: {pending} rule proposal(s) await operator review "
              f"(python postmortem.py list)")

    all_ok = all(c["ok"] for c in checks)
    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": "nightly",
        "ok": all_ok,
        "checks": checks,
        "pending_rules": pending,
    }
    REPORTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORTS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(report) + "\n")

    if not all_ok:
        try:
            import httpx
            httpx.post("http://127.0.0.1:5030/api/qa/alerts", timeout=5, json={
                "source": "SELF_CHECK", "severity": "HIGH",
                "message": "; ".join(f"{c['check']}: {c['detail']}"
                                     for c in checks if not c["ok"])[:500],
            })
        except Exception:
            pass

    print(f"\n=== {'ALL CHECKS PASSED' if all_ok else 'FAILURES DETECTED'} ===")
    return 0 if all_ok else 1


def _tail_jsonl(path: Path, since: datetime) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
            ts = e.get("ts") or e.get("timestamp") or ""
            if ts and ts >= since.isoformat():
                out.append(e)
        except json.JSONDecodeError:
            continue
    return out


def digest() -> int:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    logs = BRIDGE_ROOT / "logs"
    loop_events = _tail_jsonl(logs / "loop_history.jsonl", since)
    autonomy    = _tail_jsonl(logs / "autonomy_events.jsonl", since)
    episodes    = _tail_jsonl(logs / "episodes.jsonl", since)
    audits      = _tail_jsonl(logs / "audit_reports.jsonl", since)
    selfchecks  = _tail_jsonl(logs / "self_check_reports.jsonl", since)
    recipes     = _tail_jsonl(logs / "deploy_recipes.jsonl", since)

    by_status = {}
    for ep in episodes:
        by_status[ep.get("status", "?")] = by_status.get(ep.get("status", "?"), 0) + 1

    print(f"=== ClaudeAY Weekly Digest — week ending "
          f"{datetime.now(timezone.utc).date()} ===\n")
    print(f"  Loop runs (episodes): {len(episodes)}  {by_status or ''}")
    print(f"  Loop events logged  : {len(loop_events)}")
    print(f"  Autonomy events     : {len(autonomy)} "
          f"({sum(1 for a in autonomy if a.get('status') == 'triggered')} fired, "
          f"{sum(1 for a in autonomy if a.get('status') == 'circuit_open')} circuit-opens)")
    print(f"  Audits              : {len(audits)} "
          f"({sum(1 for a in audits if not a.get('verified'))} rejections)")
    print(f"  Deploys             : {len(recipes)}")
    nightly_fails = [s for s in selfchecks if s.get("kind") == "nightly" and not s.get("ok")]
    print(f"  Self-checks         : {len(selfchecks)} ({len(nightly_fails)} failed)")
    print(f"  Pending rules       : {_count_pending_rules()} awaiting review")

    if by_status.get("error", 0) or nightly_fails:
        print("\n  NOTE: Review needed: failed runs or self-checks this week.")
    report = {
        "ts": datetime.now(timezone.utc).isoformat(), "kind": "digest",
        "episodes": len(episodes), "by_status": by_status,
        "autonomy_events": len(autonomy), "audits": len(audits),
        "deploys": len(recipes), "pending_rules": _count_pending_rules(),
    }
    with open(REPORTS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(report) + "\n")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "nightly"
    sys.exit(digest() if mode == "digest" else nightly())
