"""samples.py — generate a sample logo so identity extraction can be demoed."""
import os


def make_logo(path, primary="#0E3B2E", cream="#EDE3CF", accent="#C8892A"):
    """A simple but real logo artifact (deep-green roundel + amber bean + wordmark)
    so colour SAMPLING recovers a genuine palette."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import letter
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp_pdf = path + ".tmp.pdf"
    c = canvas.Canvas(tmp_pdf, pagesize=(360, 200))
    c.setFillColor(HexColor(cream)); c.rect(0, 0, 360, 200, fill=1, stroke=0)
    c.setFillColor(HexColor(primary)); c.circle(90, 100, 64, fill=1, stroke=0)
    c.setFillColor(HexColor(accent)); c.ellipse(74, 74, 106, 126, fill=1, stroke=0)
    c.setFillColor(HexColor(cream)); c.rect(88, 74, 4, 52, fill=1, stroke=0)
    c.setFillColor(HexColor(primary)); c.setFont("Helvetica-Bold", 30)
    c.drawString(170, 108, "COLD")
    c.setFillColor(HexColor(accent)); c.drawString(170, 74, "BREW")
    c.save()
    # rasterize to PNG via pypdfium2
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(tmp_pdf)
    pdf[0].render(scale=2.0).to_pil().save(path)
    pdf.close()
    try:
        os.remove(tmp_pdf)
    except OSError:
        pass
    return os.path.abspath(path)


if __name__ == "__main__":
    print(make_logo("out/coldbrew_logo.png"))
