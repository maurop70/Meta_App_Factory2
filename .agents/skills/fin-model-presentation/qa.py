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


# ═══════════════════════════════════════════════════════════════════════════
#  LIVE OFFICE RENDERING — render the actual .xlsx workbook (incl. its native
#  charts) for visual QA via LibreOffice headless conversion to PDF, then raster.
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


def office_to_pdf(office_path: str, out_dir: str = None, timeout: int = 180) -> str:
    """Convert an Office file (.xlsx/.pptx/.docx) to PDF with LibreOffice headless.
    Uses a per-call user-profile dir so a running LibreOffice never blocks the
    conversion. Raises RuntimeError if LibreOffice is unavailable or no PDF emerges."""
    import subprocess
    soffice = _resolve_soffice()
    if not soffice:
        raise RuntimeError("LibreOffice (soffice) not found — set LIBREOFFICE_PATH or "
                           "add it to PATH to enable live .xlsx/.pptx rendering")
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


def qa_xlsx(xlsx_path: str, out_dir: str = None) -> dict:
    """Live visual QA of the generated Excel workbook AND its native charts: convert
    it to PDF with LibreOffice, render each page to PNG, and scan the rendered text
    for spreadsheet error markers (#REF!/#DIV/0!/#VALUE!/…). `clean` is True only when
    pages rendered and no error/placeholder text is present."""
    import pdfplumber
    pdf = office_to_pdf(xlsx_path, out_dir=out_dir)
    report = {"source_xlsx": os.path.abspath(xlsx_path), "pdf_path": os.path.abspath(pdf),
              "png_pages": [], "issues": [], "clean": False}
    full_text = ""
    with pdfplumber.open(pdf) as doc:
        for page in doc.pages:
            full_text += "\n" + (page.extract_text() or "")
    hits = _placeholder_hits(full_text)
    if hits:
        report["issues"].append({"page": "doc",
                                 "issues": [f"spreadsheet error/placeholder text: {hits}"]})
    try:
        report["png_pages"] = render_pages(pdf, out_dir=out_dir)
    except Exception as e:
        report["issues"].append({"page": "render", "issues": [f"render failed: {e!r}"]})
    report["page_count"] = len(report["png_pages"])
    report["clean"] = not report["issues"] and report["page_count"] > 0
    return report
