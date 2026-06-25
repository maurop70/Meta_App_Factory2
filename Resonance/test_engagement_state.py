"""
Unit tests for engagement_engine §5.3 / §5.4 (Phase 4b restraint).

These exercise the state machine and hard caps DIRECTLY — they are the behaviours
most likely to regress. Every test uses a mocked ``now`` and a mocked LLM; nothing
here touches the network or a real model.

Run:  python -m pytest test_engagement_state.py -v
"""

import os
from datetime import datetime, timedelta

import pytest

# Keep speak_to_room from ever scanning mDNS / casting; secure the server endpoint.
os.environ["RESONANCE_TEST_MODE"] = "true"
os.environ.setdefault("RESONANCE_TOKEN", "test-secret-token")

import engagement_engine as ee


# ── Autouse: deterministic, network-free engine ──────────────────────────────
@pytest.fixture(autouse=True)
def _stub_engine(monkeypatch):
    # Never proactively skip via a stale on-disk sandbox flag.
    monkeypatch.setattr(ee, "_is_sandbox_mode", lambda: False)
    # Pin the wind-down gate OFF so caps/cooldown tests stay wall-clock independent.
    monkeypatch.setattr(ee, "is_in_wind_down_window", lambda *a, **k: False)
    # Any opener / decline-line generation returns a safe, phone-free line.
    monkeypatch.setattr(ee, "_invoke_llm", lambda u, s=None: "Yo, bet you can't out-jam me today!")
    monkeypatch.setattr(ee, "_build_system_prompt", lambda: "(stub persona)")


NOW = datetime(2026, 6, 24, 20, 0, 0)


def _awaiting_config(opener_time, *, post_cooldown_light=False, **eng_overrides):
    eng = {
        "enabled": True,
        "max_initiations_per_hour": 2,
        "max_initiations_per_day": 6,
        "cooldown_after_decline_minutes": 30,
        "silence_is_decline_after_minutes": 4,
        "state": ee.STATE_AWAITING,
        "cooldown_until_iso": None,
        "initiations": [{
            "timestamp": opener_time.isoformat(),
            "trigger_reason": "screen_time_hook",
            "style": "cool_fact",
            "opener": "yo check this out",
            "outcome": ee.OUTCOME_PENDING,
            "post_cooldown_light": post_cooldown_light,
        }],
    }
    eng.update(eng_overrides)
    return {"engagement": eng, "interest_store": {"topics": ["guitar"], "recent_callbacks": []}}


def _idle_config(initiations=None, **eng_overrides):
    eng = {
        "enabled": True,
        "max_initiations_per_hour": 2,
        "max_initiations_per_day": 6,
        "cooldown_after_decline_minutes": 30,
        "silence_is_decline_after_minutes": 4,
        "state": ee.STATE_IDLE,
        "cooldown_until_iso": None,
        "initiations": initiations or [],
    }
    eng.update(eng_overrides)
    return {"engagement": eng, "interest_store": {"topics": ["guitar"], "recent_callbacks": []}}


def _initiations_at(times):
    return [{"timestamp": t.isoformat(), "style": "cool_fact", "opener": "hi",
             "outcome": ee.OUTCOME_ENGAGED} for t in times]


# ── State transitions (§5.3) ─────────────────────────────────────────────────
def test_silence_past_threshold_declines_silently():
    cfg = _awaiting_config(NOW - timedelta(minutes=5))  # 5 > 4 min threshold
    res = ee.check_and_update_state(reply=None, now=NOW, config=cfg, save=False)

    assert res["transition"] == "declined"
    assert res["outcome"] == ee.OUTCOME_SILENT
    assert res["decline_line"] is None  # no one's listening — go quiet
    eng = cfg["engagement"]
    assert eng["state"] == ee.STATE_COOLDOWN
    assert eng["initiations"][-1]["outcome"] == ee.OUTCOME_SILENT
    assert eng["cooldown_until_iso"] == (NOW + timedelta(minutes=30)).isoformat()


def test_silence_within_window_stays_awaiting():
    cfg = _awaiting_config(NOW - timedelta(minutes=2))  # 2 < 4
    res = ee.check_and_update_state(reply=None, now=NOW, config=cfg, save=False)
    assert res["changed"] is False
    assert cfg["engagement"]["state"] == ee.STATE_AWAITING


