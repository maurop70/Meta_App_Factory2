---
name: form-fill
description: Fill an existing PDF or Word/Google Doc form from whatever data the user provides — natural-language text and/or uploaded files (Excel, CSV, PDF, Word, images) — deriving the value each field actually asks for, including counts, sums and cross-tabs computed from the source, and filling the correct fields (including table/matrix grids) while leaving the rest untouched. Use when given a form to complete plus data: onboarding/intake/application forms, statutory/registration filings, headcount & diversity (EEO) reports, contracts with fill-in blanks, purchase orders, vendor setup forms.
---

# form-fill

## Purpose
Fill an **existing** form (PDF / .docx) from any mix of data, **deriving** the value
each field asks for — frequently a value that is *not written anywhere verbatim* and
must be counted, summed, averaged, grouped or cross-tabulated from the source.
Preserves the original document; fills only the agent's designated portion.

## Trigger
A form to complete (PDF with fields/blanks/checkboxes/tables, or .docx) **plus**
data (prose and/or uploaded Excel/CSV/PDF/Word/images). Onboarding, applications,
intake sheets, tax/registration/statutory forms, **headcount & diversity matrices**,
contracts with blanks, purchase orders, vendor setup.

## How it works
1. **Understand the form.** `detect_form()` branches correctly:
   - **PDF AcroForm** — enumerate fields (type, value, options, signature flag).
   - **Flat PDF** — no fields: locate the matrix from the table's real cell
     rectangles and **overlay text at the exact cell centres** (geometry, not guesses).
   - **.docx** — `{{placeholders}}`, "Label: ____" blanks, and **empty table cells**.
   - **Table/matrix groups** captured as one structured target (rows × cols × cells).
2. **Understand the sources** via the reusable **data-context** module (prose +
   Excel/CSV/PDF/Word/images, with provenance and vocabulary normalization).
3. **Derive the value** — direct copy, or a computation over the full dataset
   (count/sum/avg/cross-tab) with the form↔source vocabulary mapped explicitly.
4. **Reconcile before writing** — matrix cells must tie to row/column/grand totals
   and to (records − excluded). If they don't, it **does not fill** — it reports.
5. **Fill, preserving the original** — AcroForm values (+ appearances, editable by
   default), docx cells/placeholders, or flat-PDF overlay; each matrix value into
   the correct row × column cell.
6. **Fill report** — every filled field → value; every derived value → its **formula
   + source columns + reconciliation**; everything left blank (needs input);
   everything left for a human (signatures); and the excluded/unknown row count.

## Hard rules (own trap list — checked, fail loud)
- **Never fabricate.** No supporting data → leave blank and list under "needs input".
- **Compute, don't estimate.** Aggregates derived over the full dataset (pandas).
- **Map categories explicitly; flag ambiguity.** A missing required dimension means
  the value can't be derived — say so; two plausible columns → surface for confirmation.
- **Reconcile, then fill.** Numbers that don't add up are worse than blanks.
- **Never auto-sign;** signature/attestation fields are left for a human.
- **Leave out-of-scope sections untouched** ("office use only", counterparty).

## Mandatory QA loop (non-negotiable)
- **Read back** the saved file (AcroForm fields / docx cells / flat-PDF table) and
  confirm each value — **independently of the placement anchors** so a placement bug
  cannot self-validate. Re-check matrix reconciliation on the saved output.
- **Render pages to images** — PDFs via `pypdfium2` **with form drawing** (so AcroForm
  values are actually visible — pdfplumber's rasterizer ignores NeedAppearances and
  would show blank fields; always verify the *rendered* file).

## Usage
```python
import form_fill as ff
# Derive a matrix cross-tab from an uploaded roster and fill the grid cells:
res = ff.fill_matrix_form("headcount.pdf", ["roster.xlsx"],
                          ["Male", "Female"], ["Production", "Warehouse", "Office"],
                          "headcount_FILLED.pdf")
print(res["report_text"])           # derivations + sources + reconciliation
# Fill direct fields from a paragraph (signature left for a human):
ff.fill_simple_form("onboarding.pdf", paragraph, {"EmployeeName": "name", ...},
                    "onboarding_FILLED.pdf")
```

## Agent binding & reuse
Designed to attach to form-filling agents: hand it (a form + any mix of prose and
uploaded files) and get back (filled file + fill report). Usable standalone; binding
is additive. The source-ingestion + derivation stages (B–F) live in the separate,
reusable **[[data-context]]** module so other agents aggregate uploaded data without
reimplementing it.

## Runtime
Native Python: `pypdf` (AcroForm), `pdfplumber` (flat-PDF tables/anchors),
`python-docx`, `reportlab` (overlay), `pypdfium2` (form-faithful render),
`pandas` (via data-context). Registered at `.agents/skills/form-fill/`.
