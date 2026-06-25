"""Unit tests for app_stream.py: shared Alex prompt builder, the Anthropic SSE
streaming client, and graceful Claude -> Gemini fallback (Plan v2 §3.3 / §3.4)."""

from unittest.mock import patch

import app_stream


class FakeResponse:
    """Minimal stand-in for a streaming requests.Response (context manager)."""

    def __init__(self, status_code=200, text="", lines=None):
        self.status_code = status_code
        self.text = text
        self.encoding = None
        self._lines = lines or []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_lines(self, decode_unicode=False):
        return iter(self._lines)


def _no_disk(monkeypatch):
    """Stub out every disk-touching helper so tests never mutate real state."""
    monkeypatch.setattr(app_stream, "get_secret", lambda k, *a, **kw: "fake-key")
    monkeypatch.setattr(app_stream, "_is_sandbox_mode", lambda: False)
    monkeypatch.setattr(app_stream, "_load_history", lambda *a, **kw: [])
    monkeypatch.setattr(app_stream, "_save_history", lambda *a, **kw: None)
    monkeypatch.setattr(app_stream, "_collect_hints", lambda *a, **kw: None)
    monkeypatch.setattr(app_stream, "_save_parent_config_for_stream", lambda *a, **kw: None)
    monkeypatch.setattr(app_stream, "_load_parent_config_for_stream",
                        lambda: {"cognitive_metrics": {"current_conversational_level": 4}})


# ── §3.4: shared prompt builder ─────────────────────────────────────────────

def test_build_shared_system_prompt_injects_persona_and_complexity():
    with patch("app_stream._load_parent_config_for_stream") as mock_load:
        mock_load.return_value = {
            "student_profile": {"name": "Leo", "age": 16},
            "cognitive_metrics": {"current_conversational_level": 3},
        }
        prompt = app_stream.build_shared_system_prompt(sandbox_mode=False)
    assert "Alex" in prompt
    assert "CONVERSATIONAL COMPLEXITY LEVEL" in prompt
    assert "CONVERSATIONAL COMPLEXITY LEVEL: 3 of 5" in prompt


# ── §3.3 + §3.4: Claude path uses the shared prompt, correct headers, no thinking ──

def test_claude_path_uses_shared_persona_and_correct_headers(monkeypatch):
    _no_disk(monkeypatch)
    monkeypatch.setattr(app_stream._model_router, "determine_optimal_model",
                        lambda *a, **kw: "claude-sonnet-4-6")
    captured = {}

    def fake_post(url, json=None, headers=None, stream=None, timeout=None):
        if "api.anthropic.com" in url:
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = json
            return FakeResponse(200, lines=[
                "event: content_block_delta",
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Yo Leo!"}}',
                'data: {"type":"message_stop"}',
            ])
        raise AssertionError("Gemini must not be called when Claude succeeds")

    monkeypatch.setattr(app_stream.requests, "post", fake_post)

    chunks = list(app_stream.stream_chat("Solve 2x + 5 = 15 for x"))
    text = "".join(c.get("text", "") for c in chunks)

    assert "Yo Leo!" in text
    assert not [c for c in chunks if "error" in c]
    # Same shared prompt reaches Claude (Alex persona + §3.4 complexity directive).
    assert "Alex" in captured["body"]["system"]
    assert "CONVERSATIONAL COMPLEXITY LEVEL: 4 of 5" in captured["body"]["system"]
    # Required SSE headers; key sourced via get_secret (env-backed).
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["headers"]["x-api-key"] == "fake-key"
    # 4.6+ adaptive thinking: no budget_tokens / thinking / sampling params sent.
    assert "thinking" not in captured["body"]
    assert "budget_tokens" not in captured["body"]
    assert "temperature" not in captured["body"]
    assert captured["body"]["stream"] is True
    assert captured["body"]["model"] == "claude-sonnet-4-6"


# ── §3 #4: a Claude outage falls back to the conversational (Gemini) path ─────

def test_stream_chat_falls_back_to_gemini_on_claude_error(monkeypatch):
    _no_disk(monkeypatch)
    monkeypatch.setattr(app_stream._model_router, "determine_optimal_model",
                        lambda *a, **kw: "claude-sonnet-4-6")

    def fake_post(url, json=None, headers=None, stream=None, timeout=None):
        if "api.anthropic.com" in url:
            # Simulate a Claude outage (overloaded) before any text streams.
            return FakeResponse(529, text="overloaded")
        if "generativelanguage" in url:
            return FakeResponse(200, lines=[
                'data: {"candidates": [{"content": {"parts": [{"text": "Hello from Alex on Gemini!"}]}}]}',
            ])
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(app_stream.requests, "post", fake_post)

    chunks = list(app_stream.stream_chat("Solve 2x + 5 = 15 for x"))
    text = "".join(c.get("text", "") for c in chunks)

    # No unhandled error, and Alex still answers via the conversational path.
    assert not [c for c in chunks if "error" in c], chunks
    assert "Claude unavailable" in text          # graceful fallback notice
    assert "Hello from Alex on Gemini!" in text  # conversational path responded


def test_stream_anthropic_raises_on_non_200_before_yield(monkeypatch):
    monkeypatch.setattr(app_stream.requests, "post",
                        lambda *a, **kw: FakeResponse(401, text="bad key"))
    gen = app_stream.stream_anthropic("hi", "sys", [], "claude-sonnet-4-6", "k")
    try:
        next(gen)
        assert False, "expected RuntimeError before any text is yielded"
    except RuntimeError as e:
        assert "401" in str(e)