def test_disinterested_reply_declines_not_engages():
    # KEY REGRESSION: a reply within the timeout must NOT auto-mean "engaged".
    cfg = _awaiting_config(NOW - timedelta(minutes=1))
    res = ee.check_and_update_state(reply="not now", now=NOW, config=cfg, save=False)

    assert res["transition"] == "declined"
    assert res["outcome"] == ee.OUTCOME_DECLINED
    assert res["decline_line"]  # Alex says one warm line on explicit disinterest
    assert ee.is_phone_free(res["decline_line"])
    eng = cfg["engagement"]
    assert eng["state"] == ee.STATE_COOLDOWN
    assert eng["initiations"][-1]["outcome"] == ee.OUTCOME_DECLINED


def test_interested_reply_engages():
    cfg = _awaiting_config(NOW - timedelta(minutes=1))
    res = ee.check_and_update_state(reply="yeah totally, tell me more!", now=NOW, config=cfg, save=False)

    assert res["transition"] == "engaged"
    assert res["outcome"] == ee.OUTCOME_ENGAGED
    assert res["decline_line"] is None
    assert cfg["engagement"]["state"] == ee.STATE_ENGAGED
    assert cfg["engagement"]["initiations"][-1]["outcome"] == ee.OUTCOME_ENGAGED


def test_decline_sets_cooldown_until_correctly():
    cfg = _awaiting_config(NOW - timedelta(minutes=1), cooldown_after_decline_minutes=45)
    ee.check_and_update_state(reply="no", now=NOW, config=cfg, save=False)
    assert cfg["engagement"]["cooldown_until_iso"] == (NOW + timedelta(minutes=45)).isoformat()
    assert cfg["engagement"]["state"] == ee.STATE_COOLDOWN


def test_late_reply_after_timeout_treated_as_silence():
    # Timeout check runs FIRST: a reply arriving after the window is still a no.
    cfg = _awaiting_config(NOW - timedelta(minutes=6))
    res = ee.check_and_update_state(reply="yeah sure!", now=NOW, config=cfg, save=False)
    assert res["outcome"] == ee.OUTCOME_SILENT
    assert res["decline_line"] is None


def test_no_op_when_not_awaiting():
    cfg = _idle_config()
    res = ee.check_and_update_state(reply="hello", now=NOW, config=cfg, save=False)
    assert res["changed"] is False
    assert res["transition"] is None


# ── Disinterest classifier uses the LLM only when ambiguous ──────────────────
def test_ambiguous_reply_uses_mocked_llm_disinterested(monkeypatch):
    monkeypatch.setattr(ee, "_llm_interest_read", lambda reply, sp=None: "disinterested")
    cfg = _awaiting_config(NOW - timedelta(minutes=1))
    res = ee.check_and_update_state(reply="i dunno about that one", now=NOW, config=cfg, save=False)
    assert res["transition"] == "declined"
    assert res["outcome"] == ee.OUTCOME_DECLINED


def test_ambiguous_reply_uses_mocked_llm_interested(monkeypatch):
    monkeypatch.setattr(ee, "_llm_interest_read", lambda reply, sp=None: "interested")
    cfg = _awaiting_config(NOW - timedelta(minutes=1))
    res = ee.check_and_update_state(reply="i dunno about that one", now=NOW, config=cfg, save=False)
    assert res["transition"] == "engaged"


# ── Hard caps (§5.3) — the load-bearing guardrail ────────────────────────────
def test_over_per_hour_cap_suppresses_initiation():
    recent = [NOW - timedelta(minutes=5), NOW - timedelta(minutes=20)]  # 2 in last hour
    cfg = _idle_config(initiations=_initiations_at(recent), max_initiations_per_hour=2)
    res = ee.trigger_engagement(now=NOW, config=cfg, save=False, test_mode=True)
    assert res["triggered"] is False
    assert res["reason"] == "max_per_hour_reached"


def test_over_per_day_cap_suppresses_initiation():
    # 6 today, spread >1h apart so the hourly gate stays open.
    times = [NOW - timedelta(hours=h) for h in (2, 4, 6, 8, 10, 12)]
    cfg = _idle_config(initiations=_initiations_at(times), max_initiations_per_day=6)
    res = ee.trigger_engagement(now=NOW, config=cfg, save=False, test_mode=True)
    assert res["triggered"] is False
    assert res["reason"] == "max_per_day_reached"


