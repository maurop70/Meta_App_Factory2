"""
panel/session.py — ClaudeAY panel, Phase 2: deep model-reviewer seats over one
question, persisted, with FAITHFUL (mechanical, synthesis-free) disagreement capture.
═════════════════════════════════════════════════════════════════════════════
Reuses warroom_protocol.WarRoomReport + ReportStore (agent-agnostic) as-is. Seats
run behind the Phase-1 fail-closed caller (panel.lineage.run_seat) — NEVER
model_router (which silently substitutes families). Each seat self-reports its OWN
stance; disagreement is captured by MECHANICAL comparison of those stances — no model
interprets the dissent (that is the chair's accountable job, Phase 3).

Honest depth: the panel runs at whatever depth verifies (today two-deep: Claude +
Gemini, with the third seat wired-but-not-enabled). It is labeled as such — never
presented as a finished three-seat panel. With <2 distinct families it REFUSES
(consistent with Phase 1).

INSPECTION ONLY. No plan, no scope field, no mint, no executor path. Writes seat
reports (via ReportStore) + a session/disagreements artifact. Nothing here can cause
the executor to act. Credentials (C2): keys never logged (handled in lineage).
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

BRIDGE_ROOT = Path(__file__).resolve().parent.parent
MAF_ROOT = BRIDGE_ROOT.parent
PANEL_DIR = Path(__file__).resolve().parent
for _p in (str(PANEL_DIR), str(BRIDGE_ROOT), str(MAF_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lineage                                   # panel.lineage (sibling)
import warroom_protocol as wp                    # WarRoomReport + ReportStore (reused as-is)

SESSIONS_DIR = BRIDGE_ROOT / "logs" / "panel_sessions"
REPORTS_BASE = BRIDGE_ROOT / "logs" / "panel_reports"

_REVIEW_PROMPT = """You are an INDEPENDENT technical reviewer on a panel. Analyze the \
question below entirely on its own merits and give your own full reasoning. Do NOT \
defer to, assume, or imitate any other reviewer — your value is your independent view.

QUESTION:
{question}

Give a thorough analysis: assumptions, key tradeoffs, and concrete risks. Then, as the \
VERY LAST thing in your reply, output a single fenced json block with exactly these keys:
```json
{{"recommendation": "PROCEED|REVISE|REJECT", "risks": ["short risk", "..."], "key_claims": ["short claim", "..."]}}
```"""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _parse_stance(content: str) -> dict:
    """Extract the seat's self-reported stance from its own reply. Best-effort and
    honest: if it can't be parsed, the stance is UNKNOWN (never fabricated)."""
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", content or "", re.DOTALL)
    raw = blocks[-1] if blocks else None
    if not raw:
        m = re.search(r"\{[^{}]*\"recommendation\"[^{}]*\}", content or "", re.DOTALL)
        raw = m.group(0) if m else None
    if not raw:
        return {"recommendation": "UNKNOWN", "risks": [], "key_claims": [], "parsed": False}
    try:
        d = json.loads(raw)
        return {
            "recommendation": str(d.get("recommendation", "UNKNOWN")).upper().strip(),
            "risks": [str(x) for x in (d.get("risks") or [])],
            "key_claims": [str(x) for x in (d.get("key_claims") or [])],
            "parsed": True,
        }
    except Exception:
        return {"recommendation": "UNKNOWN", "risks": [], "key_claims": [], "parsed": False}


def capture_disagreements(stances: list[dict]) -> dict:
    """MECHANICAL, synthesis-free. Compares what the seats ACTUALLY said — divergent
    recommendations, and risks/claims raised by some verified seats but not all.
    No model interprets this."""
    verified = [s for s in stances if s["status"] == "verified"]
    recs = {s["seat"]: s["stance"]["recommendation"] for s in verified}

    def divergence(field: str) -> list[dict]:
        sets = {s["seat"]: {_norm(x) for x in s["stance"].get(field, [])} for s in verified}
        allitems = set().union(*sets.values()) if sets else set()
        out = []
        for item in sorted(allitems):
            raised = [seat for seat, st in sets.items() if item in st]
            if len(raised) < len(verified):                 # not unanimous → a divergence
                out.append({"item": item, "raised_by": raised,
                            "missed_by": [s["seat"] for s in verified if s["seat"] not in raised]})
        return out

    return {
        "recommendations": recs,
        "recommendation_divergent": len(set(recs.values())) > 1,
        "risk_divergence": divergence("risks"),
        "claim_divergence": divergence("key_claims"),
        "note": ("Mechanical comparison only — items matched as normalized strings; "
                 "differently-worded but equivalent points count as divergent. No model "
                 "interprets the dissent (chair's job, Phase 3)."),
    }


