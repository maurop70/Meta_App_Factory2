"""
panel/chair.py — ClaudeAY panel, Phase 3: the Chair (drafts-then-ratified).
═════════════════════════════════════════════════════════════════════════════
The Chair turns Phase 2's faithful window (N independent analyses + the mechanical
disagreement capture) into ONE ratifiable plan. A DISTINCT chair-drafter model (not a
promoted seat) drafts; the HUMAN ratifies (accept / send-back / override). The human
never authors the synthesis from raw reviews.

The protection is NOT trusting the drafter. It is:
  (1) RECONCILIATION — the drafter's dissent ledger is checked, mechanically, against
      the Phase-2 disagreement artifact. Every captured dissent must be accounted for;
      a dropped dissent is a visible reconciliation FAILURE, not a silent omission. The
      original Phase-2 wording is preserved beside each disposition so softening is
      visible by comparison.
  (2) READABLE-ON-TOP, COMPLETE-UNDERNEATH — decision-relevant dissents surface in plain
      language; the full set is preserved beneath; the drafter must STATE the rule by
      which it judged relevance. Nothing is discarded, only folded down.
  (3) ONE PLAN, NEVER A BLEND — the output schema carries a single plan; set-aside seat
      recommendations are named in the ledger, so a blend would be visible.
  (4) SCOPE DECLARES BOTH where (workdir/subtrees) AND risk-ceiling (tier) — explicitly,
      nothing inferred after approval. This is exactly what Phase-4's mint consumes.

Send-back RE-DRAFTS from the existing seat reports by default (most send-backs are "you
synthesized this wrong"). A fresh seat re-run is a separate, explicitly-invoked action
(panel.session.run_panel) — never triggered automatically by a send-back.

INSPECTION/PROPOSAL ONLY. The Chair drafts and the human ratifies, but nothing mints,
declares a token, or reaches the executor. The scope field is produced and shown, NOT
wired to the gate (Phase 4). Same import discipline (no executor path). Credentials (C2):
keys never logged (handled in lineage).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

BRIDGE_ROOT = Path(__file__).resolve().parent.parent
PANEL_DIR = Path(__file__).resolve().parent
for _p in (str(PANEL_DIR), str(BRIDGE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lineage                                    # panel.lineage (sibling)

SESSIONS_DIR = BRIDGE_ROOT / "logs" / "panel_sessions"
CHAIR_DIR = BRIDGE_ROOT / "logs" / "panel_chair"

# The chair-drafter is a DISTINCT ROLE (its own spec), provider-configurable. Its
# lineage need not differ from a seat — the protection is the reconcilable ledger, not
# lineage independence. The actual responding model is recorded for provenance.
def _chair_spec() -> lineage.SeatSpec:
    provider = os.getenv("PANEL_CHAIR_PROVIDER", "anthropic").strip().lower()
    family, _, keyenv = lineage._PROVIDERS.get(provider, (provider, None, "ANTHROPIC_API_KEY"))
    model = os.getenv("PANEL_CHAIR_MODEL", "claude-sonnet-4-6")
    return lineage.SeatSpec("chair", provider, family, keyenv, model)


# ── Enumerate the Phase-2 dissents into stable ids the ledger must reconcile to ──
def enumerate_dissents(session: dict) -> list[dict]:
    d = session.get("disagreements") or {}
    out: list[dict] = []
    if d.get("recommendation_divergent"):
        out.append({"id": "D-REC", "kind": "recommendation",
                    "item": f"reviewers split on the recommendation: {d.get('recommendations')}"})
    for i, x in enumerate(d.get("risk_divergence", []), 1):
        out.append({"id": f"D-R{i}", "kind": "risk",
                    "item": x["item"], "raised_by": x["raised_by"], "missed_by": x["missed_by"]})
    for i, x in enumerate(d.get("claim_divergence", []), 1):
        out.append({"id": f"D-C{i}", "kind": "claim",
                    "item": x["item"], "raised_by": x.get("raised_by", [])})
    return out


def _parse_json_block(content: str) -> dict | None:
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", content or "", re.DOTALL)
    raw = blocks[-1] if blocks else None
    if not raw:
        m = re.search(r"\{.*\"dissents\".*\}", content or "", re.DOTALL)
        raw = m.group(0) if m else None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


_CHAIR_PROMPT = """You are the CHAIR of a review panel. You did NOT review the question \
yourself — your job is to SYNTHESIZE the independent reviewers' analyses into exactly ONE \
plan, and to keep an honest ledger of EVERY disagreement, including the ones you set aside.

QUESTION:
{question}
{steer}
REVIEWERS' FULL ANALYSES:
{analyses}

CAPTURED DISAGREEMENTS — the faithful mechanical record. You MUST address EVERY id below \
with its own ledger entry; do not omit, merge, or rename any id:
{dissents}

