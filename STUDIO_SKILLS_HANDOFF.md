# Studio-Grade Skills — Handoff (continue on another PC)

**Branch:** `feat/studio-grade-skills`  ·  **Repo:** `github.com/maurop70/Meta_App_Factory2`
**Commit:** `3a7dd85` — "feat: studio-grade deliverable skills + CFO Agent binding"

This branch adds five native-Python skills and wires the two financial ones into the
CFO Agent. Phases 1–4 are built **and verified**; Phase 5 (brand-deck) is built and its
deck renders QA-clean; Phase 6 (combined acceptance test) is the remaining work.

---

## 1. Get the code on the other PC
```bash
git clone https://github.com/maurop70/Meta_App_Factory2.git
cd Meta_App_Factory2
git checkout feat/studio-grade-skills
```
The skills are **vendored in-repo** at `.agents/skills/` so they travel with the clone.
The CFO binding resolves the skills root automatically across layouts
(dev sibling `../.agents/skills`, vendored `./.agents/skills`, or env `MAF_SKILLS_ROOT`).

## 2. Python environment
Python 3.12. Create a venv and install the deliverable-skill deps (in addition to the
repo's existing `requirements.txt`):
```bash
python -m venv venv
venv\Scripts\pip install openpyxl formulas reportlab pdfplumber pypdfium2 \
    python-pptx python-docx pandas pillow numpy pypdf fastapi uvicorn httpx \
    pytesseract google-api-python-client google-auth-oauthlib
```
> Core deck/model rendering is still pure-Python (`pypdfium2`/`pdfplumber`; Excel
> recalc via the `formulas` engine). The **live upgrades** add optional system tools:
> - **Tesseract OCR** — scanned-PDF/image OCR. Windows: `winget install UB-Mannheim.TesseractOCR`
>   (binary at `C:\Program Files\Tesseract-OCR\tesseract.exe`); Linux: `apt install tesseract-ocr`.
>   The code auto-discovers it (PATH / common locations / `TESSERACT_CMD` env); no manual PATH edit needed.
> - **LibreOffice** — live `.pptx`/`.xlsx` render-QA via headless conversion to PDF.
>   Linux droplet: `apt install libreoffice`; Windows: `winget install TheDocumentFoundation.LibreOffice`
>   (needs an admin/UAC approval). Auto-discovered (PATH / common locations / `LIBREOFFICE_PATH`).
>   When absent, the office-render QA steps cleanly **SKIP** (the PDF QA still gates).
> - **Google Docs API** (Task 2) — needs an OAuth *Desktop* client secret; point
>   `GOOGLE_OAUTH_CLIENT_SECRET` at it (token cached to `GOOGLE_OAUTH_TOKEN`/`token.json`).
> - **Gemini** (Task 3) — `extract_assumptions` routes through the model router's
>   `assumptions_extraction` task → Gemini Pro; needs `GEMINI_API_KEY` in `.env`
>   (falls back to a clearly-labelled offline default if every model is unavailable).

## 3. What's where
```
.agents/skills/
  fin-model/                 # live formula-driven Excel + zero-error recalc gate
    fin_model.py  verify.py  SKILL.md  sample_assumptions.json
  fin-model-presentation/    # native brand-colored charts + board PDF + render QA
    fin_model_presentation.py  charts_pdf.py  brand_tokens.py  qa.py  SKILL.md
  form-fill/                 # fill PDF/docx forms, derive cross-tabs, never fabricate
    form_fill.py  samples.py  SKILL.md
  data-context/              # reusable ingest + derive + reconcile engine (B–F)
    data_context.py  SKILL.md
  brand-deck/                # extract existing identity -> on-brand deck + QA loop
    identity.py  deck.py  qa.py  samples.py  SKILL.md
Meta_App_Factory/
  cfo_agent.py               # + build_financial_model / extract_assumptions / route_and_build
  cfo_financial_skills.py    # NEW — the binding (intent detect, chain, call trace)
  CFO_Agent/server.py        # + POST /api/build_model (port 5070)
```

## 4. Verify each piece quickly
```bash
cd .agents/skills/fin-model
../../../Meta_App_Factory/venv/Scripts/python -c "import json,fin_model; \
  r=fin_model.build_and_verify(json.load(open('sample_assumptions.json')),'out/m.xlsx'); \
  print('verified:', r['verification']['passed'], 'errors:', r['verification']['formula_error_count'])"
```
- **fin-model:** `build_and_verify()` → `verification.passed == True`, 0 formula errors,
  sensitivity/scenario tie-outs ≈ 0. Demo headline: EBITDA inflection Year 2,
  peak funding $494,667, scenario range $261K–$1.36M.
- **fin-model-presentation:** `present(build_result, brand_tokens=None, pdf_path=...)`
  → `qa.clean == True`; pass a brand JSON to recolor charts + PDF.
- **form-fill:** `fill_matrix_form(form, [roster.xlsx], rows, cols, out)` and
  `fill_simple_form(...)`; `samples.make_all()` generates fixtures.
- **brand-deck:** `identity.extract_identity({...})` → tokens JSON; `deck.build_deck(tokens, content, out.pdf)`.

## 5. CFO Agent binding test (the required proof)
In-process:
```python
# cwd = Meta_App_Factory, venv active
import json
from cfo_agent import CFOAgent
A = json.load(open("../.agents/skills/fin-model/sample_assumptions.json"))
r = CFOAgent().route_and_build(
    "Build me a 5-year model with a sensitivity analysis and tell me how much to raise",
    assumptions=A, project_id="boardroom_demo")
print(r["status"], r["executive_summary_text"])
print([t["step"] for t in r["call_trace"]])   # ['bind','fin-model','fin-model-presentation']
```
Over HTTP (service on 5070):
```bash
venv\Scripts\python -m uvicorn CFO_Agent.server:app --host 127.0.0.1 --port 5070
# then POST /api/build_model  {"instruction": "...", "assumptions": {...}}
```
`route_and_build` returns `bound_skill_paths` pointing at `.agents/skills/...` — proof it
reached the skills through the binding, not a hardcoded shortcut.

## 6. Status — live upgrades complete
The four "graceful fallbacks" were upgraded to full live implementations and the
combined `acceptance_test.py` passes **6/6, 0 errors** (run from `.agents/skills`):
1. **OCR** — `data_context.py` rasterizes scanned PDFs (pypdfium2) + runs Tesseract;
   verified reading a text-free scanned PDF (acceptance CASE C).
2. **Google Docs API** — `form_fill.fill_google_doc()` (OAuth installed-app flow,
   fetch, `batchUpdate` replaceAllText, read-back QA) + offline `dry_run` (CASE D).
3. **Gemini assumptions** — `cfo_agent.extract_assumptions` → model-router
   `assumptions_extraction` (Gemini Pro); verified live (18 keys extracted).
4. **LibreOffice render-QA** — `qa.qa_xlsx` / `qa.qa_pptx` convert the workbook/deck
   to PDF headless and raster for visual QA; SKIP cleanly when LibreOffice is absent.
   Runs on the droplet after `apt install libreoffice`.

Also fixed: `step_cfo` factory-dir resolution now works in the vendored layout
(was hardcoded to the dev-sibling layout).

### Earlier remaining work (now also done)
- **Phase 5 finish:** run the one-call wrapper `deck.build_deck(tokens, content, "out/deck.pdf")`
  end-to-end (its sub-steps already pass; the deck rendered QA-clean across 7 slides).
- **Phase 6 — combined acceptance test:** one example end-to-end:
  (a) on-brand deck, (b) live model w/ sensitivity (recalc error report = 0),
  (c) model presented w/ charts + clean PDF, (d) form-fill on TWO cases
  (NL paragraph → AcroForm, and matrix cross-tab from an uploaded Excel roster),
  plus the CFO Agent binding trace. Show rendered images, the zero-error recalc report,
  and the fill report (each derived value's formula, source columns, reconciliation).

## 7. Deploy to DigitalOcean
> Not run from the dev box (no `doctl`/droplet creds here). The CFO service is a FastAPI
> app on port 5070 (not part of the ERP `docker-compose.yml`). Deploy = get this branch
> onto the host and restart the CFO service.

**Droplet (SSH) path — typical:**
```bash
ssh <user>@<droplet-ip>
cd /path/to/Meta_App_Factory2
git fetch origin && git checkout feat/studio-grade-skills && git pull
# install the new deps into the service venv:
venv/bin/pip install openpyxl formulas reportlab pdfplumber pypdfium2 \
    python-pptx python-docx pandas pillow numpy pypdf
# restart the CFO service (adapt to your process manager):
systemctl restart cfo-agent        # or: pm2 restart cfo  /  supervisorctl restart cfo
curl -s http://127.0.0.1:5070/api/health
```
**App Platform path:** point the component at branch `feat/studio-grade-skills` (or merge
to `main` first), add the deps above to the build, redeploy.

**Merge to main when ready:**
```bash
git checkout main && git merge --no-ff feat/studio-grade-skills && git push origin main
```

## 8. Notes / decisions made
- Committed **only** the new work; the repo's pre-existing uncommitted changes
  (`cmo_agent.py`, `model_router.py`, `factory_ui/*`, ERP work orders, …) were left untouched.
- Skills vendored into the repo for portability; the original dev copies at
  `C:\dev\Antigravity_AI_Agents\.agents\skills` remain and are still what this PC uses.
- Generated artifacts (`out/`, `*_pages/`, caches) are git-ignored.
