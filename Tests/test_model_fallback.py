import pytest
from unittest.mock import patch, MagicMock
import os
import sys

# Add directory containing model_router to PATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import model_router

def test_heavy_to_heavy_fallback_claude_to_gemini():
    """Asserts that when Claude Sonnet fails, the router strictly falls back to Gemini Pro."""
    with patch("model_router._call_claude", return_value=""):
        with patch("model_router._call_gemini") as mock_gemini:
            mock_gemini.return_value = "Mocked Gemini Pro Response"
            
            # CFO task prefers CLAUDE_SONNET
            res = model_router.route("CFO", prompt="Calculate Capex")
            
            # Assert Claude was called once, and failed
            # Assert Gemini Pro was called as fallback
            assert "Gemini Pro" in res
            mock_gemini.assert_called_once_with("Calculate Capex", "", model_name="gemini-2.5-pro")

def test_heavy_to_heavy_fallback_gemini_to_claude():
    """Asserts that when Gemini Pro fails, the router strictly falls back to Claude Sonnet."""
    with patch("model_router.get_model_for_task", return_value="gemini-2.5-pro"):
        with patch("model_router._call_gemini", return_value=""):
            with patch("model_router._call_claude") as mock_claude:
                mock_claude.return_value = "Mocked Claude Sonnet Response"
                
                res = model_router.route("CFO", prompt="Calculate Capex")
                
                assert "Claude" in res
                mock_claude.assert_called_once_with("Calculate Capex", "")

def test_speed_to_clean_failure_without_ha():
    """Asserts that when Gemini Flash fails under high_availability=False, it fails cleanly."""
    with patch("model_router.get_model_for_task", return_value="gemini-2.5-flash"):
        with patch("model_router._call_gemini", return_value=""):
            with patch("model_router._call_claude") as mock_claude:
                
                res = model_router.route("CEO", prompt="Analyze strategy", high_availability=False)
                
                # Assert clean failure (empty string)
                assert res == ""
                mock_claude.assert_not_called()

def test_speed_to_heavy_fallback_with_ha():
    """Asserts that when Gemini Flash fails under high_availability=True, it falls back to Heavy."""
    with patch("model_router.get_model_for_task", return_value="gemini-2.5-flash"):
        with patch("model_router._call_gemini") as mock_gemini:
            # First call for flash returns empty, second call for pro returns success
            mock_gemini.side_effect = ["", "Mocked Gemini Pro Response"]
            with patch("model_router._call_claude") as mock_claude:
                
                res = model_router.route("CEO", prompt="Analyze strategy", high_availability=True)
                
                assert "Gemini Pro" in res
                # Two calls: first for flash, second for pro
                assert mock_gemini.call_count == 2
                mock_claude.assert_not_called()
