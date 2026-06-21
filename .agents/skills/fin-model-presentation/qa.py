"""
qa.py — render-and-inspect QA loop for the board PDF (MAF skill)
════════════════════════════════════════════════════════════════
Renders every PDF page to PNG (pdfplumber's native page.to_image — no Poppler
needed on Windows) and inspects each page for the failure modes that separate
"fine" from "studio": text overflow past the margins, placeholder text, empty
pages, and missing expected sections. Returns a structured report; `clean` is
the gate the presentation skill loops on.
"""

from __future__ import annotations

import os
import re

# word-boundary tokens (avoid false hits like "nan" inside "Financial")
PLACEHOLDERS_WORD = ("lorem", "todo", "xxx", "placeholder", "tbd", "nan", "undefined")
# literal substrings (safe to match anywhere)
PLACEHOLDERS_SUB = ("{{", "[[", "none none", "#ref!", "#name?", "#div/0!", "#value!")


def _placeholder_hits(text: str) -> list:
    low = text.lower()
    hits = [p for p in PLACEHOLDERS_SUB if p in low]
    for w in PLACEHOLDERS_WORD:
        if re.search(r"\b" + re.escape(w) + r"\b", low):
            hits.append(w)
    return hits


def render_pages(pdf_path: str, out_dir: str = None, resolution: int = 120) -> list:
    import pdfplumber
    if out_dir is None:
        out_dir = os.path.splitext(pdf_path)[0] + "_pages"
    os.makedirs(out_dir, exist_ok=True)
    pngs = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            png = os.path.join(out_dir, f"page_{i+1}.png")
            im = page.to_image(resolution=resolution)
            im.save(png)
            pngs.append(png)
    return pngs


def qa_pdf(pdf_path: str, expect_sections=None) -> dict:
    import pdfplumber
    expect_sections = expect_sections or ["Income Statement", "Cash Flow", "Sensitivity"]
    report = {"pdf_path": os.path.abspath(pdf_path), "pages": [], "png_pages": [],
              "issues": [], "clean": False}
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        pw = pdf.pages[0].width if pdf.pages else 0
        ph = pdf.pages[0].height if pdf.pages else 0
        margin = 30
        for i, page in enumerate(pdf.pages):
            words = page.extract_words() or []
            text = page.extract_text() or ""
            full_text += "\n" + text
            # overflow: any word crossing the page margins
            overflow = [w for w in words
                        if w["x1"] > page.width - 6 or w["x0"] < 6 or
                        w["bottom"] > page.height - 4 or w["top"] < 2]
            ph_hits = _placeholder_hits(text)
            empty = len(text.strip()) < 5
            page_issues = []
            if overflow:
                page_issues.append(f"{len(overflow)} word(s) at/over the page edge")
            if ph_hits:
                page_issues.append(f"placeholder/error text: {ph_hits}")
            if empty:
                page_issues.append("page nearly empty")
            report["pages"].append({"page": i + 1, "word_count": len(words),
                                    "issues": page_issues})
            if page_issues:
                report["issues"].append({"page": i + 1, "issues": page_issues})
    # expected sections present somewhere
    missing = [s for s in expect_sections if s.lower() not in full_text.lower()]
    if missing:
        report["issues"].append({"page": "doc", "issues": [f"missing sections: {missing}"]})
    # render pages last (so a render failure doesn't hide text QA)
    try:
        report["png_pages"] = render_pages(pdf_path)
    except Exception as e:
        report["issues"].append({"page": "render", "issues": [f"render failed: {e!r}"]})
    report["page_count"] = len(report["pages"])
    report["clean"] = len(report["issues"]) == 0
    return report
