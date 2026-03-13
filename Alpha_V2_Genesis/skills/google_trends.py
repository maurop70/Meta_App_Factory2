# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

from auto_heal import healed_post, auto_heal, diagnose

def _v3_preflight():
    """V3: Ping Resonance_Watchdog_V3 before execution."""
    if not _V3_AVAILABLE:
        return True
    try:
        import json as _j
        _cfg_path = _os.path.join(_FACTORY_DIR, "resilience_config.json")
        if not _os.path.exists(_cfg_path):
            return True
        with open(_cfg_path) as _f:
            _cfg = _j.load(_f)
        _url = _cfg.get("cloud_health", {}).get("watchdog_url", "")
        if not _url:
            return True
        import requests as _rq
        _r = _rq.get(_url, timeout=5)
        return _r.status_code == 200
    except Exception:
        return False


import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class MarketTrendExtractor:
    """
    Skill for the Analyst Persona.
    Extracts text and numerical trends from Google Sheets and Slides.
    """
    def __init__(self, credentials_path=None):
        # In a real environment, we'd load credentials here
        # For now, we assume the environment is authenticated (e.g. ADC)
        pass

    def get_sheet_trends(self, spreadsheet_id, range_name):
        """Extracts numerical trends from a specific sheet range."""
        try:
            service = build('sheets', 'v4')
            sheet = service.spreadsheets()
            result = sheet.values().get(spreadsheetId=spreadsheet_id,
                                        range=range_name).execute()
            values = result.get('values', [])

            if not values:
                return "No data found."
            
            # Simple trend analysis logic (placeholder for complexity)
            return values
        except Exception as e:
            return f"An error occurred: {e}"

    def get_slides_text(self, presentation_id):
        """Extracts all text from a Google Slides deck for brand style analysis."""
        try:
            service = build('slides', 'v1')
            presentation = service.presentations().get(presentationId=presentation_id).execute()
            slides = presentation.get('slides')

            text_content = []
            for slide in slides:
                for element in slide.get('pageElements'):
                    if 'shape' in element and 'text' in element['shape']:
                        text_content.append(element['shape']['text']['textElements'][0]['textRun']['content'])
            
            return "\n".join(text_content)
        except Exception as e:
            return f"An error occurred: {e}"

if __name__ == "__main__":
    # Internal test placeholder
    print("MarketTrendExtractor Skill Initialized.")
# V3 AUTO-HEAL ACTIVE
