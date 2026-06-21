"""
identity.py — extract an EXISTING visual identity into a brand-token file (brand-deck)
═══════════════════════════════════════════════════════════════════════════════════════
The differentiator: most deck tools invent a fresh look. This skill *extracts* an
identity that already exists (logo, style guide, packaging photo, prior deck, or a
verbal description) and emits a brand-token JSON that the rest of the skill — and the
financial-presentation skill — consume. Colours are SAMPLED from images, not guessed.

Token format (shared with fin-model-presentation's brand_tokens loader):
{
  "palette": {"primary":{"hex","role"}, "secondary":{...}, "accents":[{...}],
              "ink":{...}, "paper":{...}},
  "type":    {"heading","body","fallback_heading","fallback_body"},
  "voice":   {"adjectives":[...], "taglines":[...]},
  "motif":   {"kind": "dot|corner|frame|duotone", "note": "..."}
}
"""

from __future__ import annotations

import os
import re
import json
import colorsys


# ── colour helpers ────────────────────────────────────────────────────────────
def _hex(rgb):
    return "#%02X%02X%02X" % (int(rgb[0]), int(rgb[1]), int(rgb[2]))


def _rgb(hexstr):
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _sat_val(rgb):
    r, g, b = [c / 255 for c in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return s, l, h


def sample_palette_from_image(path, n_colors=8):
    """Quantize an image to its dominant colours (weight-ranked). Returns
    [{hex, weight, sat, lum, hue}]. This is real sampling, not estimation."""
    from PIL import Image
    img = Image.open(path).convert("RGB")
    img.thumbnail((200, 200))
    q = img.quantize(colors=n_colors, method=Image.Quantize.FASTOCTREE)
    pal = q.getpalette()
    counts = q.getcolors() or []
    out = []
    total = sum(c for c, _ in counts) or 1
    for count, idx in counts:
        rgb = pal[idx * 3:idx * 3 + 3]
        s, l, h = _sat_val(rgb)
        out.append({"hex": _hex(rgb), "weight": count / total, "sat": s, "lum": l, "hue": h})
    out.sort(key=lambda c: c["weight"], reverse=True)
    return out


def assign_roles(swatches):
    """Assign palette jobs (don't just collect colours). Picks paper (lightest),
    ink (darkest), a dominant saturated primary, a distinct secondary, and accents."""
    if not swatches:
        return None
    paper = max(swatches, key=lambda c: c["lum"])     # lightest = background
    ink = min(swatches, key=lambda c: c["lum"])        # darkest = text
    # the brand PRIMARY is the dominant *saturated* colour (a light background is NOT
    # the primary, even though it covers the most area) — weight among chromatic hues.
    chromatic = [c for c in swatches if c is not paper and c["sat"] > 0.18 and c["lum"] < 0.82]
    chromatic.sort(key=lambda c: c["weight"] * 0.6 + c["sat"] * 0.4, reverse=True)
    if not chromatic:
        chromatic = [c for c in swatches if c is not paper] or swatches
    primary = chromatic[0]

    def hue_dist(a, b):
        d = abs(a["hue"] - b["hue"]) % 1.0
        return min(d, 1 - d)
    rest = [c for c in chromatic[1:]]
    # accents = remaining chromatic ranked by vividness (emphasis colours)
    accents = sorted(rest, key=lambda c: c["sat"], reverse=True)[:3]
    # secondary = the most hue-distant support colour; fall back to the top accent
    secondary = max(rest, key=lambda c: hue_dist(c, primary)) if rest else (accents[0] if accents else primary)
    if not accents:
        accents = [secondary]
    return {
        "primary": {"hex": primary["hex"], "role": "dominant — 60–70% of surface area"},
        "secondary": {"hex": secondary["hex"], "role": "support / secondary fields"},
        "accents": [{"hex": a["hex"], "role": "emphasis only (<10%)"} for a in accents],
        "ink": {"hex": ink["hex"], "role": "primary text"},
        "paper": {"hex": paper["hex"], "role": "background"},
    }


# ── description parsing (verbal identity) ──────────────────────────────────────
def parse_voice(description: str):
    adjectives, taglines = [], []
    if description:
        taglines = re.findall(r"[\"“]([^\"”]{3,60})[\"”]", description)
        m = re.search(r"(?:voice|tone|feel[s]?|adjectives?)[:\-]?\s*([A-Za-z,\s&/]+)", description, re.I)
        if m:
            adjectives = [w.strip().lower() for w in re.split(r"[,/&]| and ", m.group(1)) if w.strip()][:5]
    return {"adjectives": adjectives, "taglines": taglines}


# ── public API ─────────────────────────────────────────────────────────────────
def extract_identity(sources: dict, out_path: str = None) -> dict:
    """sources may include:
        image / logo : path → colours sampled from the artifact
        palette      : explicit {primary, secondary, accents, ink, paper} (hex)
        description  : verbal identity (voice adjectives, taglines)
        heading_font / body_font : type families (with safe fallbacks recorded)
        motif        : {kind, note}
    Produces a brand-token dict (and writes JSON if out_path given)."""
    sources = sources or {}
    palette = None

    if sources.get("palette"):
        p = sources["palette"]
        palette = {
            "primary": {"hex": p["primary"], "role": "dominant — 60–70% of surface area"},
            "secondary": {"hex": p.get("secondary", p["primary"]), "role": "support"},
            "accents": [{"hex": a, "role": "emphasis only (<10%)"} for a in p.get("accents", [])],
            "ink": {"hex": p.get("ink", "#1A1A1A"), "role": "primary text"},
            "paper": {"hex": p.get("paper", "#FFFFFF"), "role": "background"},
        }
    img = sources.get("image") or sources.get("logo")
    if palette is None and img and os.path.exists(img):
        palette = assign_roles(sample_palette_from_image(img))
    if palette is None:
        # last-resort neutral identity (clearly recorded as a fallback)
        palette = {"primary": {"hex": "#1F3864", "role": "dominant"},
                   "secondary": {"hex": "#2E75B6", "role": "support"},
                   "accents": [{"hex": "#C0A062", "role": "emphasis"}],
                   "ink": {"hex": "#1A1A1A", "role": "text"},
                   "paper": {"hex": "#FFFFFF", "role": "background"}}

    heading = sources.get("heading_font", "Helvetica-Bold")
    body = sources.get("body_font", "Helvetica")
    tokens = {
        "palette": palette,
        "type": {"heading": heading, "body": body,
                 # safe fallbacks: reportlab-registered families that won't break QA
                 "fallback_heading": "Helvetica-Bold", "fallback_body": "Helvetica"},
        "voice": sources.get("voice") or parse_voice(sources.get("description", "")),
        "motif": sources.get("motif") or {"kind": "dot",
                 "note": "a single repeated brand mark — repetition reads as identity"},
        "_provenance": {"colour_source": ("image:" + os.path.basename(img)) if img else
                        ("explicit palette" if sources.get("palette") else "fallback"),
                        "sampled": bool(img and not sources.get("palette"))},
    }
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(tokens, f, indent=2)
        tokens["_path"] = os.path.abspath(out_path)
    return tokens
