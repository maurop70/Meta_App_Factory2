"""
charts_pdf.py — brand-colored vector charts for the board PDF (reportlab shapes)
════════════════════════════════════════════════════════════════════════════════
Hand-drawn (shape-level) charts give predictable geometry, exact brand colours,
and clean handling of negative values (EBITDA Year-1, the cumulative-FCF trough)
without depending on library defaults. Each returns a reportlab Drawing.
"""

from __future__ import annotations

from reportlab.graphics.shapes import Drawing, Rect, Line, String, PolyLine, Polygon, Group
from reportlab.lib.colors import HexColor, Color


def _c(hexstr):
    return HexColor(hexstr if hexstr.startswith("#") else "#" + hexstr)


def _tint(hexstr, factor):
    """Lighten a hex colour toward white by factor (0..1)."""
    col = _c(hexstr)
    r = col.red + (1 - col.red) * factor
    g = col.green + (1 - col.green) * factor
    b = col.blue + (1 - col.blue) * factor
    return Color(r, g, b)


def _money_short(v):
    a = abs(v)
    if a >= 1_000_000:
        s = f"{v/1_000_000:.1f}M"
    elif a >= 1_000:
        s = f"{v/1_000:.0f}K"
    else:
        s = f"{v:.0f}"
    return s


# ── plot frame helpers ───────────────────────────────────────────────────────
def _frame(d, x0, y0, w, h, tokens):
    d.add(Rect(x0, y0, w, h, strokeColor=None, fillColor=_c(tokens.paper)))


def _axes(d, x0, y0, w, h, vmin, vmax, tokens, gridlines=4):
    ink = _c(tokens.ink)
    muted = _c(tokens.muted)
    span = (vmax - vmin) or 1
    # horizontal gridlines + labels
    for i in range(gridlines + 1):
        val = vmin + span * i / gridlines
        yy = y0 + h * (val - vmin) / span
        is_zero = abs(val) < span * 1e-6 or (vmin < 0 < vmax and abs(val) < span / gridlines / 2)
        d.add(Line(x0, yy, x0 + w, yy, strokeColor=ink if (vmin < 0 <= val <= 0) else _tint(tokens.muted, 0.6),
                   strokeWidth=0.25))
        d.add(String(x0 - 4, yy - 3, _money_short(val), fontName=tokens.body_font,
                     fontSize=6, fillColor=muted, textAnchor="end"))
    # zero baseline emphasised
    if vmin < 0 < vmax:
        yz = y0 + h * (0 - vmin) / span
        d.add(Line(x0, yz, x0 + w, yz, strokeColor=ink, strokeWidth=0.8))


def _yof(val, y0, h, vmin, vmax):
    span = (vmax - vmin) or 1
    return y0 + h * (val - vmin) / span


def bar_line_combo(width, height, cats, bar_vals, line_vals, tokens,
                   bar_label="Revenue", line_label="EBITDA"):
    d = Drawing(width, height)
    pad_l, pad_r, pad_t, pad_b = 34, 34, 24, 24
    x0, y0 = pad_l, pad_b
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    _frame(d, 0, 0, width, height, tokens)

    bmin, bmax = min(bar_vals + [0]), max(bar_vals + [0])
    lmin, lmax = min(line_vals + [0]), max(line_vals + [0])
    if bmax == bmin:
        bmax = bmin + 1
    _axes(d, x0, y0, w, h, bmin, bmax * 1.1, tokens)

    n = len(cats)
    slot = w / n
    bw = slot * 0.5
    # bars (revenue)
    for i, v in enumerate(bar_vals):
        cx = x0 + slot * (i + 0.5)
        yb = _yof(0, y0, h, bmin, bmax * 1.1)
        yv = _yof(v, y0, h, bmin, bmax * 1.1)
        d.add(Rect(cx - bw / 2, min(yb, yv), bw, abs(yv - yb),
                   fillColor=_c(tokens.secondary), strokeColor=None))
        d.add(String(cx, yv + 3, _money_short(v), fontName=tokens.body_font, fontSize=6,
                     fillColor=_c(tokens.ink), textAnchor="middle"))
        d.add(String(cx, y0 - 12, str(cats[i]), fontName=tokens.body_font, fontSize=6.5,
                     fillColor=_c(tokens.muted), textAnchor="middle"))
    # line (EBITDA) on its own scaling, overlaid
    lspan = (lmax * 1.1 - lmin) or 1
    pts = []
    for i, v in enumerate(line_vals):
        cx = x0 + slot * (i + 0.5)
        yv = y0 + h * (v - lmin) / lspan
        pts.extend([cx, yv])
    d.add(PolyLine(pts, strokeColor=_c(tokens.primary), strokeWidth=2))
    for i in range(0, len(pts), 2):
        d.add(Polygon([pts[i] - 2.2, pts[i + 1], pts[i], pts[i + 1] + 2.2,
                       pts[i] + 2.2, pts[i + 1], pts[i], pts[i + 1] - 2.2],
                      fillColor=_c(tokens.primary), strokeColor=None))
    # legend
    d.add(Rect(x0, height - pad_t + 8, 8, 8, fillColor=_c(tokens.secondary), strokeColor=None))
    d.add(String(x0 + 11, height - pad_t + 9, bar_label, fontName=tokens.body_font, fontSize=7,
                 fillColor=_c(tokens.ink)))
    d.add(Line(x0 + 70, height - pad_t + 12, x0 + 84, height - pad_t + 12,
               strokeColor=_c(tokens.primary), strokeWidth=2))
    d.add(String(x0 + 88, height - pad_t + 9, line_label, fontName=tokens.body_font, fontSize=7,
                 fillColor=_c(tokens.ink)))
    return d


