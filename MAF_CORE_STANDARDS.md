# PART I — MAF CORE STANDARDS

C1 — Protections are enforced server-side. Any capability that suspends, relaxes, or overrides a safety control, limit, persona constraint, or other protection must be authorized on the backend from authenticated server-side state. A client-asserted flag (a boolean in the request, a header the client sets itself) may never gate a protected action.

C2 — Credentials are never persisted or logged. Tokens, PINs, session secrets and the like must be stripped before any request reaches conversation history, logs, progress records, or analytics. The stripping must be covered by a test.

C3 — Secure-by-default, explicit opt-in for risk. Anything touching auth, network trust, or input handling defaults to the safe behavior. The riskier behavior (e.g. trusting a proxy's forwarding header) is enabled only by an explicit, documented flag.

C4 — Deployment invariants are declared and centralized. If code is only correct under a runtime/deploy condition (worker count, network mode, env flag, …), that condition must be registered in the single canonical DEPLOYMENT REQUIREMENTS list (Part III) — not left in a code comment. Silent violation of an invariant that degrades a safety control is a defect, not a footnote.

C5 — Verify before acting; report deviations. Never assume a plan was implemented as written or that the environment matches expectation. Inspect the actual code/config first. Any deviation (a substitution, a workaround, an environment finding) is surfaced with its reasoning.

C6 — Failure-path tests are part of "done." A feature is not complete until its failure and abuse paths are tested — denied permissions, expired/invalid tokens, error branches, rate-limit trips, injection attempts — not only the happy path.

C7 — Unauthenticated or unmetered model paths must be contained. Any endpoint that reaches the model without auth, or without counting against normal limits, must be isolated (its own fixed system prompt), rate-limited per source, resistant to persona/prompt-injection coercion, and barred from writing user history — proven by tests that include an actual injection attempt.

---

# PART III — DEPLOYMENT REQUIREMENTS (canonical, append-only)

> Per C4, runtime/deploy conditions that code correctness depends on are registered here. Project-local instances also appear in that project's CLAUDE.md; this is the shared reference.

D1 — Single-worker in-memory state. Where a service keeps security-relevant state in process memory (e.g. the parent-session token registry AND the cast anti-spoofing cache — the rolling deque of finished assistant replies), the stream/API server must run single-worker (uvicorn, no workers= / no --reload). Multi-worker silently breaks such guards (parent auth fails intermittently; unvalidated text can be cast to the speaker). If multi-worker is ever required, move to a signed stateless token AND a shared cast cache (or a shared store) first. (Amended 2026-06-27 to include the cast anti-spoofing cache.)

D2 — Sanctioned-build sessions require a registered Selection verifier. The sanctioned-build choke (`shared_modules/build_guard.py`) opens a build session only when a human-select verifier is registered (`build_guard.set_selection_verifier`) AND it confirms a positive, plan-bound Selection for the session's roots. If no verifier is registered, session entry REFUSES (fail-closed): an unarmed lock means builds do not proceed, never that they run unguarded. Consequence: any build path (`factory.create_app` via `/api/build/direct`, `forge_orchestrator.merge_to_live`, and any future caller) must load the panel `selection` module (which registers the verifier) before scaffolding. The server that boots the factory registers it at startup — the arm is a runtime fact to be watched live after boot (a registration line present in source ≠ a verifier live in the path), not merely present. Registered 2026-07-01 with panel seam 2; the ClaudeAY api.py boot arm lives in its `lifespan` startup.
