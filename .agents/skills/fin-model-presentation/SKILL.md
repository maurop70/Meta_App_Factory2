---
name: fin-model-presentation
description: Make a finished financial model boardroom-ready. Use alongside fin-model, or on requests to "make this model presentable", "add charts", "build a one-pager / board pack / investor pack from the model", "export the model to PDF", or "package the model for the board/CFO". Adds native editable in-workbook charts colored from brand tokens, a README/cover, clean landscape print/PDF setup with print areas that include the charts, and a board PDF that mirrors the spreadsheet's palette and grid.
---

# fin-model-presentation

## Purpose
Turn a **correct** fin-model into something a CFO/board will actually read —
without changing a single formula. It adds presentation on top of the live model:
native charts, an executive cover, brand-consistent styling, and a clean PDF.

## Trigger
Fires alongside `fin-model`, or on: "make this model presentable / add charts /
one-pager / board pack / investor pack / export to PDF / package for the board".

## Inputs
- `build_result` — the dict returned by `fin-model`'s `build_and_verify()`
  (carries `xlsx_path`, `chart_targets`, `summary`, `assumptions`).
- `brand_tokens` — `dict | path-to-json | None`. Reuses the **same brand-token
  format the `brand-deck` skill emits**; `None` → a professional navy default.

## What it adds
- **README / cover tab** (enriched in place): purpose, how-to-use (which cells to
  edit), distribution assumptions, and an honest conservatism note.
- **Native, editable in-workbook charts** (openpyxl, not pasted images), series
  colored from the brand palette:
  revenue-bars + EBITDA-line **combo** · cumulative-FCF line (shows the funding
  trough) · sorted **tornado** bar · **scenario** column chart.
- **Clean print/PDF setup:** landscape, fit-to-width, sensible margins, and
  **print areas extended to include the charts** (charts anchored below the data
  are otherwise silently clipped from exports).
- **Brand-consistent banners + tab colours** so the workbook reads as one document.
- **A board PDF** (reportlab) that visually mirrors the spreadsheet: same palette,
  same colour-coding legend (blue=input / black=formula / green=link), same number
  formats (negatives in parentheses, zeros as dashes), same grid structure —
  cover + P&L + Cash/Break-Even + Sensitivity, with brand-colored vector charts.

## Hard rules (own trap list — checked, fail loud)
- **Charts are native & editable** (openpyxl chart objects), colored from tokens —
  never library defaults, never flattened images.
- **Print areas include the charts** — no silent clipping on export.
- **Font-safety:** the PDF only emits fonts reportlab actually has registered; a
  brand font we can't embed falls back rather than breaking layout measurement.
- **PDF values are the verified values** — recomputed from the same Python shadow
  that fin-model proved equals the live workbook (so the PDF can't drift from the
  model).

## Mandatory QA loop (non-negotiable)
`present(..., qa=True)` renders **every** PDF page to PNG via `pdfplumber`'s native
`page.to_image()` (no Poppler needed on Windows) and inspects each page for: text
overflow past the margins, placeholder/error text, empty pages, and missing
sections. It loops until `qa.clean` is true. Always verify the *rendered* file.

## Usage
```python
from fin_model import build_and_verify
from fin_model_presentation import present

model = build_and_verify(assumptions, "out/model.xlsx")
assert model["verification"]["passed"]
pres = present(model, brand_tokens="brand.json", pdf_path="out/board.pdf")
assert pres["qa"]["clean"]
print(pres["pdf_path"])          # board-ready PDF
```
Standalone, or chained by the CFO Agent after `fin-model` (see `cfo_agent.py`).

## Runtime
Native Python: `openpyxl` (charts/print), `reportlab` (PDF), `pdfplumber` (QA
render). No LibreOffice/Node.js required (manifest §1). Registered at
`.agents/skills/fin-model-presentation/`.
```bash
pip install openpyxl reportlab pdfplumber
```
