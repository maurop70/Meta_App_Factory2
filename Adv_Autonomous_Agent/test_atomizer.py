# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
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



import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import json

# Add shared utils to path
SHARED_UTILS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils"))
if SHARED_UTILS not in sys.path: sys.path.append(SHARED_UTILS)

from atomizer import Atomizer

class TestAtomizer(unittest.TestCase):
    def setUp(self):
        self.atomizer = Atomizer()

    @patch('bridge.call_app')
    def test_evaluate_complex(self, mock_call):
        # Mock response for a complex task
        mock_response = '["Task 1", "Task 2", "Task 3", "Task 4"]'
        mock_call.return_value = mock_response

        chunks = self.atomizer.evaluate("Complex Prompt")
        self.assertEqual(len(chunks), 4)
        self.assertEqual(chunks[0], "Task 1")

    @patch('bridge.call_app')
    def test_evaluate_simple(self, mock_call):
        # Mock response for a simple task
        mock_call.return_value = "[]"
        
        chunks = self.atomizer.evaluate("Simple Prompt")
        self.assertEqual(len(chunks), 0)

    def test_stitch(self):
        results = ["Result 1", "Result 2"]
        report = self.atomizer.stitch(results)
        self.assertIn("# ATOMIZER SYNTHESIS REPORT", report)
        self.assertIn("## Part 1", report)
        self.assertIn("Result 1", report)

if __name__ == '__main__':
    unittest.main()
# V3 AUTO-HEAL ACTIVE
