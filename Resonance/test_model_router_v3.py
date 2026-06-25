"""Unit tests for model_router_v3: classifier-based routing + configurable model.

The classifier is an external LLM call, so we stub requests.post with a fake
that returns the YES/NO a good classifier would give for each utterance, then
assert the router maps verdicts to models correctly and — critically — that
every ambiguous/failing path defaults to the conversational model.
"""

import json as _json

import pytest

import model_router_v3 as mr


# Plain-chat utterances. Several deliberately contain the things that broke the
# old keyword/symbol routing: hyphens, URLs, dates, and the word "evolution".
CHAT_UTTERANCES = [
    "hey alex whats up today",
    "i went to see project hail mary with the YMCA on 03/23/2026",
    "do you like guitar? i wanna learn a new song",
    "my fav is the drive-through at the fast-food place",   # hyphens
    "check this out youtube.com/watch?v=aB-12_x",            # URL + hyphen
    "we did evolution in biology class but it was boring",   # ambiguous "evolution"
    "i feel kinda down and tired",
]

# Genuine step-by-step reasoning.
MATH_UTTERANCES = [
    "how do i solve 2x + 5 = 15 for x",
    "what is the derivative of x squared",
    "help me balance this chemical equation H2 + O2 -> H2O",
    "if a train goes 60 mph for 3 hours how far does it go",
]


class FakeResp:
    def __init__(self, status_code, verdict=""):
        self.status_code = status_code
        self._verdict = verdict
        self.text = verdict

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": self._verdict}]}}]}


def _make_classifier(reasoning_set):
    """Fake Gemini classifier: YES iff the embedded utterance is a reasoning one."""
    def fake_post(url, json=None, headers=None, timeout=None):
        text = json["contents"][0]["parts"][0]["text"]
        verdict = "YES" if any(u in text for u in reasoning_set) else "NO"
        return FakeResp(200, verdict)
    return fake_post


@pytest.fixture
def router(monkeypatch):
    # Pretend both API keys exist so the classifier path is exercised.
    monkeypatch.setattr(mr.IntelligentModelRouter, "_get_secret",
                        staticmethod(lambda name: "dummy-key"))
    return mr.IntelligentModelRouter()


# ── Routing behaviour ───────────────────────────────────────────────────────

@pytest.mark.parametrize("utterance", CHAT_UTTERANCES)
def test_plain_chat_defaults_to_conversational(router, monkeypatch, utterance):
    monkeypatch.setattr(mr.requests, "post", _make_classifier(MATH_UTTERANCES))
    assert router.determine_optimal_model(utterance) == router.fast_model


@pytest.mark.parametrize("utterance", MATH_UTTERANCES)
def test_genuine_reasoning_routes_to_claude(router, monkeypatch, utterance):
    monkeypatch.setattr(mr.requests, "post", _make_classifier(MATH_UTTERANCES))
    model = router.determine_optimal_model(utterance)
    assert model == router.deep_model
    assert "claude" in model.lower()


def test_no_chat_utterance_ever_routes_to_claude(router, monkeypatch):
    monkeypatch.setattr(mr.requests, "post", _make_classifier(MATH_UTTERANCES))
    routed = {u: router.determine_optimal_model(u) for u in CHAT_UTTERANCES}
    assert all(model == router.fast_model for model in routed.values()), routed


# ── Ambiguity / failure safety defaults (must be conversational) ─────────────

def test_ambiguous_verdict_defaults_to_conversational(router, monkeypatch):
    monkeypatch.setattr(mr.requests, "post",
                        lambda *a, **k: FakeResp(200, "MAYBE"))
    assert router.determine_optimal_model("is the sky blue because reasons") == router.fast_model


def test_non_200_does_not_route_to_claude(router, monkeypatch):
    # The old code routed 400/429 to Claude — that regression must not return.
    monkeypatch.setattr(mr.requests, "post", lambda *a, **k: FakeResp(429))
    assert router.determine_optimal_model("solve 2x + 5 = 15") == router.fast_model


def test_classifier_exception_defaults_to_conversational(router, monkeypatch):
    def boom(*a, **k):
        raise mr.requests.RequestException("network down")
    monkeypatch.setattr(mr.requests, "post", boom)
    assert router.determine_optimal_model("solve 2x + 5 = 15") == router.fast_model


def test_short_prompt_skips_classifier(router, monkeypatch):
    def fail(*a, **k):
        raise AssertionError("classifier should not be called for trivial input")
    monkeypatch.setattr(mr.requests, "post", fail)
    assert router.determine_optimal_model("ok") == router.fast_model


def test_missing_anthropic_key_stays_conversational(monkeypatch):
    # Gemini available but no Anthropic key -> never route to Claude.
    monkeypatch.setattr(mr.IntelligentModelRouter, "_get_secret",
                        staticmethod(lambda name: "gk" if name == "GEMINI_API_KEY" else ""))
    def fail(*a, **k):
        raise AssertionError("classifier should not run without an Anthropic key")
    monkeypatch.setattr(mr.requests, "post", fail)
    r = mr.IntelligentModelRouter()
    assert r.determine_optimal_model("solve 2x + 5 = 15") == r.fast_model


# ── Configurable Claude model (§3.2) ─────────────────────────────────────────

def test_default_claude_model_is_sonnet_4_6(monkeypatch):
    monkeypatch.delenv("RESONANCE_CLAUDE_MODEL", raising=False)
    monkeypatch.setattr(mr, "CONFIG_PATH", "this_path_does_not_exist.json")
    assert mr.IntelligentModelRouter().deep_model == "claude-sonnet-4-6"


def test_default_has_no_dated_2024_snapshot(monkeypatch):
    monkeypatch.delenv("RESONANCE_CLAUDE_MODEL", raising=False)
    monkeypatch.setattr(mr, "CONFIG_PATH", "this_path_does_not_exist.json")
    model = mr.IntelligentModelRouter().deep_model
    assert "2024" not in model and "3-5" not in model


def test_env_overrides_claude_model(monkeypatch):
    monkeypatch.setenv("RESONANCE_CLAUDE_MODEL", "claude-opus-4-8")
    assert mr.IntelligentModelRouter().deep_model == "claude-opus-4-8"


def test_config_json_fallback_for_claude_model(tmp_path, monkeypatch):
    monkeypatch.delenv("RESONANCE_CLAUDE_MODEL", raising=False)
    cfg = tmp_path / "config.json"
    cfg.write_text(_json.dumps({"claude_model": "claude-haiku-4-5-20251001"}), encoding="utf-8")
    monkeypatch.setattr(mr, "CONFIG_PATH", str(cfg))
    assert mr.IntelligentModelRouter().deep_model == "claude-haiku-4-5-20251001"
