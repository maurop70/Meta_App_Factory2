"""
panel/gate.py — ClaudeAY panel, Phase 4: the authorize-and-mint gate.
═════════════════════════════════════════════════════════════════════════════
The SECOND human gate. The FIRST is the chair ratification (chair.py: is this
synthesis faithful?). This one answers a different question: do I authorize the
builder to actually run this now? Collapsing them would let "good plan" silently
become "go build" — so they are kept separate (two gates).

On explicit human authorization, mint the capability token whose scope is EXACTLY
the chair's declared scope:
  • workdir  = the chair's declared subtrees, resolved to absolute paths (multi-subtree)
  • ceiling  = min(chair-declared, classifier-assessed) — an INDEPENDENT cross-check
               caps the chair's self-declared risk; the chair can never grant more than
               the work warrants. A mismatch (classifier reads higher) is SURFACED so an
               under-scoped plan doesn't become a silent stall.

shown-scope == minted-scope BY CONSTRUCTION: the gate shows the resolved workdir + the
cross-checked ceiling, and mints exactly those. Nothing is inferred after approval.

No autonomous mint: mint happens ONLY when human_authorized is True. Enforcement-path
file (originates the mint) → guarded by the /panel/ rule. No executor reach here — this
produces a token; dispatch is the loop's job.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

BRIDGE_ROOT = Path(__file__).resolve().parent.parent
MAF_ROOT = BRIDGE_ROOT.parent
PANEL_DIR = Path(__file__).resolve().parent
for _p in (str(PANEL_DIR), str(BRIDGE_ROOT), str(MAF_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import executor_gate
import chair as _chair                       # shared ratification_hash (one source)
from mandate_tiers import classify_tier


def _resolve_subtrees(workdir_list) -> list:
    """Resolve the chair's declared (possibly relative) subtrees to absolute paths
    under the repo, for the hook's realpath/commonpath confinement."""
    out = []
    for w in workdir_list or []:
        p = Path(w)
        if not p.is_absolute():
            p = MAF_ROOT / w
        out.append(str(p.resolve()))
    return out


def cross_check_ceiling(plan_text: str, chair_tier) -> dict:
    """Independent classifier assessment of the plan; minted ceiling = the LOWER of
    (chair-declared, classifier-assessed). Surfaces any mismatch."""
    assessed = classify_tier(plan_text or "").tier
    if chair_tier is None:
        return {"chair_declared": None, "classifier_assessed": assessed,
                "minted_ceiling": assessed, "mismatch": True,
                "note": "chair declared no ceiling — using the classifier's assessment."}
    minted = min(int(chair_tier), int(assessed))
    note = None
    if assessed > chair_tier:
        note = (f"classifier reads tier {assessed} > chair-declared {chair_tier}: plan may be "
                f"UNDER-scoped. Minted ceiling capped at {minted} (the lower) — riskier steps "
                f"will re-escalate at the drift gate rather than silently stall.")
    elif assessed < chair_tier:
        note = (f"classifier reads tier {assessed} < chair-declared {chair_tier}: chair "
                f"over-declared. Minted ceiling capped at {minted} (the lower).")
    return {"chair_declared": int(chair_tier), "classifier_assessed": assessed,
            "minted_ceiling": minted, "mismatch": assessed != chair_tier, "note": note}


def authorize_and_mint(chairplan: dict, human_authorized: bool, trace_id: str = "panel") -> dict:
    """SECOND gate. Mints ONLY on explicit human authorization. Returns a record with the
    token (or None) and the shown-vs-minted scope so equality is checkable."""
    scope = chairplan.get("scope") or {}
    declared = scope.get("declared") or {}
    shown_workdir = declared.get("workdir") or []
    chair_tier = declared.get("tier_ceiling")
    cc = cross_check_ceiling(chairplan.get("plan") or "", chair_tier)

    # Integrity of the ratified synthesis is checked FIRST (before scope/human), so an
    # altered plan or an unfaithful ledger is the surfaced reason, not a later check.
    # Gate-binding (criterion 2): the minted plan must be the EXACT plan that was ratified.
    if chairplan.get("status") != "ratified" or not chairplan.get("ratification_hash"):
        return {"minted": False, "reason": "not ratified — the ratify gate must precede the mint",
                "ceiling_check": cc, "token": None}
    if _chair.ratification_hash(chairplan) != chairplan["ratification_hash"]:
        return {"minted": False,
                "reason": "plan altered after ratification — mint REFUSED (no gap between approved and enforced)",
                "ceiling_check": cc, "token": None}
    # Reconciliation hard-gate (criterion 3): an unfaithful (omitting) dissent ledger
    # cannot mint — checked before scope so the omission itself is the surfaced reason.
    recon = chairplan.get("reconciliation") or {}
    if not recon.get("ok"):
        return {"minted": False,
                "reason": (f"dissent ledger did not reconcile (verdict={recon.get('verdict')}, "
                           f"missing={recon.get('missing')}) — mint REFUSED"),
                "ceiling_check": cc, "token": None}
    if not scope.get("well_formed"):
        return {"minted": False, "reason": "scope not well-formed (missing where/ceiling) — refused",
                "ceiling_check": cc, "token": None}
    if not human_authorized:
        return {"minted": False,
                "reason": "no human authorization at the mint gate — refused (no autonomous mint)",
                "ceiling_check": cc, "token": None}

    resolved = _resolve_subtrees(shown_workdir)
    plan_id = (f"{trace_id}|{chairplan.get('session_id')}|"
               f"{hashlib.sha256((chairplan.get('plan') or '').encode('utf-8')).hexdigest()[:16]}")
    token = executor_gate.mint(plan_id, tier_ceiling=cc["minted_ceiling"],
                               trace_id=trace_id, workdir=json.dumps(resolved))
    minted_workdir = json.loads(token.workdir)
    return {
        "minted": True, "reason": "minted on human authorization",
        "ceiling_check": cc, "token": token, "plan_id": plan_id,
        "shown_scope": {"workdir": resolved, "tier_ceiling": cc["minted_ceiling"]},
        "minted_scope": {"workdir": minted_workdir, "tier_ceiling": token.tier_ceiling},
        "scope_match": (minted_workdir == resolved and token.tier_ceiling == cc["minted_ceiling"]),
    }
