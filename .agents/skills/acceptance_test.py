"""
acceptance_test.py — combined end-to-end acceptance test for the four studio skills
════════════════════════════════════════════════════════════════════════════════════
Runs the whole story on one example (Cold-Brew Coffee Co.):
  1. brand-deck    — extract an EXISTING identity from a logo image -> brand tokens
  2. fin-model     — build a live formula-driven model; recalc gate must report 0 errors
  3. fin-model-presentation — native brand-coloured charts + board PDF (render QA)
  4. brand-deck    — on-brand deck built from the identity + the model's REAL numbers
  5. form-fill     — (A) NL paragraph -> PDF AcroForm; (B) Excel roster -> matrix cross-tab
  6. CFO Agent     — the same request made THROUGH the agent binding (call trace)

Each skill runs in its own interpreter (subprocess) so same-named helper modules
(qa.py, samples.py) across skills never collide. Artifacts land in ./_acceptance.

Run:  python acceptance_test.py            (from .agents/skills)
      python acceptance_test.py <step>     (single step, used internally)
"""

import os
import sys
import json
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
ACC = os.path.join(ROOT, "_acceptance")
PY = sys.executable


def _find_factory_dir():
    """Locate the Meta_App_Factory dir (where cfo_agent.py lives) across layouts:
    skills vendored INSIDE the factory (ROOT/../..) or as a dev sibling
    (ROOT/../../Meta_App_Factory). Env MAF_FACTORY_DIR overrides."""
    candidates = [
        os.environ.get("MAF_FACTORY_DIR"),
        os.path.abspath(os.path.join(ROOT, "..", "..")),
        os.path.abspath(os.path.join(ROOT, "..", "..", "Meta_App_Factory")),
    ]
    for c in candidates:
        if c and os.path.exists(os.path.join(c, "cfo_agent.py")):
            return c
    raise FileNotFoundError(f"Could not locate Meta_App_Factory (cfo_agent.py) from {ROOT}")


