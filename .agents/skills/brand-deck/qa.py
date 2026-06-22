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


# ═══════════════════════════════════════════════════════════════════════════
#  LIVE OFFICE RENDERING — render the actual .pptx deck for visual QA via
#  LibreOffice headless conversion to PDF, then the same render+inspect loop.
# ═══════════════════════════════════════════════════════════════════════════

def _resolve_soffice():
    """Locate the LibreOffice binary across LIBREOFFICE_PATH, PATH, and the common
    Windows/Unix/macOS install locations. Returns the path or None."""
    import shutil
    candidates = [
        os.environ.get("LIBREOFFICE_PATH"),
        shutil.which("soffice"), shutil.which("libreoffice"),
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/usr/bin/soffice", "/usr/bin/libreoffice", "/opt/libreoffice/program/soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for c in candidates:
        if c and (os.path.exists(c) or shutil.which(c)):
            return c
    return None


def office_to_pdf(office_path, out_dir=None, timeout=180):
    """Convert an Office file (.pptx/.xlsx/.docx) to PDF with LibreOffice headless.
    Uses a per-call user-profile dir so a running LibreOffice never blocks the
    conversion. Raises RuntimeError if LibreOffice is unavailable or no PDF emerges."""
    import subprocess
    soffice = _resolve_soffice()
    if not soffice:
        raise RuntimeError("LibreOffice (soffice) not found — set LIBREOFFICE_PATH or "
                           "add it to PATH to enable live .pptx/.xlsx rendering")
    out_dir = out_dir or (os.path.splitext(office_path)[0] + "_render")
    os.makedirs(out_dir, exist_ok=True)
    profile = os.path.abspath(os.path.join(out_dir, "_lo_profile")).replace("\\", "/")
    cmd = [soffice, "--headless", "--norestore", "--nolockcheck",
           f"-env:UserInstallation=file:///{profile}",
           "--convert-to", "pdf", "--outdir", out_dir, os.path.abspath(office_path)]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    pdf = os.path.join(out_dir, os.path.splitext(os.path.basename(office_path))[0] + ".pdf")
    if not os.path.exists(pdf):
        raise RuntimeError(f"LibreOffice produced no PDF for {office_path} "
                           f"(rc={proc.returncode}): {proc.stderr.decode('utf-8','ignore')[:300]}")
    return pdf


def qa_pptx(pptx_path, expect_slides=None, out_dir=None):
    """Live visual QA of the generated PowerPoint: convert the .pptx to PDF with
    LibreOffice, then run the same render+inspect deck QA on the result (overflow,
    placeholder/empty text, slide count). Verifies the *rendered* .pptx, not just the
    source PDF the deck was also exported to."""
    pdf = office_to_pdf(pptx_path, out_dir=out_dir)
    report = qa_deck(pdf, expect_slides=expect_slides)
    report["source_pptx"] = os.path.abspath(pptx_path)
    report["rendered_pdf"] = os.path.abspath(pdf)
    return report