def line_chart(width, height, cats, vals, tokens, label="Cumulative FCF", fill=True):
    d = Drawing(width, height)
    pad_l, pad_r, pad_t, pad_b = 34, 16, 22, 24
    x0, y0 = pad_l, pad_b
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    _frame(d, 0, 0, width, height, tokens)
    vmin, vmax = min(vals + [0]), max(vals + [0])
    pad = (vmax - vmin) * 0.1 or 1
    vmin -= pad; vmax += pad
    _axes(d, x0, y0, w, h, vmin, vmax, tokens)
    n = len(vals)
    slot = w / max(n - 1, 1)
    pts = []
    for i, v in enumerate(vals):
        cx = x0 + slot * i
        yv = _yof(v, y0, h, vmin, vmax)
        pts.extend([cx, yv])
        d.add(String(cx, y0 - 12, str(cats[i]), fontName=tokens.body_font, fontSize=6.5,
                     fillColor=_c(tokens.muted), textAnchor="middle"))
    if fill:
        yz = _yof(0, y0, h, vmin, vmax)
        poly = [pts[0], yz] + pts + [pts[-2], yz]
        d.add(Polygon(poly, fillColor=_tint(tokens.primary, 0.78), strokeColor=None))
    d.add(PolyLine(pts, strokeColor=_c(tokens.primary), strokeWidth=2))
    # mark the trough (deepest cumulative FCF = peak funding)
    tmin_i = min(range(n), key=lambda i: vals[i])
    cx = x0 + slot * tmin_i
    yv = _yof(vals[tmin_i], y0, h, vmin, vmax)
    d.add(Polygon([cx - 3, yv, cx, yv + 3, cx + 3, yv, cx, yv - 3],
                  fillColor=_c(tokens.accents[2] if len(tokens.accents) > 2 else tokens.primary),
                  strokeColor=None))
    d.add(String(cx, yv - 12, "trough " + _money_short(vals[tmin_i]), fontName=tokens.body_font,
                 fontSize=6, fillColor=_c(tokens.ink), textAnchor="middle"))
    d.add(String(x0, height - pad_t + 8, label, fontName=tokens.heading_font, fontSize=7.5,
                 fillColor=_c(tokens.primary)))
    return d


def hbar_tornado(width, height, labels, values, tokens, title="Tornado — EBITDA swing"):
    d = Drawing(width, height)
    pad_l, pad_r, pad_t, pad_b = 70, 30, 22, 14
    x0, y0 = pad_l, pad_b
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    _frame(d, 0, 0, width, height, tokens)
    vmax = max(values) or 1
    n = len(labels)
    slot = h / n
    bh = slot * 0.6
    for i, (lab, v) in enumerate(zip(labels, values)):
        cy = y0 + slot * (n - 1 - i) + (slot - bh) / 2
        bw = w * (v / vmax)
        col = tokens.series[i % len(tokens.series)]
        d.add(Rect(x0, cy, bw, bh, fillColor=_c(col), strokeColor=None))
        d.add(String(x0 - 4, cy + bh / 2 - 3, str(lab), fontName=tokens.body_font, fontSize=7,
                     fillColor=_c(tokens.ink), textAnchor="end"))
        d.add(String(x0 + bw + 3, cy + bh / 2 - 3, _money_short(v), fontName=tokens.body_font,
                     fontSize=6.5, fillColor=_c(tokens.muted)))
    d.add(String(x0 - 60, height - pad_t + 6, title, fontName=tokens.heading_font, fontSize=7.5,
                 fillColor=_c(tokens.primary)))
    return d


def vbar_scenarios(width, height, labels, values, tokens, title="Scenarios — EBITDA"):
    d = Drawing(width, height)
    pad_l, pad_r, pad_t, pad_b = 36, 16, 22, 22
    x0, y0 = pad_l, pad_b
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    _frame(d, 0, 0, width, height, tokens)
    vmin, vmax = min(values + [0]), max(values + [0])
    if vmax == vmin:
        vmax = vmin + 1
    _axes(d, x0, y0, w, h, vmin, vmax * 1.12, tokens)
    n = len(labels)
    slot = w / n
    bw = slot * 0.5
    colors = [tokens.accents[2] if len(tokens.accents) > 2 else tokens.primary,
              tokens.secondary, tokens.accents[0] if tokens.accents else tokens.primary]
    for i, (lab, v) in enumerate(zip(labels, values)):
        cx = x0 + slot * (i + 0.5)
        yb = _yof(0, y0, h, vmin, vmax * 1.12)
        yv = _yof(v, y0, h, vmin, vmax * 1.12)
        d.add(Rect(cx - bw / 2, min(yb, yv), bw, abs(yv - yb),
                   fillColor=_c(colors[i % len(colors)]), strokeColor=None))
        d.add(String(cx, (max(yb, yv)) + 3, _money_short(v), fontName=tokens.body_font, fontSize=6.5,
                     fillColor=_c(tokens.ink), textAnchor="middle"))
        d.add(String(cx, y0 - 11, str(lab), fontName=tokens.body_font, fontSize=7,
                     fillColor=_c(tokens.muted), textAnchor="middle"))
    d.add(String(x0 - 30, height - pad_t + 6, title, fontName=tokens.heading_font, fontSize=7.5,
                 fillColor=_c(tokens.primary)))
    return d
