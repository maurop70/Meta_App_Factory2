"""
panel/lineage.py — ClaudeAY panel, Phase 1: fail-closed seat-caller + honest
lineage reporting.
═════════════════════════════════════════════════════════════════════════════
WHAT THIS IS. Before any reviewing happens, the panel must know — honestly — how
much INDEPENDENT protection is actually available right now. Three genuinely
different model lineages (Claude / Gemini / a third, OpenAI by default) is the
standard panel. This module verifies each seat is reachable AND is *itself*, then
reports the protection depth in plain consequences.

STRICT SEMANTICS (locked). protection == "FULL" is reported ONLY when all three
lineages are present and each verified as itself. Anything less is "WEAKENED",
with the per-seat reason and a plain-language consequence. Today's honest state is
WEAKENED — two-deep, OpenAI not yet enabled.

FAIL-CLOSED, NO CROSS-FAMILY FALLBACK (the safety-forced deviation from reusing
model_router as-is). Each seat calls exactly ONE provider's own endpoint and is
counted ONLY if the provider echoes back a model id whose family matches the seat's
expected family. Any missing key, transport failure, or identity mismatch ⇒ that
seat does not count. The router's silent Claude→Gemini-style substitution is never
used here: a seat's lineage is taken from WHAT ANSWERED (the echoed model id), never
from what we asked for. A one-lineage ("same-family") panel is REFUSED.

THREE-STATE PER-SEAT TRUTH:
  verified     — reachable and the echoed model id matches the expected family
  not-enabled  — no API key configured for this seat (it is switched off)
  unreachable  — key present but the call failed, returned nothing, or the echoed
                 model id did not verify as the expected family

DETECTION ONLY. Imports nothing from the executor path. Calls read-only LLM
completion endpoints and writes only logs/panel_lineage.jsonl. It cannot mint a
token, dispatch a mandate, or change code.

CREDENTIALS (MAF C2). API keys are NEVER logged. Only model ids, families, and
statuses are recorded. Error reasons carry HTTP status / a short response snippet —
never a request header, never a key.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import requests

BRIDGE_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = BRIDGE_ROOT / "logs" / "panel_lineage.jsonl"

# Standalone runs (this self-check, CLI) need .env loaded; under api.py it's a
# no-op since the environment is already populated. Same pattern as model_router.
try:
    from dotenv import load_dotenv
    load_dotenv(BRIDGE_ROOT / ".env")
    load_dotenv(BRIDGE_ROOT.parent / ".env")
except Exception:
    pass

# A tiny probe — we only need a 200 and the provider's echoed model id, not content.
_PROBE = "Reply with the single word: OK"

# ── Identity: map an echoed model id back to its lineage family ──────────────
# The seat is trusted only if WHAT ANSWERED classifies to the expected family.
_FAMILY_TOKENS = {
    "anthropic": ("claude",),
    "google":    ("gemini",),
    "openai":    ("gpt", "o1", "o3", "o4", "chatgpt"),
}


def _family_of(model_id: str | None) -> str | None:
    s = (model_id or "").lower()
    for fam, toks in _FAMILY_TOKENS.items():
        if any(t in s for t in toks):
            return fam
    return None


# ── Provider callers: each hits ONE provider's own endpoint and returns the
#    model id that provider echoes back. No fallback, ever. (key is used only in
#    the request header — never returned, never logged.) ──────────────────────
# Each caller returns (echoed_model_id, content, error). Phase-1's probe ignores
# content; Phase-2's run_seat uses it. One source of provider logic (no drift).
def _call_anthropic(model: str, key: str, prompt: str, max_tokens: int) -> tuple:
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=120)
    if r.status_code != 200:
        return None, "", f"HTTP {r.status_code}: {r.text[:120]}"
    j = r.json()
    content = "".join(p.get("text", "") for p in j.get("content", []) if isinstance(p, dict))
    return j.get("model"), content, None


def _call_google(model: str, key: str, prompt: str, max_tokens: int) -> tuple:
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key, "content-type": "application/json"},
        json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
              "generationConfig": {"maxOutputTokens": max_tokens}},
        timeout=120)
    if r.status_code != 200:
        return None, "", f"HTTP {r.status_code}: {r.text[:120]}"
    j = r.json()
    cands = j.get("candidates", [])
    content = ""
    if cands:
        parts = cands[0].get("content", {}).get("parts", [])
        content = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    return j.get("modelVersion"), content, None


def _call_openai(model: str, key: str, prompt: str, max_tokens: int) -> tuple:
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "content-type": "application/json"},
        json={"model": model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=120)
    if r.status_code != 200:
        return None, "", f"HTTP {r.status_code}: {r.text[:120]}"
    j = r.json()
    ch = j.get("choices", [])
    content = ch[0].get("message", {}).get("content", "") if ch else ""
    return j.get("model"), content, None


# provider id → (family, caller, key env var)
_PROVIDERS = {
    "anthropic": ("anthropic", _call_anthropic, "ANTHROPIC_API_KEY"),
    "google":    ("google",    _call_google,    "GEMINI_API_KEY"),
    "openai":    ("openai",    _call_openai,    "OPENAI_API_KEY"),
}


@dataclass
class SeatSpec:
    name: str
    provider: str
    expected_family: str
    key_env: str
    model: str


def seats() -> list[SeatSpec]:
    """The standard three-lineage panel. The third seat is provider-configurable
    (PANEL_SEAT3_PROVIDER, default 'openai') so it can be swapped without a rebuild."""
    s3_provider = os.getenv("PANEL_SEAT3_PROVIDER", "openai").strip().lower()
    s3_family, _, s3_keyenv = _PROVIDERS.get(s3_provider, (s3_provider, None, "OPENAI_API_KEY"))
    return [
        SeatSpec("claude", "anthropic", "anthropic", "ANTHROPIC_API_KEY",
                 os.getenv("PANEL_CLAUDE_MODEL", "claude-sonnet-4-6")),
        SeatSpec("gemini", "google", "google", "GEMINI_API_KEY",
                 os.getenv("PANEL_GEMINI_MODEL", "gemini-2.5-pro")),
        SeatSpec("seat3", s3_provider, s3_family, s3_keyenv,
                 os.getenv("PANEL_SEAT3_MODEL", "gpt-4o")),
    ]


@dataclass
class SeatResult:
    name: str
    expected_family: str
    provider: str
    requested_model: str
    status: str                       # verified | not-enabled | unreachable
    actual_model_id: str | None = None
    actual_family: str | None = None
    reason: str = ""
    consequence: str = ""


def _verified_call(spec: SeatSpec, prompt: str, max_tokens: int) -> dict:
    """Shared fail-closed call → dict(status, model_id, family, content, reason).
    No cross-family substitution; identity is taken from the echoed model id."""
    key = (os.getenv(spec.key_env) or "").strip().strip("'\"")
    if not key:
        return dict(status="not-enabled", model_id=None, family=None, content="",
                    reason=f"no {spec.key_env} configured — seat is switched off")
    prov = _PROVIDERS.get(spec.provider)
    if not prov:
        return dict(status="unreachable", model_id=None, family=None, content="",
                    reason=f"unknown provider '{spec.provider}'")
    _, caller, _ = prov
    try:
        echoed, content, err = caller(spec.model, key, prompt, max_tokens)
    except Exception as e:
        echoed, content, err = None, "", f"call error: {type(e).__name__}: {str(e)[:80]}"
    if err or not echoed:
        return dict(status="unreachable", model_id=echoed, family=_family_of(echoed),
                    content="", reason=f"unreachable: {err or 'no model id echoed'}")
    actual = _family_of(echoed)
    if actual != spec.expected_family:        # answered as something it must not be
        return dict(status="unreachable", model_id=echoed, family=actual, content="",
                    reason=(f"identity mismatch — expected {spec.expected_family}, "
                            f"endpoint echoed '{echoed}' ({actual or 'unknown family'})"))
    return dict(status="verified", model_id=echoed, family=actual, content=content,
                reason=f"verified as {echoed}")


def call_seat(spec: SeatSpec) -> SeatResult:
    """Phase-1 lineage probe: verify one seat is reachable and is itself (fail-closed)."""
    v = _verified_call(spec, _PROBE, max_tokens=8)
    if v["status"] == "verified":
        consequence = ""
    elif v["status"] == "not-enabled":
        consequence = f"No independent {spec.expected_family} check is available."
    elif "identity mismatch" in v["reason"]:
        consequence = "Refusing to count this seat — it did not verify as itself."
    else:
        consequence = f"No independent {spec.expected_family} check this run."
    return SeatResult(name=spec.name, expected_family=spec.expected_family,
                      provider=spec.provider, requested_model=spec.model,
                      status=v["status"], actual_model_id=v["model_id"],
                      actual_family=v["family"], reason=v["reason"], consequence=consequence)


@dataclass
class SeatRun:
    """A seat's full analysis run (Phase 2). Carries provenance: the ACTUAL verified
    family from the echoed model id, never the requested one."""
    name: str
    expected_family: str
    provider: str
    requested_model: str
    status: str                       # verified | not-enabled | unreachable
    actual_model_id: str | None = None
    actual_family: str | None = None
    content: str = ""
    reason: str = ""


def run_seat(spec: SeatSpec, prompt: str, max_tokens: int = 1500) -> SeatRun:
    """Run a full prompt on one seat through the fail-closed path. Same no-substitution
    guarantee as the probe: content is counted ONLY if the provider echoed a model id
    that verifies as the expected family."""
    v = _verified_call(spec, prompt, max_tokens=max_tokens)
    return SeatRun(name=spec.name, expected_family=spec.expected_family,
                   provider=spec.provider, requested_model=spec.model,
                   status=v["status"], actual_model_id=v["model_id"],
                   actual_family=v["family"], content=v["content"], reason=v["reason"])


def _missing_text(results: list[SeatResult]) -> str:
    miss = [f"{r.name} ({r.expected_family}) — {r.status}" for r in results
            if r.status != "verified"]
    return ("Not verified: " + "; ".join(miss) + ".") if miss else ""


def report_lineage(write_log: bool = True) -> dict:
    """Run all seats and produce the honest protection report. STRICT: FULL only
    at three verified distinct families. A one-lineage panel is REFUSED."""
    results = [call_seat(s) for s in seats()]
    verified = [r for r in results if r.status == "verified"]
    families = sorted({r.actual_family for r in verified if r.actual_family})
    depth = len(verified)
    distinct = len(families)

    full = (depth == 3 and distinct == 3)
    protection = "FULL" if full else "WEAKENED"
    can_assemble = distinct >= 2          # a mixed panel needs ≥2 distinct lineages
    verdict = "CAN_ASSEMBLE" if can_assemble else "REFUSE"

    if full:
        consequence = "All three independent lineages are present and verified as themselves."
    elif distinct >= 2:
        consequence = (f"Running {depth}-deep ({', '.join(families)}). Fewer than three "
                       f"independent lineages — a blind spot shared by the present families "
                       f"can pass unseen. " + _missing_text(results))
    elif distinct == 1:
        consequence = (f"Only one model lineage is available ({families[0]}) — there is NO "
                       f"independent cross-check. This is not a mixed panel; a same-family "
                       f"panel is REFUSED. " + _missing_text(results))
    else:
        consequence = ("No model lineage verified — no panel can be assembled. "
                       + _missing_text(results))

    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "protection": protection,
        "depth": depth,
        "distinct_families": families,
        "mixed_panel_verdict": verdict,
        "consequence": consequence,
        "seats": [asdict(r) for r in results],
    }
    if write_log:
        _audit(report)
    return report


def _audit(report: dict) -> None:
    """Append the report to the audit log. No credentials are present in `report`."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(report) + "\n")
    except Exception:
        pass


# ── Self-check: prove both transitions from a real run ──────────────────────
def _print(report: dict) -> None:
    print(f"  PROTECTION: {report['protection']}  | depth={report['depth']}-deep "
          f"| families={report['distinct_families']} | mixed-panel: {report['mixed_panel_verdict']}")
    print(f"  CONSEQUENCE: {report['consequence']}")
    for s in report["seats"]:
        tag = {"verified": "✓", "not-enabled": "·", "unreachable": "✗"}.get(s["status"], "?")
        echoed = f" echoed='{s['actual_model_id']}'" if s.get("actual_model_id") else ""
        print(f"    [{tag}] {s['name']:7} {s['status']:11}{echoed}  — {s['reason']}")


if __name__ == "__main__":
    pull = sys.argv[1] if len(sys.argv) > 1 else "ANTHROPIC_API_KEY"

    print("=== TRANSITION 1: current environment (both present, OpenAI not enabled) ===")
    _print(report_lineage())

    saved = os.environ.pop(pull, None)
    print(f"\n=== TRANSITION 2: {pull} pulled (process-scoped — .env untouched) ===")
    _print(report_lineage())
    if saved is not None:
        os.environ[pull] = saved