Output a single fenced json block with EXACTLY this shape:
```json
{{"plan": "<ONE coherent plan — decide; do NOT blend contradictory options>",
  "scope": {{"workdir": ["<repo subtree the build may touch>"], "tier_ceiling": 0}},
  "relevance_rule": "<the rule you used to judge which dissents are decision-relevant>",
  "dissents": [{{"id": "<id from the list>", "disposition": "adopted|set-aside", "decision_relevant": true, "why": "<plain-language reason>"}}]}}
```
tier_ceiling is 0 (read-only), 1 (local edits), 2 (version control), or 3 (deploy/irreversible). \
Address every id; one dissents entry per id."""


def draft(session: dict, steer: str = "", max_tokens: int = 4000) -> dict:
    """Draft ONE ChairPlan from the persisted Phase-2 session. Reconciles its ledger
    against the captured dissents. Returns a ChairPlan dict (never mints, never executes)."""
    dissents = enumerate_dissents(session)
    analyses = "\n\n".join(
        f"### {s['seat']} ({s['actual_family']}, {s['actual_model_id']}) — rec={s['stance']['recommendation']}\n{_seat_body(session, s)}"
        for s in session["seats"] if s["status"] == "verified")
    prompt = _CHAIR_PROMPT.format(
        question=session["question"],
        steer=(f"\nHUMAN CHAIR STEER (incorporate this): {steer}\n" if steer else "\n"),
        analyses=analyses,
        dissents="\n".join(f"  [{x['id']}] ({x['kind']}) {x['item']}" for x in dissents) or "  (none)")

    spec = _chair_spec()
    run = lineage.run_seat(spec, prompt, max_tokens=max_tokens)
    parsed = _parse_json_block(run.content) if run.status == "verified" else None

    recon = reconcile(parsed, dissents)
    chairplan = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session["session_id"],
        "chair_provenance": {"requested_model": spec.model, "actual_model_id": run.actual_model_id,
                             "actual_family": run.actual_family, "status": run.status, "reason": run.reason},
        "steer": steer or None,
        "plan": (parsed or {}).get("plan") if parsed else None,
        "scope": _validate_scope((parsed or {}).get("scope") if parsed else None),
        "relevance_rule": (parsed or {}).get("relevance_rule") if parsed else None,
        "dissent_ledger": _build_ledger(parsed, dissents),
        "reconciliation": recon,
        "one_plan_ok": bool(parsed and isinstance(parsed.get("plan"), str) and parsed.get("plan").strip()),
        "status": "drafted",
        "raw": run.content,
    }
    return chairplan


def _seat_body(session: dict, seat: dict) -> str:
    """Pull the seat's full analysis from its persisted report (truncated for the prompt)."""
    try:
        rep = json.load(open(seat["report_path"], encoding="utf-8"))
        return rep.get("display_content", "")[:3500]
    except Exception:
        return "(analysis unavailable)"


def _validate_scope(scope) -> dict:
    """Scope must declare BOTH where (non-empty workdir) AND a risk ceiling (tier 0-3).
    Anything missing is flagged — nothing is inferred after the fact."""
    ok = (isinstance(scope, dict) and isinstance(scope.get("workdir"), list)
          and len(scope["workdir"]) > 0 and scope.get("tier_ceiling") in (0, 1, 2, 3))
    return {"declared": scope, "well_formed": bool(ok),
            "missing": [] if ok else [k for k in ("workdir", "tier_ceiling")
                                       if not (scope or {}).get(k) and (scope or {}).get(k) != 0]}


def reconcile(parsed: dict | None, dissents: list[dict]) -> dict:
    """MECHANICAL check: every captured Phase-2 dissent id must appear in the chair's
    ledger. A dropped id is a visible omission (the protection — not trust in the drafter)."""
    captured = {x["id"] for x in dissents}
    addressed = {str(e.get("id")) for e in (parsed or {}).get("dissents", [])} if parsed else set()
    missing = sorted(captured - addressed)
    extra = sorted(addressed - captured)
    return {"captured": len(captured), "addressed": len(addressed & captured),
            "missing": missing, "extra": extra,
            "ok": len(missing) == 0 and parsed is not None,
            "verdict": ("RECONCILED" if (parsed is not None and not missing)
                        else "OMISSION" if missing else "UNPARSEABLE")}


def _build_ledger(parsed: dict | None, dissents: list[dict]) -> dict:
    """Readable on top (decision-relevant), complete underneath (full set), with the
    original Phase-2 wording preserved beside each disposition so softening is visible."""
    by_id = {x["id"]: x for x in dissents}
    entries = []
    for e in (parsed or {}).get("dissents", []):
        did = str(e.get("id"))
        src = by_id.get(did, {})
        entries.append({
            "id": did,
            "original_phase2_item": src.get("item", "(NOT IN PHASE-2 CAPTURE)"),
            "kind": src.get("kind"),
            "disposition": e.get("disposition"),
            "decision_relevant": bool(e.get("decision_relevant")),
            "why": e.get("why", ""),
        })
    # any captured dissent the drafter never addressed → surfaced explicitly, not dropped
    addressed_ids = {en["id"] for en in entries}
    for x in dissents:
        if x["id"] not in addressed_ids:
            entries.append({"id": x["id"], "original_phase2_item": x["item"], "kind": x["kind"],
                            "disposition": "OMITTED-BY-DRAFTER", "decision_relevant": None,
                            "why": "(drafter did not address this captured dissent — surfaced by reconciliation)"})
    relevant = [e for e in entries if e["decision_relevant"] is True]
    return {"relevance_rule": (parsed or {}).get("relevance_rule"),
            "decision_relevant": relevant, "full": entries}


