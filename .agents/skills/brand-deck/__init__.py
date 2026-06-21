"""brand-deck skill — decks/brochures that honor an EXISTING visual identity."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

from identity import extract_identity, sample_palette_from_image, assign_roles
from deck import DeckBuilder, build_deck, default_pitch_content
from qa import qa_deck, render_pages

__all__ = ["extract_identity", "sample_palette_from_image", "assign_roles",
           "DeckBuilder", "build_deck", "default_pitch_content", "qa_deck", "render_pages"]
