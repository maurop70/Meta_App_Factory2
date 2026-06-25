"""
Unit tests for Prompt 3.5 (v2) — Core Persona & Soft Drift Detector.

Verifies that the friend-not-boss persona clause is present GLOBALLY (every
complexity level and mode) and that detect_bossy_tone flags nagging/bossy lines
while letting enthusiastic friendly lines pass cleanly.

Run:  python -m pytest test_persona_drift.py -v
"""

import pytest

import app_stream


# ── Persona builder: clause is global ────────────────────────────────────────
@pytest.fixture
def _isolated_builder(monkeypatch):
    """Stub the disk/engine reads so build_shared_system_prompt is deterministic.

    Leaves complexity level controllable via the returned parent config.
    """
    monkeypatch.setattr(app_stream, "_load_profile_hints", lambda: {"hints": []})

    def _set_level(level):
        # No student_profile / disabled report intel -> council & clinical skipped.
        monkeypatch.setattr(
            app_stream, "_load_parent_config_for_stream",
            lambda: {
                "cognitive_metrics": {"current_conversational_level": level},
                "report_intelligence": {"enabled": False},
            },
        )
    return _set_level


def test_persona_clause_present_at_complexity_level_1(_isolated_builder):
    _isolated_builder(1)
    prompt = app_stream.build_shared_system_prompt()
    assert app_stream.FRIEND_NOT_BOSS_PERSONA in prompt
    assert "CONVERSATIONAL COMPLEXITY LEVEL: 1 of 5" in prompt
    # Spot-check verbatim wording survived.
    assert "not his parent, teacher, boss, or babysitter" in prompt
    assert "by pull, never push" in prompt


def test_persona_clause_present_at_complexity_level_5(_isolated_builder):
    _isolated_builder(5)
    prompt = app_stream.build_shared_system_prompt()
    assert app_stream.FRIEND_NOT_BOSS_PERSONA in prompt
    assert "CONVERSATIONAL COMPLEXITY LEVEL: 5 of 5" in prompt
    assert "he never makes you feel managed" in prompt


def test_persona_clause_present_when_wind_down_mode_active(_isolated_builder):
    _isolated_builder(2)
    # Simulate a wind-down mode being active via the live-state channel.
    prompt = app_stream.build_shared_system_prompt(
        dashboard_context={"mode": "wind_down", "minutes_to_bedtime": 10}
    )
    assert app_stream.FRIEND_NOT_BOSS_PERSONA in prompt
    # The clause's bedtime guidance is pull-not-push (calmer/quieter, no orders).
    assert "near bedtime, you get calmer and quieter" in prompt


def test_persona_clause_present_in_sandbox_mode(_isolated_builder):
    _isolated_builder(3)
    prompt = app_stream.build_shared_system_prompt(sandbox_mode=True)
    assert app_stream.FRIEND_NOT_BOSS_PERSONA in prompt


# ── Soft drift detector: flags bossy/nagging ─────────────────────────────────
@pytest.mark.parametrize("line", [
    "Leo, go to sleep",
    "get off your phone",
    "you need to stop now",
    "it's time to turn it off",
    "turn the screen off",
    "stop playing that game",
    "hurry up",
    "that's enough",
    "you have to go to bed",
    "you should put your controller down",
])
def test_detect_bossy_tone_flags_nagging(line):
    warnings = app_stream.detect_bossy_tone(line)
    assert warnings, f"expected a warning for bossy line: {line!r}"


# ── Soft drift detector: passes friendly/enthusiastic lines ──────────────────
@pytest.mark.parametrize("line", [
    "you should totally see this redstone trick",
    "guess what I found out about dinosaurs",
    "all good, I'm here whenever",
    "you should put more effort into that awesome drawing",
    "I really want to hear how your tennis match went",
    "",
])
def test_detect_bossy_tone_passes_friendly(line):
    assert app_stream.detect_bossy_tone(line) == []


def test_detect_bossy_tone_returns_specific_phrases():
    warnings = app_stream.detect_bossy_tone("Leo, go to sleep — that's enough for tonight.")
    assert "go to sleep" in warnings
    assert "that's enough" in warnings
