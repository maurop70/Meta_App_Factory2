"""
Executor Gate — capability-based authorization (Phase 1).
---------------------------------------------------------
Default-DENY floor (unchanged from Phase 0): authorize(None, ...) refuses exactly
as the freeze did. Authority is an unforgeable, explicitly-PASSED, single-use,
mandate-bound, tier-capped capability token.

NO-AMBIENT-STATE INVARIANT (the un-rideable property):
  This module stores NO Authorization anywhere. Its only module-level mutable
  state is _consumed (a set of spent nonce STRINGS) and _lock. There is no
  global token, no threading.local, and no getter that returns a live token.
  The only way to obtain a token is to hold the reference mint() returned, or to
  be passed it as an explicit `authorization` argument. A caller not handed the
  token gets the default None -> refused. So a concurrent/unapproved action
  cannot ride a live token: there is nowhere to read it from.
  (Out of scope, as for any in-process Python capability: a deliberate gc/frame
  introspection attack by malicious in-process code. That is a different threat
  than the ambient/autonomous ride-along this defends against.)

mint() is called ONLY by the operator-approval path (Phase 1 piece 5). Until then
nothing mints, so the floor holds. Every check is logged to logs/executor_gate.jsonl.
"""
import hashlib
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_LOG = Path(__file__).parent / "logs" / "executor_gate.jsonl"
FROZEN_REASON = "EXECUTOR REFUSED — no operator authorization (default-deny floor)"

# The ONLY module-level mutable state. Holds spent nonce strings — never tokens.
_consumed: set[str] = set()
_lock = threading.Lock()


def _hash_mandate(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Authorization:
    mandate_hash: str    # sha256 of the exact approved mandate
    tier_ceiling: int    # highest tier the operator approved
    nonce: str           # single-use identity
    trace_id: str = ""
    workdir: str = ""    # executor confined to this directory (piece 5)


def mint(mandate_text: str, tier_ceiling: int, trace_id: str = "",
         workdir: str = "") -> "Authorization":
    """Mint a token bound to ONE mandate. Called ONLY by the operator-approval
    path (approval_gate, piece 5). No other code path mints."""
    return Authorization(_hash_mandate(mandate_text), int(tier_ceiling),
                         os.urandom(16).hex(), trace_id, workdir)


def authorize(authorization, action_tier: int, detail: str = "", door: str = "",
              mandate_text: str | None = None) -> "tuple[bool, str]":
    """Return (ok, reason). Default-DENY: None refuses as the Phase-0 freeze did.
    A token authorizes ONLY when present, well-formed, unspent, within its tier
    ceiling, and (when mandate_text is given) bound to that exact mandate."""
    if authorization is None:
        _audit(door, "refused", "no_authorization", detail)
        return False, FROZEN_REASON
    if not isinstance(authorization, Authorization):
        _audit(door, "refused", "bad_token_type", detail)
        return False, "EXECUTOR REFUSED — malformed authorization"
    with _lock:
        spent = authorization.nonce in _consumed
    if spent:
        _audit(door, "refused", "token_consumed", detail)
        return False, "EXECUTOR REFUSED — authorization already used"
    if int(action_tier) > authorization.tier_ceiling:
        _audit(door, "refused", "tier_exceeds_ceiling",
               f"action_tier={action_tier} ceiling={authorization.tier_ceiling} :: {detail}")
        return False, (f"EXECUTOR REFUSED — action tier {action_tier} exceeds "
                       f"approved ceiling {authorization.tier_ceiling}")
    if mandate_text is not None and _hash_mandate(mandate_text) != authorization.mandate_hash:
        _audit(door, "refused", "mandate_mismatch", detail)
        return False, "EXECUTOR REFUSED — authorization not bound to this mandate"
    _audit(door, "authorized", "ok",
           f"tier={action_tier}/{authorization.tier_ceiling} :: {detail}")
    return True, "authorized"


def consume(authorization) -> None:
    """Spend a token at the END of its mandate session (single-use across sessions;
    reusable across that one session's sub-ops, which is why it is not spent here)."""
    if isinstance(authorization, Authorization):
        with _lock:
            _consumed.add(authorization.nonce)


def _audit(door, action, reason, detail=""):
    try:
        _LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts":     datetime.now(timezone.utc).isoformat(),
                "door":   door,
                "action": action,
                "reason": reason,
                "detail": str(detail)[:300],
            }) + "\n")
    except Exception:
        pass
