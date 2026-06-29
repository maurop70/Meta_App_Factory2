"""
Approval gate (Phase 1 piece 5) — the human approval surface that MINTS the token.
The ONLY caller of executor_gate.mint(): a token is produced ONLY by an explicit
operator approval of one specific plan. Approve / reject / ask-a-question.

HARD RULE — questions never approve (structural, not remembered): there is exactly
ONE mint() call, in the approve branch. The ask branch loops and mints nothing;
reject/blank mint nothing. There is no path from a question to a token.

ask_fn is INERT by construction: text in, text out. Answering a question generates
language only — it cannot run a tool, dispatch a mandate, or write a file. Asking
moves nothing.

PANEL-PHASE NOTE (flagged, not built): the question SHOULD eventually be answered by
a model OTHER than the plan's author — a real second opinion, not the author
reassuring you. Unavailable with CC as sole executor today.
"""
import executor_gate

_APPROVE = {"approve", "approved", "yes", "y", "go", "proceed"}
_REJECT = {"reject", "no", "stop", "halt", "abort", ""}     # blank NEVER approves


def default_ask_fn(question: str, plan_text: str) -> str:
    """INERT: routes the question to a model for a plain-language answer and returns
    that text. No tool, no executor, no file, no dispatch."""
    try:
        import os
        import sys
        maf = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if maf not in sys.path:
            sys.path.insert(0, maf)
        from model_router import route
        ans = route("chat",
                    "Answer this question about the plan in plain language. Do NOT take "
                    f"any action; just explain.\n\nPLAN:\n{plan_text}\n\nQUESTION: {question}")
        return ans or "[no answer available]"
    except Exception as exc:
        return f"[answer unavailable: {exc}]"


def request_approval(plan_text, mandate, tier, workdir, trace_id="",
                     *, ask_fn=default_ask_fn, input_fn=input, echo_fn=print,
                     log_fn=lambda *a: None):
    """Drive the operator decision. Returns a minted Authorization ONLY on an explicit
    'approve'; None on reject/blank. Questions loop without minting."""
    echo_fn(f"\n[PLAN FOR APPROVAL]\n{plan_text}\n")
    log_fn("PLAN_PRESENTED", str(plan_text)[:160])
    while True:
        raw = (input_fn("[APPROVAL] 'approve' / 'reject' / 'ask <question>': ") or "").strip()
        low = raw.lower()
        if low in _APPROVE:
            tok = executor_gate.mint(mandate, tier_ceiling=tier,
                                     trace_id=trace_id, workdir=workdir)
            log_fn("APPROVED", f"token minted tier={tier} workdir={workdir}")
            return tok                                        # the ONLY mint path
        if low in _REJECT:
            log_fn("NOT_APPROVED", repr(raw))
            return None                                       # reject/blank => no token
        if low.startswith("ask"):
            answer = ask_fn(raw[3:].strip(" :?"), plan_text)  # plan UNCHANGED, UNAPPROVED
            echo_fn(f"[ANSWER] {answer}\n(plan still UNAPPROVED — only 'approve' approves)")
            log_fn("QUESTION", "answered — no token, plan unapproved")
            continue                                          # loop; nothing minted
        echo_fn("Unrecognized. Nothing approves except 'approve'.")