def _make_scanned_pdf(out_path):
    """Build a 'scanned' PDF (text rasterized into an image, NO text layer) so the
    OCR live path has something genuine to read. Returns the path or None if the
    imaging deps are unavailable."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
    except Exception:
        return None
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    img = Image.new("RGB", (1100, 320), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 46)
    except Exception:
        font = ImageFont.load_default()
    d.text((40, 60), "VENDOR: Cold Brew Coffee Co", fill="black", font=font)
    d.text((40, 150), "INVOICE TOTAL: 4250 USD", fill="black", font=font)
    png = os.path.splitext(out_path)[0] + "_scan.png"
    img.save(png)
    c = canvas.Canvas(out_path, pagesize=letter)
    c.drawImage(png, 50, 380, width=520, height=150)
    c.save()
    return out_path


# ── individual steps (each runs in a fresh interpreter) ──────────────────────
def step_identity():
    sys.path.insert(0, os.path.join(ROOT, "brand-deck"))
    from samples import make_logo
    from identity import extract_identity
    logo = make_logo(os.path.join(ACC, "coldbrew_logo.png"))
    t = extract_identity({"logo": logo,
        "description": 'Voice: artisanal, calm, confident, premium. Tagline: "Slow-steeped. Seriously good."',
        "motif": {"kind": "dot"}}, out_path=os.path.join(ACC, "brand_tokens.json"))
    print("  identity sampled:", {k: (v[0]['hex'] if isinstance(v, list) else v['hex'])
                                   for k, v in t["palette"].items()})


def step_model_present():
    sys.path.insert(0, os.path.join(ROOT, "fin-model"))
    sys.path.insert(0, os.path.join(ROOT, "fin-model-presentation"))
    from fin_model import build_and_verify, shadow_model
    from fin_model_presentation import present
    A = json.load(open(os.path.join(ROOT, "fin-model", "sample_assumptions.json")))
    model = build_and_verify(A, os.path.join(ACC, "coldbrew_model.xlsx"))
    v = model["verification"]
    print(f"  RECALC: passed={v['passed']} errors={v['formula_error_count']} "
          f"cells={v['cells_evaluated']} sens_tie={round(v['sensitivity_tieout']['value'],4)} "
          f"scen_tie={round(v['scenario_tieout']['value'],4)}")
    assert v["passed"] and v["formula_error_count"] == 0, "fin-model recalc gate failed"
    pres = present(model, brand_tokens=os.path.join(ACC, "brand_tokens.json"),
                   pdf_path=os.path.join(ACC, "coldbrew_board.pdf"), qa=True)
    print(f"  PRESENT: qa_clean={pres['qa']['clean']} charts={pres['charts']}")
    assert pres["qa"]["clean"], "presentation QA failed"
    # LIVE PATH: render the actual .xlsx workbook + its native charts via LibreOffice.
    import qa as fmp_qa
    if fmp_qa._resolve_soffice():
        xq = fmp_qa.qa_xlsx(os.path.join(ACC, "coldbrew_model.xlsx"))
        print(f"  XLSX RENDER (LibreOffice): clean={xq['clean']} pages={xq['page_count']}")
        assert xq["clean"], f"xlsx chart render QA failed: {xq['issues']}"
    else:
        print("  XLSX RENDER (LibreOffice): SKIPPED (LibreOffice not installed)")
    sm = shadow_model(A); rows = sm["rows"]
    json.dump({"gross_margin_pct": sm["gross_margin_pct"] * 100,
               "peak_funding_requirement": round(sm["peak_funding"]),
               "ebitda_inflection_year": sm["ebitda_inflection_year"],
               "cats": [f"Y{r['year']}" for r in rows],
               "revenue": [r["revenue"] for r in rows],
               "ebitda": [r["ebitda"] for r in rows]},
              open(os.path.join(ACC, "fin_summary.json"), "w"))


def step_deck():
    sys.path.insert(0, os.path.join(ROOT, "brand-deck"))
    from deck import build_deck, default_pitch_content
    fin = json.load(open(os.path.join(ACC, "fin_summary.json")))
    tok = json.load(open(os.path.join(ACC, "brand_tokens.json")))
    content = default_pitch_content("Cold-Brew Coffee Co.", tok["voice"]["taglines"][0],
        summary={k: fin[k] for k in ("gross_margin_pct", "peak_funding_requirement", "ebitda_inflection_year")},
        cats=fin["cats"], revenue=fin["revenue"], ebitda=fin["ebitda"])
    out = build_deck(os.path.join(ACC, "brand_tokens.json"), content,
                     os.path.join(ACC, "coldbrew_deck.pdf"))
    print(f"  DECK: qa_clean={out['qa']['clean']} slides={out['qa']['slide_count']} pptx={bool(out.get('pptx_path'))}")
    assert out["qa"]["clean"], "deck QA failed"
    # LIVE PATH: render the actual .pptx deck via LibreOffice and QA the rendered slides.
    import qa as bd_qa
    if bd_qa._resolve_soffice() and out.get("pptx_path"):
        pq = bd_qa.qa_pptx(out["pptx_path"], expect_slides=out["qa"]["slide_count"])
        print(f"  PPTX RENDER (LibreOffice): clean={pq['clean']} slides={pq['slide_count']}")
        assert pq["clean"], f"pptx render QA failed: {pq['issues']}"
    else:
        print("  PPTX RENDER (LibreOffice): SKIPPED (LibreOffice not installed or no .pptx)")


def step_formfill():
    sys.path.insert(0, os.path.join(ROOT, "form-fill"))
    from samples import make_all, ROW_CATS, COL_CATS
    import form_fill as ff
    paths = make_all(os.path.join(ACC, "forms"))
    para = ("Please onboard Jordan Rivera, joining the Warehouse team starting 2026-07-06, "
            "reporting to Dana Pike. Email jordan.rivera@coldbrew.co, salary $58,000.")
    A = ff.fill_simple_form(paths["onboarding_pdf"], para,
        {"EmployeeName": "name", "StartDate": "date", "Department": "department",
         "Email": "email", "Salary": "amount", "Manager": "manager", "Signature": "signature"},
        os.path.join(ACC, "onboarding_FILLED.pdf"))
    print(f"  CASE A (NL->AcroForm): {A['status']} qa_clean={A['report']['qa']['clean']} "
          f"filled={len(A['report']['filled'])} human={len(A['report']['human_action_required'])}")
    B = ff.fill_matrix_form(paths["headcount_flat_pdf"], [paths["roster"]], ROW_CATS, COL_CATS,
                            os.path.join(ACC, "headcount_FILLED.pdf"))
    rec = B["report"]["reconciliation"]["reconciled"]
    print(f"  CASE B (roster->matrix): {B['status']} qa_clean={B['report']['qa']['clean']} "
          f"reconciled={rec} excluded={B['report']['excluded_unknown_rows']}")
    assert A["status"] == "filled" and B["status"] == "filled" and rec, "form-fill failed"

    # LIVE PATH C: scanned PDF (no text layer) -> live Tesseract OCR via data_context.
    sys.path.insert(0, os.path.join(ROOT, "data-context"))
    import data_context as dc
    scanned = _make_scanned_pdf(os.path.join(ACC, "forms", "scanned_invoice.pdf"))
    if scanned and dc._resolve_tesseract():
        ctx = dc.DataContext.from_sources([scanned])
        ocr_txt = " ".join(t["text"] for t in ctx.text_facts)
        print(f"  CASE C (scanned PDF -> OCR): chars={len(ocr_txt)} "
              f"read_vendor={'COLD BREW' in ocr_txt.upper()}")
        assert "COLD" in ocr_txt.upper(), f"OCR failed to read the scanned PDF: {ctx.notes}"
    else:
        print("  CASE C (scanned PDF -> OCR): SKIPPED (Tesseract engine not installed)")

    # LIVE PATH D: Google Docs API write. Dry-run proves the batchUpdate request set
    # is built correctly offline; a live push runs when OAuth creds + a doc_id exist.
    gdoc_id = os.environ.get("GOOGLE_TEST_DOC_ID")
    if gdoc_id and (os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or os.path.exists("credentials.json")):
        g = ff.fill_google_doc(gdoc_id, {"EmployeeName": "Jordan Rivera", "Department": "Warehouse"})
        print(f"  CASE D (Google Docs LIVE): status={g['status']} qa_clean={g['qa']['clean']}")
        assert g["status"] == "filled" and g["qa"]["clean"], "live Google Docs fill failed"
    else:
        g = ff.fill_google_doc("SAMPLE_DOC_ID",
                               {"EmployeeName": "Jordan Rivera", "Department": "Warehouse"}, dry_run=True)
        print(f"  CASE D (Google Docs API, dry-run): status={g['status']} requests={g['n_requests']} "
              "(set GOOGLE_TEST_DOC_ID + OAuth creds for a live push)")
        assert g["status"] == "dry_run" and g["n_requests"] == 2, "Google Docs request build failed"


def step_cfo():
    fac = _find_factory_dir()
    sys.path.insert(0, fac)
    os.chdir(fac)
    from cfo_agent import CFOAgent
    A = json.load(open(os.path.join(ROOT, "fin-model", "sample_assumptions.json")))
    r = CFOAgent().route_and_build(
        "Build me a 5-year model with a sensitivity analysis and tell me how much to raise",
        assumptions=A, brand_tokens=os.path.join(ACC, "brand_tokens.json"),
        project_id="acceptance_boardroom")
    print(f"  CFO BINDING: status={r['status']} trace={[t['step'] for t in r['call_trace']]}")
    print(f"  exec_summary: {r['executive_summary_text']}")
    assert r["status"] == "success" and [t["step"] for t in r["call_trace"]] == \
        ["bind", "fin-model", "fin-model-presentation"], "CFO binding failed"

    # LIVE PATH: assumptions parsed from a natural-language request via the model
    # router (Gemini). Structure is always asserted; when GEMINI_API_KEY is set we
    # also require the model (not the offline fallback) produced them.
    ex = CFOAgent().extract_assumptions(
        "Launch a premium cold brew brand selling 12000 bottles a month at $4 each.")
    src = ex.get("_extracted_by") or ("offline-fallback" if ex.get("_assumptions_estimated") else "unknown")
    print(f"  LIVE ASSUMPTIONS (Gemini): keys={len(ex)} source={src} product={ex.get('product_name')!r}")
    assert isinstance(ex, dict) and ex.get("product_name"), "assumptions extraction returned nothing usable"
    if os.environ.get("GEMINI_API_KEY"):
        assert ex.get("_extracted_by"), "GEMINI_API_KEY set but assumptions came from the offline fallback"


STEPS = [("identity", step_identity), ("model_present", step_model_present),
         ("deck", step_deck), ("formfill", step_formfill), ("cfo", step_cfo)]


def main():
    os.makedirs(ACC, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] != "all":
        dict(STEPS)[sys.argv[1]]()
        return
    print("COMBINED ACCEPTANCE TEST — four studio-grade skills + CFO binding\n")
    for name, _ in STEPS:
        print(f"[{name}]")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        p = subprocess.run([PY, os.path.abspath(__file__), name], cwd=ROOT, env=env)
        if p.returncode != 0:
            print(f"\nFAILED at step '{name}'"); sys.exit(1)
    print("\nALL ACCEPTANCE STEPS PASSED — artifacts in", ACC)


if __name__ == "__main__":
    main()
