"""
panel/selection.py — ClaudeAY panel, Phase 5b seam 2: propose ≠ select.
═════════════════════════════════════════════════════════════════════════════
A plan the panel/chair produces is a PROPOSAL. It must not become the SELECTED build
by being the default (the fold), nor by being left sitting until it ages into selected
(the silence path). A Selection is a POSITIVE, plan-bound, single-use artifact minted
ONLY by an explicit human-select event (`select`). It is structurally separate from the
proposal — a proposal dict may carry any `selected`/`default`/`human_authorized` flag it
likes and NONE of it mints a Selection; only calling `select` (the human act) does.

  • the FOLD is refused because session entry consults the Selection store, never a flag
    on the proposal — a default dressed as chosen has no Selection.
  • the SILENCE path is refused by ABSENCE, not expiry: silence calls nothing, so no
    Selection is ever minted. There is no time window to tune, so no long-window
    silent-acceptance hole. A Selection is single-use (consumed at session entry) — that
    guards replay, not silence; silence has nothing to expire.

(Named `selection`, not `select`, on purpose: a top-level module named `select` would
shadow Python's stdlib `select` on the panel sys.path.)

This module registers itself as the sanctioned-build choke's Selection verifier on import
(build_guard.set_selection_verifier) — loading the panel ARMS the choke. Per the C4
invariant (build_guard docstring + DEPLOYMENT REQUIREMENTS D2): if this verifier is never
registered, session entry fails CLOSED (an unarmed lock means builds do not proceed, not
that they run unguarded).

INSPECTION/AUTHORIZATION artifact only — mints no token, reaches no executor. Seam 1
(sticky-taint) rides the same event: `select` refuses to mint for a tainted plan unless a
human, shown the taint, clears it.
"""
from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BRIDGE_ROOT = Path(__file__).resolve().parent.parent
MAF_ROOT = BRIDGE_ROOT.parent
for _p in (str(MAF_ROOT), str(BRIDGE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared_modules import build_guard as _bg   # the choke this arms; share its resolver


class SelectionRefused(Exception):
    """select() refused to mint — e.g. a tainted plan the human has not cleared. No
    Selection exists afterward (fail-closed: propose ≠ select ≠ authorized)."""


@dataclass
class Selection:
    """Positive, plan-bound, single-use proof that a human selected THIS plan for THESE
    roots. Only select() mints one; a proposal can never forge it."""
    selection_id: str
    plan_id: str
    roots: tuple
    selected_at: str
    consumed: bool = False


# A proposal is NOT a selection. It sits here (or nowhere) doing nothing until a human
# selects it. Left sitting forever, it never becomes a Selection.
_proposals: dict = {}
_selections: dict = {}


def propose(plan_id: str, roots, plan_text: str = "") -> dict:
    """Record a PROPOSAL. This authorizes nothing. Silence after this mints no Selection."""
    pid = uuid.uuid4().hex[:12]
    prop = {"proposal_id": pid, "plan_id": str(plan_id),
            "roots": tuple(_bg._resolved(r) for r in roots),
            "plan_text": plan_text, "selected": False}
    _proposals[pid] = prop
    return prop


def select(proposal: dict, *, taint_cleared: bool = False, tainted: bool = False) -> Selection:
    """THE positive human-select event — the ONLY minter of a Selection. A tainted plan
    requires the human, having been SHOWN the taint, to clear it (seam 1, same event)."""
    if tainted and not taint_cleared:
        raise SelectionRefused(
            "plan carries UNTRUSTED provenance not cleared by a human — no Selection minted")
    sel = Selection(
        selection_id=uuid.uuid4().hex[:12],
        plan_id=str(proposal["plan_id"]),
        roots=tuple(proposal["roots"]),
        selected_at=datetime.now(timezone.utc).isoformat(),
    )
    _selections[sel.selection_id] = sel
    return sel


def plan_id_selected(plan_id: str) -> bool:
    """True iff an UNCONSUMED Selection is bound to this plan identity (the gate's binding
    check — 'is this exact plan the one a human selected?'). Does not consume."""
    return any((not s.consumed) and s.plan_id == str(plan_id) for s in _selections.values())


def verify_and_consume(requested_roots) -> bool:
    """The sanctioned-build choke's verifier seam calls this at session entry. True iff an
    UNCONSUMED Selection covers EVERY requested root; consumes it (single-use). No matching
    Selection → False. Silence/absence → False by construction (the store is empty)."""
    req = [_bg._resolved(r) for r in (requested_roots or [])]
    if not req:
        return False
    for sel in _selections.values():
        if sel.consumed:
            continue
        if all(any(_bg._under(r, sr) for sr in sel.roots) for r in req):
            sel.consumed = True
            return True
    return False


def _reset_for_test() -> None:
    """Test-only: clear the proposal/selection stores between proof scenarios."""
    _proposals.clear()
    _selections.clear()


# Loading the panel ARMS the choke (C4 / D2). Without this registration the choke fails
# closed on every sanctioned_session entry.
_bg.set_selection_verifier(verify_and_consume)