def test_per_day_counts_local_calendar_day_not_rolling_24h():
    # An initiation 22h ago (NOW=20:00 -> prev day 22:00) is a DIFFERENT local
    # day, yet within a rolling 24h window — so it must NOT count toward today.
    yesterday = [NOW - timedelta(hours=22)]
    cfg = _idle_config(initiations=_initiations_at(yesterday), max_initiations_per_day=1)
    allowed, reason = ee.check_gates(cfg, now=NOW)
    assert allowed is True  # yesterday's initiation doesn't fill today's cap
    assert reason == "clear"


def test_sandbox_mode_suppresses_initiation(monkeypatch):
    monkeypatch.setattr(ee, "_is_sandbox_mode", lambda: True)
    res = ee.trigger_engagement(now=NOW, config=_idle_config(), save=False, test_mode=True)
    assert res["triggered"] is False
    assert res["reason"] == "sandbox_mode"


def test_active_cooldown_blocks_gate():
    cfg = _idle_config(state=ee.STATE_COOLDOWN,
                       cooldown_until_iso=(NOW + timedelta(minutes=10)).isoformat())
    allowed, reason = ee.check_gates(cfg, now=NOW)
    assert (allowed, reason) == (False, "in_cooldown")


# ── Backoff escalation: first post-cooldown approach is lighter ──────────────
def test_first_approach_after_cooldown_is_lighter():
    cfg = _idle_config(state=ee.STATE_COOLDOWN,
                       cooldown_until_iso=(NOW - timedelta(minutes=1)).isoformat())
    res = ee.trigger_engagement(now=NOW, config=cfg, save=False, test_mode=True)
    assert res["triggered"] is True
    assert res["style"] == "joke_or_dare"          # forced light style
    assert res["post_cooldown_light"] is True
    assert cfg["engagement"]["initiations"][-1]["post_cooldown_light"] is True


def test_second_decline_after_cooldown_suspends_session():
    # Cooldown just expired -> lighter re-approach -> ALSO declined -> suspend.
    cfg = _idle_config(state=ee.STATE_COOLDOWN,
                       cooldown_until_iso=(NOW - timedelta(minutes=1)).isoformat())
    res1 = ee.trigger_engagement(now=NOW, config=cfg, save=False, test_mode=True)
    assert res1["triggered"] is True and res1["post_cooldown_light"] is True

    later = NOW + timedelta(minutes=1)
    res2 = ee.check_and_update_state(reply="nope", now=later, config=cfg, save=False)
    assert res2["transition"] == "declined"
    assert res2["suspended"] is True
    assert cfg["engagement"]["proactive_suspended_until_iso"] is not None

    # Gate now refuses any further proactive approach this session.
    allowed, reason = ee.check_gates(cfg, now=later + timedelta(minutes=2))
    assert allowed is False
    assert reason == "proactive_suspended"


# ── Parent visibility (§5.4) ─────────────────────────────────────────────────
def test_initiation_record_has_parent_visible_fields():
    cfg = _idle_config()
    ee.trigger_engagement(now=NOW, config=cfg, save=False, test_mode=True)
    rec = cfg["engagement"]["initiations"][-1]
    for field in ("timestamp", "trigger_reason", "opener", "style", "outcome"):
        assert field in rec
    assert rec["outcome"] == ee.OUTCOME_PENDING  # resolves later


def test_engagement_log_endpoint_requires_token():
    # /api/engagement/log must reject a missing/empty/wrong token with 401.
    try:
        from fastapi.testclient import TestClient
        import server
    except Exception as exc:  # heavy deps unavailable in this env
        pytest.skip(f"server import unavailable: {exc}")

    client = TestClient(server.app)  # no context manager -> no startup side effects

    assert client.get("/api/engagement/log").status_code == 401           # missing
    assert client.get("/api/engagement/log",
                      headers={"X-Resonance-Token": ""}).status_code == 401  # empty
    assert client.get("/api/engagement/log",
                      headers={"X-Resonance-Token": "wrong"}).status_code == 401  # wrong
