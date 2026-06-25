"""
Unit tests for Prompt 8 (v3) — Bedtime wind-down.

Core principle under test: near bedtime Alex gets CALMER and QUIETER, never
bossier and never refusing. Everything uses a mocked `now`; nothing hits the
network. The stale on-disk sandbox flag is forced OFF so bedtime logic runs (one
test re-enables it to prove the bypass).

Run:  python -m pytest test_bedtime_suppression.py -v
"""

import os
from datetime import datetime

import pytest

os.environ["RESONANCE_TEST_MODE"] = "true"

import app_stream as a
import engagement_engine as ee


@pytest.fixture(autouse=True)
def _force_sandbox_off(monkeypatch):
    monkeypatch.setattr(a, "_is_sandbox_mode", lambda: False)


def _bt_config(**bt):
    bedtime = {
        "scheduled_time": "21:30",
        "parent_hard_cap": "22:00",
        "wind_down_minutes": 30,
        "child_stated_time": None,
        "last_asked_iso": None,
        "wind_down_heads_up_iso": None,
    }
    bedtime.update(bt)
    return {"bedtime": bedtime}


def _eng_bedtime_config(**bt):
    cfg = _bt_config(**bt)
    cfg["engagement"] = {
        "enabled": True,
        "max_initiations_per_hour": 5,
        "max_initiations_per_day": 9,
        "cooldown_after_decline_minutes": 30,
        "silence_is_decline_after_minutes": 4,
        "state": "idle",
        "cooldown_until_iso": None,
        "initiations": [],
    }
    return cfg


# ── §2: status across boundaries ─────────────────────────────────────────────
@pytest.mark.parametrize("h,m,expected", [
    (19, 0, "normal"),
    (20, 59, "normal"),
    (21, 0, "wind_down"),     # wind_down_start = 21:30 - 30m
    (21, 29, "wind_down"),
    (21, 30, "past_bedtime"), # at scheduled bedtime
    (21, 45, "past_bedtime"),
    (22, 15, "past_bedtime"), # beyond hard cap — still the same gentle state
    (6, 0, "normal"),         # morning, back to normal
])
def test_status_across_boundaries(h, m, expected):
    assert a.get_bedtime_status(_bt_config(), datetime(2026, 6, 24, h, m)) == expected


def test_midnight_wrap_reads_as_past_bedtime():
    # REQUIRED: 00:30 against a 21:30 bedtime is PAST bedtime, not "normal".
    assert a.get_bedtime_status(_bt_config(), datetime(2026, 6, 25, 0, 30)) == "past_bedtime"
    assert a.get_bedtime_status(_bt_config(), datetime(2026, 6, 25, 4, 30)) == "past_bedtime"


def test_child_stated_time_clamped_to_parent_hard_cap():
    # Child says 23:00; cap is 22:00 -> active bedtime is 22:00, so 22:30 is past.
    cfg = _bt_config(child_stated_time="23:00")
    assert a.get_bedtime_status(cfg, datetime(2026, 6, 24, 22, 30)) == "past_bedtime"
    # And an earlier-than-scheduled stated time pulls wind-down earlier.
    cfg2 = _bt_config(child_stated_time="21:00")
    assert a.get_bedtime_status(cfg2, datetime(2026, 6, 24, 20, 45)) == "wind_down"


# ── §4: forgiving stated-time parsing ────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("11 pm", "22:00"),       # 23:00 clamped to hard cap 22:00
    ("930", "09:30"),         # digit logic: 9 and 30
    ("9:45", "09:45"),
    ("10:30 PM", "22:00"),    # 22:30 clamped to 22:00
    ("half 9", "09:30"),      # British idiom
    ("ten", "10:00"),         # word number
    ("10", "10:00"),
])
def test_parse_stated_bedtime_formats(text, expected):
    assert a.parse_stated_bedtime(text, a._hhmm_to_minutes("22:00")) == expected


@pytest.mark.parametrize("text", ["dunno", "🌙", "", "no idea lol", None])
def test_parse_stated_bedtime_garbage_returns_none(text):
    assert a.parse_stated_bedtime(text, a._hhmm_to_minutes("22:00")) is None


def test_garbage_answer_does_not_write_bad_stated_time():
    now = datetime(2026, 6, 24, 21, 15)
    cfg = _bt_config(last_asked_iso=now.isoformat())  # already asked this evening
    out, changed = a.apply_bedtime_to_prompt("BASE", cfg, now=now, user_reply="dunno 🤷")
    assert cfg["bedtime"]["child_stated_time"] is None  # no bad value persisted
    # Falls back to the scheduled parent value, so status is unaffected.
    assert a.get_bedtime_status(cfg, now) == "wind_down"


def test_good_answer_captured_and_clamped():
    now = datetime(2026, 6, 24, 21, 15)
    cfg = _bt_config(last_asked_iso=now.isoformat())
    out, changed = a.apply_bedtime_to_prompt("BASE", cfg, now=now, user_reply="11 pm")
    assert cfg["bedtime"]["child_stated_time"] == "22:00"
    assert changed is True


