# Generated Builds Gallery

Self-contained apps produced by the **Builder Chat Self-Healing Build Pipeline**
(generate → run → observe → fix → verify). Each app is a single, dependency-free
`index.html` that runs entirely in the browser — no backend, no build step.

## How apps land here

1. **Builder Chat** (factory_ui, `localhost:5173`) takes a plain-language request.
2. The Master Architect generates a hardened blueprint JSON
   (`max_output_tokens=32768`, temperature-0.0 retry on `JSONDecodeError`).
3. The `:5050` server actuates the blueprint into `generated_builds/<app-slug>/`.
4. `factory_ui/verify_app.mjs` headlessly renders the app (Playwright, non-local
   egress blocked), capturing console / runtime / network errors + a screenshot.
5. Any failure is fed back to Gemini for **up to 3 repair passes**. `✅ Build
   Complete` is gated on a clean render (verifier failures fail-open so a
   verifier hiccup can't block a build).
6. The app is served over HTTP and surfaced in the **Built Apps** sidebar gallery,
   with an in-chat **Open app** button on completion.

## Apps

| App | Slug | What it does |
|---|---|---|
| **MAF Blueprint Inspector** | `maf-blueprint-inspector` | Paste a blueprint/JSON payload and validate it — structural lint with a pass/fail status banner. Useful for sanity-checking blueprints before actuation. |
| **MAF Token Cost Estimator** | `maf-token-cost-estimator` | Estimate LLM token usage and dollar cost for a prompt/run, supporting MAF's cost-tracking discipline. |
| **MAF UUID Generator** | `maf-uuid-generator` | Generate UUID v4 identifiers on demand. |

> Each app is built and verified end-to-end by the pipeline above. To rebuild or
> add one, drive it from Builder Chat — do not hand-edit generated output, as the
> next build will overwrite it.

## See also

- `AGENTS.md` §3 — Builder Chat Self-Healing Build Pipeline (factory engine docs)
- `MAF_Architecture_Manifest.md` §3 — Execution Lifecycle
- `factory_ui/verify_app.mjs` — the headless verifier
- `Master_Architect_Elite_Logic/server.py` — verify→heal loop + completion gating
