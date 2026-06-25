"""Unit tests for resonance_config: load/validate/fallback and atomic save."""

import os
import json
import glob

import pytest

import resonance_config as rc


# ── load_config: happy path & fallbacks ────────────────────────────────────

def test_load_valid_file_returns_merged_config(tmp_path):
    path = tmp_path / "parent_config.json"
    data = {
        "pin": "9999",
        "student_profile": {"name": "Leo", "age": 16},
    }
    path.write_text(json.dumps(data), encoding="utf-8")

    cfg = rc.load_config(str(path))

    assert cfg["pin"] == "9999"
    # Missing sub-keys are deep-merged from defaults.
    assert cfg["student_profile"]["name"] == "Leo"
    assert cfg["student_profile"]["social_level"] == "social"
    # Whole missing sections are filled from defaults.
    assert cfg["bedtime"]["scheduled_time"] == "21:30"
    assert cfg["interest_store"] == {"topics": [], "recent_callbacks": [], "last_updated_iso": None}


def test_load_missing_file_falls_back_to_defaults(tmp_path, caplog):
    path = tmp_path / "does_not_exist.json"
    with caplog.at_level("WARNING"):
        cfg = rc.load_config(str(path))
    assert cfg == rc.default_config()
    assert "not found" in caplog.text.lower()


def test_load_malformed_json_falls_back_and_logs_loudly(tmp_path, caplog):
    path = tmp_path / "parent_config.json"
    path.write_text("{ this is not valid json ", encoding="utf-8")
    with caplog.at_level("ERROR"):
        cfg = rc.load_config(str(path))
    assert cfg == rc.default_config()
    assert any(r.levelname == "ERROR" for r in caplog.records)


def test_load_non_object_top_level_falls_back(tmp_path, caplog):
    path = tmp_path / "parent_config.json"
    path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    with caplog.at_level("ERROR"):
        cfg = rc.load_config(str(path))
    assert cfg == rc.default_config()


def test_load_wrong_typed_section_uses_default_for_that_section(tmp_path, caplog):
    path = tmp_path / "parent_config.json"
    # bedtime should be a dict; give it a string instead.
    data = {"pin": "4321", "bedtime": "oops"}
    path.write_text(json.dumps(data), encoding="utf-8")
    with caplog.at_level("WARNING"):
        cfg = rc.load_config(str(path))
    # Bad section replaced by default; valid sibling preserved.
    assert cfg["bedtime"] == rc.DEFAULT_CONFIG["bedtime"]
    assert cfg["pin"] == "4321"
    assert "bedtime" in caplog.text


