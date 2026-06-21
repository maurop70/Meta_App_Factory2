---
name: brand-deck
description: Create a presentation, pitch deck, brochure, one-pager or sell sheet that conforms to an ALREADY-EXISTING visual identity — when a brand, style guide, logo, palette, product packaging, prior deck or example artifact is provided or referenced. This skill owns the case where there is an existing identity to honor (extract it and enforce it), so the output looks like it came from inside that company rather than a generic template.
---

# brand-deck

## Purpose
Generic deck tools pick their own colours and fonts and look templated. When a brand
**already exists**, the output must look like it came **from inside that company**.
This skill *extracts* the identity and then *enforces* it across every page.

## Trigger
Any request to create a deck / pitch / brochure / one-pager / sell sheet **where a
brand, style guide, logo, palette, packaging, website, prior deck or example artifact
is provided or referenced.** The presence of an existing identity to honor is the
differentiator — this skill owns it.

## Workflow
**A. Identity extraction (always first).** `extract_identity()` ingests whatever
exists — logo/packaging image (colours **sampled**, not guessed), explicit palette,
or a verbal description — and emits a **brand-token JSON** the rest of the skill
consumes (never hardcoded inline). It captures:
- `palette`: primary, secondary, 2–4 accents, ink, paper — each with a **role**
  (a light background is NOT the primary even if it covers the most area).
- `type`: heading & body families **with safe fallbacks**.
- `voice`: adjectives + verbatim taglines (so copy matches tone).
- `motif`: the one repeatable mark. This is the SAME token format the
  `fin-model-presentation` skill consumes — reuse one identity across deliverables.

**B. Design system, then slides.** Grid, spacing scale and token mapping are set once
and applied to every slide.

**C. Generate with a library.** Builds the deck programmatically (reportlab PDF —
the render-QA'd artifact — plus an editable `python-pptx` companion), geometry driven
from the spacing scale, not hand-placed magic numbers.

## Hard design rules (the difference between "fine" and "studio")
- **One dominant colour does 60–70% of the work** (full-bleed cover/dividers/closing +
  content header zones); accents are <10%, emphasis only.
- **Repeat the motif** in the same position on every page — repetition reads as identity.
- **NO decorative accent bars / underlines / edge stripes** as a crutch — structure
  comes from type hierarchy, whitespace and the motif.
- **Serious type hierarchy** (big heading→body jump, generous leading, ≤ 2 families).
- **Whitespace is intentional**, not leftover.
- **Real data only** — charts inherit brand tokens and numbers come from the session
  (e.g. the live fin-model); illustrative figures are labelled as such.

## Mandatory QA loop (non-negotiable)
`qa_deck()` renders **every** page to PNG (pypdfium2, no Poppler) and inspects each for
text overflow/collision past the margins, placeholder text, empty pages, and missing
slides — looping until clean. Includes a placeholder grep and **font-safety** (the PDF
only emits registered fonts; the brand font falls back rather than breaking layout
measurement). Always verify the *rendered* file.

## Usage
```python
from identity import extract_identity
from deck import build_deck, default_pitch_content

tokens = extract_identity({"logo": "logo.png", "description": '... "tagline" ...'},
                          out_path="brand_tokens.json")
content = default_pitch_content("Acme", tokens["voice"]["taglines"][0],
                                summary=fin_summary, cats=cats, revenue=rev, ebitda=eb)
out = build_deck("brand_tokens.json", content, "deck.pdf")   # + .pptx + QA
assert out["qa"]["clean"]
```

## Runtime
Native Python: `reportlab` (PDF), `python-pptx` (editable deck), `Pillow` (colour
sampling), `pypdfium2`/`pdfplumber` (render QA). Reuses the shared brand-token loader
and chart helpers from `fin-model-presentation`. Registered at `.agents/skills/brand-deck/`.
