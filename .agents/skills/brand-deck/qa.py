"""
qa.py — render-and-inspect QA loop for the deck (brand-deck)
════════════════════════════════════════════════════════════
Renders every page to PNG (pypdfium2, falling back to pdfplumber) and inspects for
the failure modes that separate "fine" from "studio": text overflow/collision past
the margins, placeholder text, empty pages, and missing expected slides. Always
verify the *rendered* file, never the source. `clean` is the gate to loop on.
"""

from __future__ import annotations

import os
import re

PLACEHOLDERS_WORD = ("lorem", "todo", "xxx", "placeholder", "tbd", "nan", "undefined", "none")
PLACEHOLDERS_SUB = ("{{", "[[", "#ref!", "$0", "illustrative")


def render_pages(pdf_path, resolution=130):
    out_dir = os.path.splitext(pdf_path)[0] + "_pages"
    os.makedirs(out_dir, exist_ok=True)
    pngs = []
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_path)
        try:
            pdf.init_forms()
        except Exception:
            pass
        for i in range(len(pdf)):
            png = os.path.join(out_dir, f"slide_{i+1}.png")
            pdf[i].render(scale=resolution / 72.0).to_pil().save(png)
            pngs.append(png)
        return pngs
    except Exception:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                png = os.path.join(out_dir, f"slide_{i+1}.png")
                page.to_image(resolution=resolution).save(png)
                pngs.append(png)
        return pngs


def _placeholders(text):
    low = text.lower()
    hits = [p for p in PLACEHOLDERS_SUB if p in low]
    for w in PLACEHOLDERS_WORD:
        if re.search(r"\b" + re.escape(w) + r"\b", low):
            hits.append(w)
    return hits


def qa_deck(pdf_path, expect_slides=None, margin=18):
    import pdfplumber
    report = {"pdf_path": os.path.abspath(pdf_path), "slides": [], "issues": [], "clean": False}
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            words = page.extract_words() or []
            text = page.extract_text() or ""
            overflow = [w for w in words if w["x1"] > page.width - margin or w["x0"] < margin - 6
                        or w["bottom"] > page.height - margin or w["top"] < margin - 6]
            ph = _placeholders(text)
            empty = len(text.strip()) < 2
            issues = []
            if overflow:
                issues.append(f"{len(overflow)} word(s) past the margin: "
                              f"{[w['text'] for w in overflow[:4]]}")
            if ph:
                issues.append(f"placeholder/empty-value text: {ph}")
            if empty:
                issues.append("slide nearly empty")
            report["slides"].append({"slide": i + 1, "words": len(words), "issues": issues})
            if issues:
                report["issues"].append({"slide": i + 1, "issues": issues})
    if expect_slides and len(report["slides"]) != expect_slides:
        report["issues"].append({"slide": "doc",
                                 "issues": [f"expected {expect_slides} slides, got {len(report['slides'])}"]})
    report["png_pages"] = render_pages(pdf_path)
    report["slide_count"] = len(report["slides"])
    report["clean"] = len(report["issues"]) == 0
    return report
