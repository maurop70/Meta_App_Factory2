"""Unit tests for Dr. Aris safe_post fix."""

import pytest
from Resonance_Engines.dr_aris_engine import parse_gemini_response

class MockResponse:
    def __init__(self, status_code, json_data, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        if self._json_data is None:
            raise ValueError("No JSON")
        return self._json_data


def test_blocked_payload_no_candidates():
    """Test 1: A blocked payload with blockReason and no candidates."""
    blocked_json = {
        "promptFeedback": {
            "blockReason": "SAFETY"
        }
    }
    resp = MockResponse(200, blocked_json)
    res = parse_gemini_response("sent", resp)
    assert res["status"] == "blocked"
    assert res["reason"] == "SAFETY"


def test_empty_candidates_payload():
    """Test 2: An empty-candidates payload."""
    empty_json = {
        "candidates": []
    }
    resp = MockResponse(200, empty_json)
    res = parse_gemini_response("sent", resp)
    assert res["status"] == "error"
    assert "No candidates" in res["error"]


def test_non_200_response():
    """Test 3: A non-200 response."""
    resp = MockResponse(500, None, text="Internal Server Error")
    res = parse_gemini_response("sent", resp)
    assert res["status"] == "error"
    assert "HTTP 500" in res["error"]
