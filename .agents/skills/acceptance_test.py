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


def step_cfo():
    fac = os.path.abspath(os.path.join(ROOT, "..", "..", "Meta_App_Factory"))
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
