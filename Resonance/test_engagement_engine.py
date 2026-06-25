"""
Unit tests for engagement_engine (Plan v2 §5.1 / §5.2).

The LLM is always mocked — these tests never touch the network. They verify:
  - opener generation produces non-empty, phone-free text;
  - the gate logic blocks correctly, in order;
  - a full trigger records the initiation and advances the state machine;
  - the opener STYLE rotates across initiations;
  - a phone-mentioning opener that slips the prompt is discarded, not cast.

Run:  python -m pytest test_engagement_engine.py -v
"""

import os
from datetime import datetime, timedelta

import pytest

# Keep speak_to_room from ever scanning mDNS / casting during these tests.
os.environ["RESONANCE_TEST_MODE"] = "true"

import engagement_engine as ee


@pytest.fixture(autouse=True)
def _no_sandbox(monkeypatch):
    """Force sandbox OFF so a stale on-disk sandbox flag can't suppress triggers."""
    monkeypatch.setattr(ee, "_is_sandbox_mode", lambda: False)


# ── Fixtures / helpers ───────────────────────────────────────────────────────
def _base_config(**eng_overrides):
    eng = {
        "enabled": True,
        "max_initiations_per_hour": 2,
        "max_initiations_per_day": 6,
        "cooldown_after_decline_minutes": 30,
        "silence_is_decline_after_minutes": 4,
        "state": "idle",
        "cooldown_until_iso": None,
        "initiations": [],
    }
    eng.update(eng_overrides)
    return {
        "engagement": eng,
        "interest_store": {
            "topics": ["antenna towers", "guitar", "fast-food drive-throughs"],
            "recent_callbacks": ["that gnarly riff you were learning"],
            "last_updated_iso": None,
        },
    }


def _initiations_at(times):
    return [{"timestamp": t.isoformat(), "style": "cool_fact", "opener": "hi"} for t in times]


# ── §5.2 opener generation ───────────────────────────────────────────────────
def test_opener_is_non_empty_and_phone_free(monkeypatch):
    monkeypatch.setattr(
        ee, "_invoke_llm",
        lambda user_prompt, system_prompt: "Yo, you ever wonder how those antenna towers don't just topple over?",
    )
    text = ee.generate_opener(
        "curious_question",
        ["antenna towers", "guitar"],
        "that riff you were learning",
        system_prompt="(stub persona)",
    )
    assert text  # non-empty
    assert ee.is_phone_free(text)


def test_opener_strips_wrapping_quotes(monkeypatch):
    monkeypatch.setattr(ee, "_invoke_llm", lambda u, s: '"Bet you can\'t name three exit signs in the YMCA."')
    text = ee.generate_opener("joke_or_dare", ["exit signs"], None, system_prompt="x")
    assert not text.startswith('"') and not text.endswith('"')
    assert text


def test_opener_with_phone_language_is_discarded(monkeypatch):
    # Even if the model slips and mentions a phone, the engine must not cast it.
    monkeypatch.setattr(ee, "_invoke_llm", lambda u, s: "Hey, maybe put the phone down and grab your guitar?")
    text = ee.generate_opener("i_was_thinking", ["guitar"], None, system_prompt="x")
    assert text == ""


def test_opener_empty_generation_returns_empty(monkeypatch):
    monkeypatch.setattr(ee, "_invoke_llm", lambda u, s: "   ")
    assert ee.generate_opener("cool_fact", ["guitar"], None, system_prompt="x") == ""


def test_is_phone_free_catches_variants():
    assert ee.is_phone_free("Let's jam on the guitar tonight!")
    assert not ee.is_phone_free("Too much screen time today")
    assert not ee.is_phone_free("Get off your tablet")  # 'get off your'
    assert not ee.is_phone_free("stop scrolling")


# ── §5.1 gate logic ──────────────────────────────────────────────────────────
def test_gate_clear_when_idle_and_enabled():
    allowed, reason = ee.check_gates(_base_config())
    assert allowed is True
    assert reason == "clear"


def test_gate_blocks_when_disabled():
    allowed, reason = ee.check_gates(_base_config(enabled=False))
    assert allowed is False
    assert reason == "engagement_disabled"


def test_gate_blocks_during_cooldown():
    now = datetime(2026, 6, 24, 20, 0, 0)
    cfg = _base_config(cooldown_until_iso=(now + timedelta(minutes=10)).isoformat())
    allowed, reason = ee.check_gates(cfg, now=now)
    assert allowed is False
    assert reason == "in_cooldown"


def test_gate_passes_when_cooldown_expired():
    now = datetime(2026, 6, 24, 20, 0, 0)
    cfg = _base_config(cooldown_until_iso=(now - timedelta(minutes=1)).isoformat())
    allowed, reason = ee.check_gates(cfg, now=now)
    assert allowed is True


