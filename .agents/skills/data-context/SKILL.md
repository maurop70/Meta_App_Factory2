---
name: data-context
description: Build one unified, queryable picture of whatever data a user supplies — natural-language prose AND uploaded files (Excel, CSV, PDF, Word, images) — then DERIVE the value a question actually asks for (count / sum / average / min / max with filters and group-bys, cross-tabs, ratios, date math) rather than assuming it is written verbatim. Carries provenance (file → sheet → column/row), normalizes category vocabularies, and reconciles derived matrices. Reusable internal module behind form-fill and any agent that must aggregate uploaded data.
---

# data-context

## Purpose
The reusable ingestion + derivation engine (form-fill stages **B–F**), factored out
so any agent/skill can extract and aggregate from uploaded files without
reimplementing it. It answers questions whose answer is **not written anywhere
verbatim** — it must be *computed* from the source.

## What it does
- **Ingest every source into one picture.** Natural-language prose → text facts with
  source snippets. Excel/CSV → every sheet as a real `pandas` table, with the **true
  header row detected** even when titles/blank rows sit above it; columns, dtypes and
  sample values profiled. PDF/Word → text **and tables** (structure, not a blob).
  Images → OCR when available, else flagged (never guessed).
- **Provenance everywhere** — every datum knows its file → sheet → column/row.
- **Vocabulary normalization** — the form's words rarely match the data's: maps
  categories onto source columns and values (synonyms, codes, casing, trailing
  spaces) — e.g. "female" → `{F, Female, W, woman}`, "Production" → `{Production,
  PROD}`.
- **Derivation** — `derive(op=count/sum/avg/min/max, filters=...)` and the central
  `crosstab(rows, cols)`: a full row×col count computed in ONE pass, each cell
  carrying its expression and the contributing source-row indices.
- **Reconciliation** — `reconcile_matrix()` checks cells sum to row totals, column
  totals and the grand total, and that the grand total equals records − excluded.

## Hard rules
- **Never fabricate.** A missing required dimension (e.g. no department column) →
  reported as unresolved, not invented.
- **Flag ambiguity.** Two plausible columns for one category → surfaced
  (`ambiguous`, `ambiguous_with`) for confirmation, not silently chosen.
- **Report exclusions.** Rows with blank/unknown categories are counted and
  reported (`unknown_excluded`), never silently dropped.

## Usage
```python
from data_context import DataContext, reconcile_matrix
ctx = DataContext.from_sources(["roster.xlsx"]); ctx.add_text("...prose...")
ct = ctx.crosstab(["Male", "Female"], ["Production", "Warehouse", "Office"])
assert reconcile_matrix(ct)["reconciled"]
print(ct["grid"], ct["row_totals"], ct["unknown_excluded"])
single = ctx.derive(op="count", filters={"Sex": "Female", "Dept": "Production"})
```

## Runtime
Native Python: `pandas`, `pdfplumber`, `python-docx`, `openpyxl` (+ optional
`pytesseract` for image OCR). Registered at `.agents/skills/data-context/`.
