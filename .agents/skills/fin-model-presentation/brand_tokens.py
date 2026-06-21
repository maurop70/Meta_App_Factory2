"""
brand_tokens.py — shared brand-token loader (MAF skills: fin-model-presentation, brand-deck)
════════════════════════════════════════════════════════════════════════════════════════════
A single normalized view of a company's visual identity, consumed by BOTH the
financial presentation layer (chart + PDF colours) and the brand-deck skill.

Accepts either:
  • the rich brand-deck token format:
      {"palette": {"primary": {"hex": "#1F3864", "role": "..."},
                   "secondary": {"hex": "#2E75B6"}, "accents": [{"hex": "#548235"}, ...],
                   "ink": {"hex": "#1A1A1A"}, "paper": {"hex": "#FFFFFF"}},
       "type": {"heading": "Georgia", "body": "Arial",
                "fallback_heading": "Georgia", "fallback_body": "Arial"}}
  • a flat format: {"primary": "#1F3864", "secondary": "#2E75B6",
       "accents": ["#548235", "#BF8F00"], "ink": "#1A1A1A", "paper": "#FFFFFF",
       "heading_font": "Georgia", "body_font": "Arial"}
  • a path to a JSON file in either format
  • None → a professional brand-neutral default (navy) consistent with the
    fin-model spreadsheet banners, so output is always on-palette.
"""

from __future__ import annotations

import json
import os

# Default palette — matches the fin-model workbook banners (navy / blue / green / gold)
_DEFAULT = {
    "primary": "#1F3864",     # deep navy  — banners, dominant fields
    "secondary": "#2E75B6",   # mid blue   — revenue series, secondary fills
    "accents": ["#548235", "#BF8F00", "#C00000"],  # green / gold / red
    "ink": "#1A1A1A",         # near-black text
    "paper": "#FFFFFF",
    "muted": "#808080",
    "heading_font": "Helvetica-Bold",
    "body_font": "Helvetica",
}


def _hexnorm(h: str, fallback="#000000") -> str:
    if not h:
        return fallback
    h = str(h).strip()
    if not h.startswith("#"):
        h = "#" + h
    if len(h) == 4:  # #abc → #aabbcc
        h = "#" + "".join(c * 2 for c in h[1:])
    return h.upper()


class BrandTokens:
    def __init__(self, d: dict):
        self.primary = d["primary"]
        self.secondary = d["secondary"]
        self.accents = d["accents"]
        self.ink = d["ink"]
        self.paper = d["paper"]
        self.muted = d.get("muted", "#808080")
        self.heading_font = d.get("heading_font", "Helvetica-Bold")
        self.body_font = d.get("body_font", "Helvetica")

    # chart series palette: primary, secondary, then accents (cycled)
    @property
    def series(self):
        base = [self.primary, self.secondary] + list(self.accents)
        return [_hexnorm(c) for c in base]

    @staticmethod
    def rgb(hex_color: str) -> str:
        """'#1F3864' → '1F3864' for openpyxl solidFill."""
        return _hexnorm(hex_color)[1:]

    def __repr__(self):
        return f"BrandTokens(primary={self.primary}, secondary={self.secondary})"


def load_tokens(source=None) -> BrandTokens:
    """source: dict | path-to-json | None. Always returns a complete BrandTokens."""
    if source is None:
        data = {}
    elif isinstance(source, str):
        if os.path.exists(source):
            with open(source, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
    elif isinstance(source, dict):
        data = source
    else:
        data = {}

    # Rich brand-deck format → flatten
    if "palette" in data:
        p = data["palette"]
        def gh(node, key, fb):
            v = node.get(key)
            if isinstance(v, dict):
                return _hexnorm(v.get("hex"), fb)
            return _hexnorm(v, fb) if v else fb
        accents = []
        for acc in (p.get("accents") or []):
            accents.append(_hexnorm(acc.get("hex") if isinstance(acc, dict) else acc))
        t = data.get("type", {})
        flat = {
            "primary": gh(p, "primary", _DEFAULT["primary"]),
            "secondary": gh(p, "secondary", _DEFAULT["secondary"]),
            "accents": accents or [_hexnorm(c) for c in _DEFAULT["accents"]],
            "ink": gh(p, "ink", _DEFAULT["ink"]),
            "paper": gh(p, "paper", _DEFAULT["paper"]),
            "heading_font": t.get("heading") or _DEFAULT["heading_font"],
            "body_font": t.get("body") or _DEFAULT["body_font"],
        }
    else:
        flat = {
            "primary": _hexnorm(data.get("primary"), _DEFAULT["primary"]),
            "secondary": _hexnorm(data.get("secondary"), _DEFAULT["secondary"]),
            "accents": [_hexnorm(c) for c in (data.get("accents") or _DEFAULT["accents"])],
            "ink": _hexnorm(data.get("ink"), _DEFAULT["ink"]),
            "paper": _hexnorm(data.get("paper"), _DEFAULT["paper"]),
            "heading_font": data.get("heading_font") or _DEFAULT["heading_font"],
            "body_font": data.get("body_font") or _DEFAULT["body_font"],
        }
    flat.setdefault("muted", _DEFAULT["muted"])
    return BrandTokens(flat)