def test_load_preserves_unknown_top_level_keys(tmp_path):
    path = tmp_path / "parent_config.json"
    data = {
        "report_intelligence": {"enabled": True, "reports": []},
        "settings": {"council_intensity": "supportive"},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    cfg = rc.load_config(str(path))
    assert cfg["report_intelligence"] == {"enabled": True, "reports": []}
    assert cfg["settings"] == {"council_intensity": "supportive"}


def test_default_config_returns_independent_copies():
    a = rc.default_config()
    a["student_profile"]["name"] = "Mutated"
    b = rc.default_config()
    assert b["student_profile"]["name"] == "Leo"


# ── save_config: atomicity, round-trip, secret stripping ────────────────────

def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "parent_config.json"
    cfg = rc.default_config()
    cfg["pin"] = "0000"
    rc.save_config(cfg, str(path))
    assert json.loads(path.read_text(encoding="utf-8"))["pin"] == "0000"
    assert rc.load_config(str(path))["pin"] == "0000"


def test_save_leaves_no_temp_files_behind(tmp_path):
    path = tmp_path / "parent_config.json"
    rc.save_config(rc.default_config(), str(path))
    leftovers = glob.glob(str(tmp_path / ".parent_config.*.tmp"))
    assert leftovers == []


def test_save_strips_secret_looking_keys(tmp_path, caplog):
    path = tmp_path / "parent_config.json"
    cfg = rc.default_config()
    cfg["GEMINI_API_KEY"] = "should-not-persist"
    cfg["auth_token"] = "nope"
    with caplog.at_level("ERROR"):
        rc.save_config(cfg, str(path))
    written = json.loads(path.read_text(encoding="utf-8"))
    assert "GEMINI_API_KEY" not in written
    assert "auth_token" not in written
    assert written["pin"] == "1234"
    assert "SECURITY" in caplog.text


def test_save_rejects_non_dict():
    with pytest.raises(TypeError):
        rc.save_config(["not", "a", "dict"], "ignored.json")


def test_save_failure_preserves_original_and_cleans_temp(tmp_path):
    path = tmp_path / "parent_config.json"
    # Seed a known-good original.
    original = rc.default_config()
    original["pin"] = "GOOD"
    rc.save_config(original, str(path))

    # A config containing a non-serializable value makes json.dump raise after
    # the temp file is opened but before os.replace runs.
    broken = rc.default_config()
    broken["explode"] = object()
    with pytest.raises(TypeError):
        rc.save_config(broken, str(path))

    # Original file is untouched, and the temp file was cleaned up.
    assert json.loads(path.read_text(encoding="utf-8"))["pin"] == "GOOD"
    assert glob.glob(str(tmp_path / ".parent_config.*.tmp")) == []


def test_repo_parent_config_matches_schema():
    """The checked-in parent_config.json loads and carries every §1 section."""
    cfg = rc.load_config()
    for section in (
        "pin", "instructions", "focus_topics", "vocabulary", "progress_log",
        "student_profile", "bedtime", "engagement", "cognitive_metrics",
        "interest_store",
    ):
        assert section in cfg, f"missing §1 section: {section}"
    assert cfg["student_profile"]["age"] == 16


# ── recompute_conversational_level ─────────────────────────────────────────

def test_recompute_level_increase(monkeypatch):
    """Test that level increases when score is high and flag is enabled."""
    monkeypatch.setenv("RESONANCE_ADAPTIVE_COMPLEXITY", "ON")
    metrics = {
        "current_conversational_level": 1,
        "level_min": 1,
        "parent_level_cap": 5,
        "parent_level_override": None,
        "last_level_change_iso": None,
        "level_change_cooldown_hours": 48,
        "rolling_average_sentence_length": 12.0,
        "active_vocabulary_retention_score": 1.0,
        "quiz_accuracy_streak": 5,
    }
    new_level = rc.recompute_conversational_level(metrics)
    assert new_level == 5
    assert metrics["current_conversational_level"] == 5
    assert metrics["last_level_change_iso"] is not None


def test_recompute_level_decrease(monkeypatch):
    """Test that level decreases when score is low and flag is enabled."""
    monkeypatch.setenv("RESONANCE_ADAPTIVE_COMPLEXITY", "ON")
    metrics = {
        "current_conversational_level": 3,
        "level_min": 1,
        "parent_level_cap": 5,
        "parent_level_override": None,
        "last_level_change_iso": None,
        "level_change_cooldown_hours": 48,
        "rolling_average_sentence_length": 0.0,
        "active_vocabulary_retention_score": 0.0,
        "quiz_accuracy_streak": 0,
    }
    new_level = rc.recompute_conversational_level(metrics)
    assert new_level == 1
    assert metrics["current_conversational_level"] == 1
    assert metrics["last_level_change_iso"] is not None


def test_recompute_level_cooldown(monkeypatch):
    """Test that level changes are blocked during cooldown period."""
    monkeypatch.setenv("RESONANCE_ADAPTIVE_COMPLEXITY", "ON")
    from datetime import datetime
    iso_now = datetime.now().isoformat()
    metrics = {
        "current_conversational_level": 1,
        "level_min": 1,
        "parent_level_cap": 5,
        "parent_level_override": None,
        "last_level_change_iso": iso_now,
        "level_change_cooldown_hours": 48,
        "rolling_average_sentence_length": 12.0,
        "active_vocabulary_retention_score": 1.0,
        "quiz_accuracy_streak": 5,
    }
    new_level = rc.recompute_conversational_level(metrics)
    assert new_level == 1
    assert metrics["current_conversational_level"] == 1


def test_recompute_level_override():
    """Test that parent level override wins verbatim."""
    metrics = {
        "current_conversational_level": 1,
        "level_min": 1,
        "parent_level_cap": 5,
        "parent_level_override": 4,
        "last_level_change_iso": None,
        "level_change_cooldown_hours": 48,
        "rolling_average_sentence_length": 0.0,
        "active_vocabulary_retention_score": 0.0,
        "quiz_accuracy_streak": 0,
    }
    new_level = rc.recompute_conversational_level(metrics)
    assert new_level == 4
    assert metrics["current_conversational_level"] == 4


def test_recompute_level_clamp(monkeypatch):
    """Test that the computed level is clamped within parent cap limits."""
    monkeypatch.setenv("RESONANCE_ADAPTIVE_COMPLEXITY", "ON")
    metrics = {
        "current_conversational_level": 1,
        "level_min": 1,
        "parent_level_cap": 3,
        "parent_level_override": None,
        "last_level_change_iso": None,
        "level_change_cooldown_hours": 48,
        "rolling_average_sentence_length": 12.0,
        "active_vocabulary_retention_score": 1.0,
        "quiz_accuracy_streak": 5,
    }
    new_level = rc.recompute_conversational_level(metrics)
    assert new_level == 3
    assert metrics["current_conversational_level"] == 3


def test_recompute_level_flagged_off():
    """Test that level remains unchanged when the adaptive complexity flag is disabled."""
    metrics = {
        "current_conversational_level": 1,
        "level_min": 1,
        "parent_level_cap": 5,
        "parent_level_override": None,
        "last_level_change_iso": None,
        "level_change_cooldown_hours": 48,
        "rolling_average_sentence_length": 12.0,
        "active_vocabulary_retention_score": 1.0,
        "quiz_accuracy_streak": 5,
    }
    new_level = rc.recompute_conversational_level(metrics)
    assert new_level == 1