def run_panel(question: str, project_id: str | None = None, max_tokens: int = 4000) -> dict:
    """Run the deep model-reviewer panel over one question. Inspection only."""
    project_id = project_id or f"panel_{uuid.uuid4().hex[:8]}"
    lineage_snapshot = lineage.report_lineage()            # honest depth + panel_lineage.jsonl
    specs = lineage.seats()
    store = wp.ReportStore(base_dir=str(REPORTS_BASE))

    # Run every seat deep, in parallel (run_seat is fail-closed and never raises).
    prompt = _REVIEW_PROMPT.format(question=question)

    async def _go():
        async with asyncio.TaskGroup() as tg:
            tasks = {s.name: tg.create_task(asyncio.to_thread(lineage.run_seat, s, prompt, max_tokens))
                     for s in specs}
        return {n: t.result() for n, t in tasks.items()}

    runs = asyncio.run(_go())

    seats_out, stances = [], []
    for spec in specs:
        r = runs[spec.name]
        entry = {"seat": spec.name, "expected_family": spec.expected_family,
                 "provider": spec.provider, "status": r.status,
                 "actual_model_id": r.actual_model_id, "actual_family": r.actual_family,
                 "reason": r.reason, "report_path": None, "stance": None}
        if r.status == "verified":
            stance = _parse_stance(r.content)
            # PROVENANCE: agent name carries the ACTUAL verified family (no colons — Windows paths)
            report = wp.WarRoomReport(
                agent=f"seat_{r.actual_family}", phase="review", project_id=project_id,
                display_content=r.content, raw_response=r.content,
                recommendation=stance["recommendation"],
                structured_data={
                    "seat": spec.name, "requested_model": r.requested_model,
                    "actual_model_id": r.actual_model_id, "actual_family": r.actual_family,
                    "stance": stance,
                },
            )
            entry["report_path"] = store.save(report)
            entry["stance"] = stance
        seats_out.append(entry)
        stances.append(entry)

    verified = [s for s in seats_out if s["status"] == "verified"]
    families = sorted({s["actual_family"] for s in verified if s["actual_family"]})
    depth = len(verified)
    can_assemble = len(families) >= 2
    disagreements = capture_disagreements(stances) if can_assemble else {}

    session = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": project_id,
        "question": question,
        "depth_label": (f"{depth}-deep ({', '.join(families)})"
                        + ("" if depth == 3 else " — NOT a finished three-seat panel; "
                           "third seat wired-but-not-enabled or unavailable")),
        "protection": lineage_snapshot["protection"],
        "mixed_panel_verdict": "CAN_ASSEMBLE" if can_assemble else "REFUSE",
        "seats": seats_out,
        "disagreements": disagreements,
        "lineage_snapshot": lineage_snapshot,
    }
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    (SESSIONS_DIR / f"{project_id}.json").write_text(json.dumps(session, indent=2), encoding="utf-8")
    return session


def _print(s: dict) -> None:
    print(f"  SESSION {s['session_id']}  protection={s['protection']}  "
          f"depth={s['depth_label']}  verdict={s['mixed_panel_verdict']}")
    for seat in s["seats"]:
        tag = {"verified": "✓", "not-enabled": "·", "unreachable": "✗"}.get(seat["status"], "?")
        prov = f" actual={seat['actual_model_id']}" if seat["actual_model_id"] else ""
        rec = f" rec={seat['stance']['recommendation']}" if seat.get("stance") else ""
        print(f"    [{tag}] {seat['seat']:7} {seat['status']:11}{prov}{rec}  ({seat['reason']})")
    d = s.get("disagreements") or {}
    if d:
        print(f"  RECOMMENDATIONS: {d['recommendations']}  divergent={d['recommendation_divergent']}")
        print(f"  RISK divergences: {len(d['risk_divergence'])}  CLAIM divergences: {len(d['claim_divergence'])}")


if __name__ == "__main__":
    q = (" ".join(sys.argv[1:]) or
         "Should a small team replace its REST API with GraphQL for a CRUD-heavy "
         "internal admin tool? Recommend PROCEED, REVISE, or REJECT.")
    print("=== PANEL RUN (deep seats, two-deep today; inspection only) ===")
    _print(run_panel(q))