def test_triggering_message_not_captured_before_asking():
    # On the turn we first ask, a stray number in Leo's message must NOT be grabbed.
    now = datetime(2026, 6, 24, 21, 15)
    cfg = _bt_config()  # not asked yet this evening
    a.apply_bedtime_to_prompt("BASE", cfg, now=now, user_reply="I scored 10 goals today!")
    assert cfg["bedtime"]["child_stated_time"] is None


# ── §3: past_bedtime stays himself, never refuses or bosses ───────────────────
def test_past_bedtime_injects_sleepy_tone_without_refusing():
    base = "BASE_PERSONA_PROMPT"
    now = datetime(2026, 6, 24, 23, 0)
    out, changed = a.apply_bedtime_to_prompt(base, _bt_config(), now=now, user_reply="yo what's 2+2")
    # Additive only — it never replaces the prompt or returns a refusal/block.
    assert out.startswith(base)
    assert a.PAST_BEDTIME_TONE_DIRECTIVE in out
    # The injected tone carries NO bossy/command string (it forbids commands, it
    # doesn't issue them) — so the soft drift detector finds nothing.
    injected = out[len(base):]
    assert a.detect_bossy_tone(injected) == []


def test_wind_down_asks_at_most_once_per_day():
    now = datetime(2026, 6, 24, 21, 15)
    cfg = _bt_config()
    out1, _ = a.apply_bedtime_to_prompt("BASE", cfg, now=now, user_reply=None)
    assert a.WIND_DOWN_ASK_DIRECTIVE in out1
    assert cfg["bedtime"]["last_asked_iso"] is not None

    later = datetime(2026, 6, 24, 21, 25)
    out2, _ = a.apply_bedtime_to_prompt("BASE", cfg, now=later, user_reply=None)
    assert a.WIND_DOWN_ASK_DIRECTIVE not in out2   # asked already this evening
    assert a.WIND_DOWN_TONE_DIRECTIVE in out2      # but the calmer tone still applies


def test_past_bedtime_goodnight_nudge_at_most_once_per_evening():
    cfg = _bt_config()
    n1 = datetime(2026, 6, 24, 23, 0)
    out1, _ = a.apply_bedtime_to_prompt("BASE", cfg, now=n1, user_reply=None)
    assert a.PAST_BEDTIME_GOODNIGHT_DIRECTIVE in out1
    # Same evening, just after midnight -> no second goodnight nudge.
    n2 = datetime(2026, 6, 25, 0, 30)
    out2, _ = a.apply_bedtime_to_prompt("BASE", cfg, now=n2, user_reply=None)
    assert a.PAST_BEDTIME_GOODNIGHT_DIRECTIVE not in out2
    assert a.PAST_BEDTIME_TONE_DIRECTIVE in out2


# ── §5: proactive initiations suppressed near bedtime ────────────────────────
def test_proactive_blocked_during_wind_down():
    cfg = _eng_bedtime_config()
    allowed, reason = ee.check_gates(cfg, now=datetime(2026, 6, 24, 21, 15))
    assert (allowed, reason) == (False, "wind_down_window")


def test_proactive_blocked_past_bedtime():
    cfg = _eng_bedtime_config()
    allowed, reason = ee.check_gates(cfg, now=datetime(2026, 6, 24, 23, 0))
    assert (allowed, reason) == (False, "wind_down_window")


def test_proactive_allowed_when_normal():
    cfg = _eng_bedtime_config()
    allowed, reason = ee.check_gates(cfg, now=datetime(2026, 6, 24, 19, 0))
    assert (allowed, reason) == (True, "clear")


# ── persona layering + sandbox bypass ────────────────────────────────────────
def test_friend_not_boss_clause_present_with_wind_down_directive(monkeypatch):
    monkeypatch.setattr(a, "_load_profile_hints", lambda: {"hints": []})
    monkeypatch.setattr(
        a, "_load_parent_config_for_stream",
        lambda: {"cognitive_metrics": {"current_conversational_level": 1},
                 "report_intelligence": {"enabled": False}},
    )
    base = a.build_shared_system_prompt()
    out, _ = a.apply_bedtime_to_prompt(base, _bt_config(), now=datetime(2026, 6, 24, 21, 15), user_reply=None)
    # The wind-down directive layers ON TOP — it never replaces the persona.
    assert a.FRIEND_NOT_BOSS_PERSONA in out
    assert a.WIND_DOWN_TONE_DIRECTIVE in out


def test_sandbox_bypasses_all_bedtime_logic(monkeypatch):
    monkeypatch.setattr(a, "_is_sandbox_mode", lambda: True)
    cfg = _bt_config()
    assert a.get_bedtime_status(cfg, datetime(2026, 6, 24, 21, 15)) == "normal"
    out, changed = a.apply_bedtime_to_prompt("BASE", cfg, now=datetime(2026, 6, 24, 23, 0), user_reply="11 pm")
    assert out == "BASE"
    assert changed is False
    assert cfg["bedtime"]["child_stated_time"] is None
