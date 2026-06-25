"""Unit tests for Dr. Aris Phase 1 fix: defensive Gemini response parsing.

Covers the KeyError('candidates') class of crashes — Gemini omits "candidates"
when a request is blocked or errored, so parse_gemini_response must return a
structured result for every failure path and never raise.
"""

import dr_aris_engine as dr


class MockResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON content")
        return self._payload


# ── REQUIRED cases: each returns a structured result, none raise ────────────

def test_blocked_payload_with_blockreason_and_no_candidates():
    # (a) Gemini blocked the prompt: promptFeedback.blockReason, no candidates key.
    resp = MockResponse(200, {"promptFeedback": {"blockReason": "SAFETY"}})
    result = dr.parse_gemini_response("sent", resp)
    assert result["status"] == "blocked"
    assert result["reason"] == "SAFETY"


def test_empty_candidates_payload():
    # (b) 200 OK but candidates is an empty list.
    resp = MockResponse(200, {"candidates": []})
    result = dr.parse_gemini_response("sent", resp)
    assert result["status"] == "error"
    assert "candidate" in result["error"].lower()


def test_non_200_response():
    # (c) Non-200 HTTP status.
    resp = MockResponse(503, payload=None, text="Service Unavailable")
    result = dr.parse_gemini_response("sent", resp)
    assert result["status"] == "error"
    assert "503" in result["error"]


# ── Additional ordered-check coverage ───────────────────────────────────────

def test_candidates_key_entirely_absent():
    # The literal KeyError('candidates') scenario: key not present at all.
    resp = MockResponse(200, {"usageMetadata": {"totalTokenCount": 5}})
    result = dr.parse_gemini_response("sent", resp)
    assert result["status"] == "error"


def test_interrupted_finish_reason():
    resp = MockResponse(200, {"candidates": [{"finishReason": "RECITATION", "content": {"parts": []}}]})
    result = dr.parse_gemini_response("sent", resp)
    assert result["status"] == "error"
    assert "RECITATION" in result["error"]


def test_invalid_json_body():
    resp = MockResponse(200, payload=None, text="<html>not json</html>")
    result = dr.parse_gemini_response("sent", resp)
    assert result["status"] == "error"
    assert "json" in result["error"].lower()


def test_buffered_and_failed_statuses_short_circuit():
    # safe_post_with_response can return (status, None) with no response object.
    assert dr.parse_gemini_response("buffered", None)["status"] == "buffered"
    assert dr.parse_gemini_response("failed", None)["status"] == "failed"


def test_successful_response_extracts_text():
    resp = MockResponse(200, {
        "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "Hello Leo"}]}}]
    })
    result = dr.parse_gemini_response("sent", resp)
    assert result["status"] == "success"
    assert result["text"] == "Hello Leo"


# ── Call-site integration: graceful fallback, never an unhandled exception ───

def test_boardroom_query_returns_graceful_on_blocked(monkeypatch):
    monkeypatch.setattr(dr, "_get_api_key", lambda: "dummy-key")
    blocked = MockResponse(200, {"promptFeedback": {"blockReason": "SAFETY"}})
    monkeypatch.setattr(dr, "safe_post_with_response", lambda *a, **k: ("sent", blocked))
    result = dr.boardroom_query("How do anxious teens engage with companion apps?")
    assert result["status"] == "error"  # graceful structured fallback, no raise


def test_analyze_profile_returns_graceful_on_non200(monkeypatch):
    monkeypatch.setattr(dr, "_get_api_key", lambda: "dummy-key")
    monkeypatch.setattr(dr, "_is_sandbox_active", lambda: False)
    monkeypatch.setattr(dr, "safe_post_with_response",
                        lambda *a, **k: ("sent", MockResponse(503, text="err")))
    # Avoid touching real report files on the graceful-degradation path.
    monkeypatch.setattr(dr, "run_alert_scan", lambda *a, **k: [])
    monkeypatch.setattr(dr, "_load_reports", lambda: dr._empty_reports())
    monkeypatch.setattr(dr, "_save_reports", lambda r: None)

    result = dr.analyze_profile(parent_config={}, hints_data={"hints": []}, recent_history=[])
    # No exception; returns a structured report with the fallback profile.
    assert isinstance(result, dict)
    assert "psychological_profile" in result
    assert result["psychological_profile"]["attachment_style"].startswith("Unable to assess")