# ── Human-chair ratification (accept / send-back / override) ────────────────
def ratification_hash(chairplan: dict) -> str:
    """Canonical hash of the parts that must NOT change between the ratify gate and the
    mint gate: the plan, the declared scope, and each dissent's id+disposition. The mint
    re-checks this — if the plan changed after ratification, the mint refuses (no gap
    between approved and enforced)."""
    canon = json.dumps({
        "plan": chairplan.get("plan"),
        "scope": (chairplan.get("scope") or {}).get("declared"),
        "ledger": [(e.get("id"), e.get("disposition"))
                   for e in (chairplan.get("dissent_ledger") or {}).get("full", [])],
    }, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def accept(chairplan: dict) -> dict:
    """Gate 1 — the human ratifies the synthesis as faithful. Stamps a ratification hash
    binding the EXACT plan; the mint gate (gate.py) verifies it before authorizing."""
    chairplan["status"] = "ratified"
    chairplan["ratified_ts"] = datetime.now(timezone.utc).isoformat()
    chairplan["ratification_hash"] = ratification_hash(chairplan)
    return _persist(chairplan)


def send_back(session: dict, steer: str) -> dict:
    """Default send-back: RE-DRAFT from the existing seat reports with the human's steer.
    (A fresh seat re-run is a separate explicit action: panel.session.run_panel.)"""
    cp = draft(session, steer=steer)
    cp["status"] = "redrafted_from_sendback"
    return _persist(cp)


def override(chairplan: dict, override_text: str) -> dict:
    chairplan["status"] = "overridden"
    chairplan["human_override"] = override_text          # recorded verbatim
    chairplan["overridden_ts"] = datetime.now(timezone.utc).isoformat()
    return _persist(chairplan)


def _persist(chairplan: dict) -> dict:
    CHAIR_DIR.mkdir(parents=True, exist_ok=True)
    fn = f"{chairplan['session_id']}_{chairplan['status']}_{uuid.uuid4().hex[:6]}.json"
    (CHAIR_DIR / fn).write_text(json.dumps(chairplan, indent=2), encoding="utf-8")
    chairplan["_artifact"] = str(CHAIR_DIR / fn)
    return chairplan


def latest_session() -> dict:
    files = sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise SystemExit("no Phase-2 session found — run panel/session.py first")
    return json.loads(files[0].read_text(encoding="utf-8"))


def _print(cp: dict) -> None:
    r = cp["reconciliation"]; sc = cp["scope"]
    print(f"  status={cp['status']}  chair={cp['chair_provenance']['actual_model_id']}  one_plan_ok={cp['one_plan_ok']}")
    print(f"  RECONCILIATION: {r['verdict']}  captured={r['captured']} addressed={r['addressed']} missing={r['missing']}")
    print(f"  SCOPE: well_formed={sc['well_formed']}  declared={sc['declared']}")
    print(f"  relevance_rule: {cp['dissent_ledger']['relevance_rule']}")
    print(f"  ledger: {len(cp['dissent_ledger']['decision_relevant'])} decision-relevant / "
          f"{len(cp['dissent_ledger']['full'])} total")
    if cp.get("plan"):
        print(f"  plan opens: {cp['plan'][:140].strip()!r}")


if __name__ == "__main__":
    session = latest_session()
    print(f"=== CHAIR over Phase-2 session {session['session_id']} ({session['depth_label']}) ===")

    print("\n[1] DRAFT (one plan + reconciled ledger + scope):")
    cp = draft(session)
    _print(cp)

    print("\n[2] RECONCILIATION CATCHES A DROPPED DISSENT (tamper test — watch it fire):")
    tampered = json.loads(json.dumps(cp))
    dissents = enumerate_dissents(session)
    if dissents:
        drop = dissents[0]["id"]
        # simulate a drafter that silently omitted the first dissent
        fake = {"plan": cp.get("plan"), "relevance_rule": cp["dissent_ledger"]["relevance_rule"],
                "dissents": [{"id": e["id"]} for e in cp["dissent_ledger"]["full"] if e["id"] != drop]}
        rec = reconcile(fake, dissents)
        print(f"    dropped {drop} → verdict={rec['verdict']}  missing={rec['missing']}  (omission is VISIBLE, not silent)")

    print("\n[3] SEND-BACK (re-draft from existing reports with a human steer):")
    cp2 = send_back(session, steer="Weight operational/monitoring risks more heavily.")
    _print(cp2)

    print("\n[4] OVERRIDE (recorded verbatim):")
    cp3 = override(cp2, "Chair override: cap tier_ceiling at 1 regardless of draft.")
    print(f"    status={cp3['status']}  human_override={cp3['human_override']!r}  artifact={cp3['_artifact']}")

    print("\n[5] ACCEPT (ratified artifact):")
    cp_final = accept(cp)
    print(f"    status={cp_final['status']}  artifact={cp_final['_artifact']}")