def test_gate_blocks_over_per_hour_limit():
    now = datetime(2026, 6, 24, 20, 0, 0)
    recent = [now - timedelta(minutes=5), now - timedelta(minutes=20)]  # 2 in last hour
    cfg = _base_config(max_initiations_per_hour=2, initiations=_initiations_at(recent))
    allowed, reason = ee.check_gates(cfg, now=now)
    assert allowed is False
    assert reason == "max_per_hour_reached"


def test_gate_blocks_over_per_day_limit():
    now = datetime(2026, 6, 24, 20, 0, 0)
    # 6 spread across the last day but >1h apart so the hourly gate stays open.
    times = [now - timedelta(hours=h) for h in (2, 4, 6, 8, 10, 12)]
    cfg = _base_config(max_initiations_per_day=6, initiations=_initiations_at(times))
    allowed, reason = ee.check_gates(cfg, now=now)
    assert allowed is False
    assert reason == "max_per_day_reached"


def test_gate_order_enabled_checked_before_cooldown():
    # Disabled AND in cooldown -> the FIRST failing gate (disabled) wins.
    now = datetime(2026, 6, 24, 20, 0, 0)
    cfg = _base_config(enabled=False, cooldown_until_iso=(now + timedelta(minutes=10)).isoformat())
    allowed, reason = ee.check_gates(cfg, now=now)
    assert (allowed, reason) == (False, "engagement_disabled")


# ── style rotation ───────────────────────────────────────────────────────────
def test_style_rotates_through_all_then_cycles():
    seen = [ee.select_opener_style(i) for i in range(len(ee.OPENER_STYLES))]
    assert seen == ee.OPENER_STYLES
    # Wraps around.
    assert ee.select_opener_style(len(ee.OPENER_STYLES)) == ee.OPENER_STYLES[0]


# ── full trigger (§5.1 end-to-end, in-memory config) ─────────────────────────
def test_trigger_records_initiation_and_sets_awaiting_response(monkeypatch):
    monkeypatch.setattr(ee, "_invoke_llm", lambda u, s: "Yo, you crack that new guitar riff yet?")
    monkeypatch.setattr(ee, "_build_system_prompt", lambda: "(stub persona)")
    cfg = _base_config()

    result = ee.trigger_engagement(config=cfg, save=False, test_mode=True)

    assert result["triggered"] is True
    assert result["style"] == "curious_question"  # first initiation
    assert ee.is_phone_free(result["opener"])
    assert cfg["engagement"]["state"] == "awaiting_response"
    assert len(cfg["engagement"]["initiations"]) == 1
    rec = cfg["engagement"]["initiations"][0]
    assert rec["style"] == "curious_question"
    assert rec["opener"] == result["opener"]


def test_trigger_blocked_gate_does_nothing(monkeypatch):
    called = {"llm": False}

    def _fail(*a, **k):
        called["llm"] = True
        return "should not be called"

    monkeypatch.setattr(ee, "_invoke_llm", _fail)
    cfg = _base_config(enabled=False)

    result = ee.trigger_engagement(config=cfg, save=False, test_mode=True)

    assert result == {"triggered": False, "reason": "engagement_disabled"}
    assert called["llm"] is False  # gate short-circuits before any generation
    assert cfg["engagement"]["state"] == "idle"
    assert cfg["engagement"]["initiations"] == []


def test_trigger_aborts_when_opener_unusable(monkeypatch):
    monkeypatch.setattr(ee, "_invoke_llm", lambda u, s: "put the phone down dude")
    monkeypatch.setattr(ee, "_build_system_prompt", lambda: "(stub persona)")
    cfg = _base_config()

    result = ee.trigger_engagement(config=cfg, save=False, test_mode=True)

    assert result["triggered"] is False
    assert result["reason"] == "opener_generation_failed"
    assert cfg["engagement"]["state"] == "idle"
    assert cfg["engagement"]["initiations"] == []


def test_consecutive_triggers_rotate_style(monkeypatch):
    monkeypatch.setattr(ee, "_invoke_llm", lambda u, s: "Yo, quick one — guitar or tennis today?")
    monkeypatch.setattr(ee, "_build_system_prompt", lambda: "(stub persona)")
    # High limits so the rate gates don't interfere.
    cfg = _base_config(max_initiations_per_hour=99, max_initiations_per_day=99)

    styles = []
    for _ in range(len(ee.OPENER_STYLES) + 1):
        res = ee.trigger_engagement(config=cfg, save=False, test_mode=True)
        assert res["triggered"] is True
        styles.append(res["style"])

    assert styles[: len(ee.OPENER_STYLES)] == ee.OPENER_STYLES
    assert styles[len(ee.OPENER_STYLES)] == ee.OPENER_STYLES[0]  # cycles
