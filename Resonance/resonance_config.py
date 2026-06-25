"""
resonance_config.py — Single source of truth for parent_config.json I/O.

Implements §1 of docs/Resonance_Implementation_Plan_v2.md:

* load_config() validates the file on load and falls back to safe defaults
  (logging loudly) instead of crashing on missing / malformed input.
* save_config() writes atomically (temp file in the same directory, then
  os.replace) so a crash mid-write can never corrupt the config on disk.

SECURITY: This config holds NO API keys or secrets. Keys are read from the
environment only. save_config() strips any secret-looking top-level keys and
logs loudly if it ever finds them, so a key can't accidentally be persisted.
"""

import os
import json
import copy
import logging
import tempfile

logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_CONFIG_PATH = os.path.join(SCRIPT_DIR, "parent_config.json")

# Safe defaults for every section defined in §1 of the v2 plan. A fresh /
# corrupt config is rebuilt from this; partial configs are filled in from it.
DEFAULT_CONFIG = {
    "pin": "1234",
    "instructions": "",
    "focus_topics": [],
    "vocabulary": [],
    "progress_log": [],
    "student_profile": {
        "name": "Leo",
        "age": 16,
        "hobbies_interests": [],
        "social_level": "social",
        "academic_weak_areas": [],
        "stress_indicators": [],
        "learning_style_preferences": [],
    },
    "bedtime": {
        "scheduled_time": "21:30",
        "wind_down_minutes": 30,
        "child_stated_time": None,
        "last_asked_iso": None,
        "parent_hard_cap": "22:00",
        "wind_down_heads_up_iso": None,
    },
    "engagement": {
        "enabled": True,
        "max_initiations_per_hour": 2,
        "max_initiations_per_day": 6,
        "cooldown_after_decline_minutes": 30,
        "silence_is_decline_after_minutes": 4,
        "state": "idle",
        "cooldown_until_iso": None,
        "initiations": [],
    },
    "cognitive_metrics": {
        "rolling_average_sentence_length": 0.0,
        "active_vocabulary_retention_score": 0.0,
        "quiz_accuracy_streak": 0,
        "current_conversational_level": 1,
        "level_min": 1,
        "level_max": 5,
        "parent_level_cap": 5,
        "parent_level_override": None,
        "last_level_change_iso": None,
        "level_change_cooldown_hours": 48,
    },
    "interest_store": {
        "topics": [],
        "recent_callbacks": [],
        "max_callbacks": 20,
        "last_updated_iso": None,
    },
}

# Fallback cap for interest_store.recent_callbacks when none is configured.
DEFAULT_MAX_CALLBACKS = 20

# Expected python type for each known top-level section. A section with the
# wrong type is discarded in favour of its default (and logged loudly).
_SECTION_TYPES = {
    "pin": str,
    "instructions": str,
    "focus_topics": list,
    "vocabulary": list,
    "progress_log": list,
    "student_profile": dict,
    "bedtime": dict,
    "engagement": dict,
    "cognitive_metrics": dict,
    "interest_store": dict,
}

# Case-insensitive substrings that mark a top-level key as a secret. Such keys
# must never live in parent_config.json — they come from the environment only.
_SECRET_HINTS = (
    "api_key", "apikey", "secret", "password", "passwd", "token", "private_key",
)


def default_config():
    """Return a fresh deep copy of the safe defaults (never the shared dict)."""
    return copy.deepcopy(DEFAULT_CONFIG)


def _merge_section(default_value, loaded_value):
    """Fill missing keys of a dict section from its defaults; preserve extras.

    Non-dict sections are returned as-is (already type-validated by the caller).
    """
    if not isinstance(default_value, dict) or not isinstance(loaded_value, dict):
        return loaded_value
    merged = copy.deepcopy(default_value)
    merged.update(loaded_value)
    return merged


def enforce_interest_store_caps(config):
    """Trim interest_store.recent_callbacks to its ``max_callbacks`` (drop oldest).

    Keeps the child's behavioural profile bounded so it can't grow without limit.
    Mutates and returns ``config``; safe on missing/malformed values.
    """
    store = config.get("interest_store")
    if not isinstance(store, dict):
        return config
    callbacks = store.get("recent_callbacks")
    if not isinstance(callbacks, list):
        return config
    try:
        cap = int(store.get("max_callbacks", DEFAULT_MAX_CALLBACKS))
    except (ValueError, TypeError):
        cap = DEFAULT_MAX_CALLBACKS
    if cap < 0:
        cap = DEFAULT_MAX_CALLBACKS
    if len(callbacks) > cap:
        store["recent_callbacks"] = callbacks[-cap:]  # keep newest, drop oldest
    return config


def _strip_secrets(config):
    """Return a copy of config with any secret-looking top-level keys removed."""
    cleaned = {}
    for key, value in config.items():
        if any(hint in key.lower() for hint in _SECRET_HINTS):
            logger.error(
                "SECURITY: refusing to persist secret-looking key %r to "
                "parent_config.json — keys come from the environment only.",
                key,
            )
            continue
        cleaned[key] = value
    return cleaned


def load_config(path=PARENT_CONFIG_PATH):
    """Load and validate parent_config.json.

    On a missing file, malformed JSON, or a non-object top level, log loudly and
    return a fresh copy of the safe defaults instead of raising. Known sections
    with the wrong type are replaced by their defaults; dict sections are
    deep-merged so callers always find every expected field. Unknown top-level
    keys (e.g. report_intelligence, settings) are preserved as-is.
    """
    if not os.path.exists(path):
        logger.warning("parent_config.json not found at %s — using safe defaults.", path)
        return default_config()

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        logger.error(
            "Failed to read/parse parent_config.json at %s (%s) — using safe defaults.",
            path, e,
        )
        return default_config()

    if not isinstance(raw, dict):
        logger.error(
            "parent_config.json top level is %s, expected object — using safe defaults.",
            type(raw).__name__,
        )
        return default_config()

    config = default_config()
    for key, value in raw.items():
        expected = _SECTION_TYPES.get(key)
        if expected is None:
            # Unknown section (report_intelligence, settings, ...) — preserve it.
            config[key] = value
            continue
        if not isinstance(value, expected):
            logger.warning(
                "parent_config.json section %r has wrong type %s (expected %s) — "
                "using default for this section.",
                key, type(value).__name__, expected.__name__,
            )
            continue
        config[key] = _merge_section(DEFAULT_CONFIG.get(key), value)

    return config


def save_config(config, path=PARENT_CONFIG_PATH):
    """Atomically write config to parent_config.json.

    Writes to a temp file in the same directory, fsyncs it, then os.replace()s
    it into place so a crash mid-write leaves the original file intact. Any
    secret-looking top-level keys are stripped before writing.
    """
    if not isinstance(config, dict):
        raise TypeError(f"save_config expects a dict, got {type(config).__name__}")

    config = _strip_secrets(config)
    config = enforce_interest_store_caps(config)  # bound child profile growth

    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=directory, prefix=".parent_config.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        # Never leave a half-written temp file behind on failure.
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        logger.error("Failed to save parent_config.json atomically to %s.", path)
        raise

    return path


def recompute_conversational_level(metrics: dict) -> int:
    """Recompute the conversational complexity level based on cognitive metrics.

    Implements §7 of the v2 implementation plan:
      - Runs at session end (bidirectional).
      - Combines sentence length, vocabulary retention, and quiz streak.
      - Implements hysteresis to prevent jitter.
      - Clamps to parent caps and respects overrides.
      - Protected behind a feature flag (default off).
    """
    from datetime import datetime

    current_level = metrics.get("current_conversational_level", 1)
    level_min = metrics.get("level_min", 1)
    parent_level_cap = metrics.get("parent_level_cap", 5)
    parent_level_override = metrics.get("parent_level_override")

    # 1. Parent override wins immediately
    if parent_level_override is not None:
        clamped = max(level_min, min(parent_level_override, parent_level_cap))
        metrics["current_conversational_level"] = clamped
        return clamped

    # 2. Check feature flag (increment/decrement is disabled if flag is False)
    feature_flag = os.getenv("RESONANCE_ADAPTIVE_COMPLEXITY", "OFF").upper() == "ON"
    if not feature_flag:
        return current_level

    # 3. Check cooldown
    last_change_str = metrics.get("last_level_change_iso")
    cooldown_hours = metrics.get("level_change_cooldown_hours", 48)
    if last_change_str:
        try:
            last_change = datetime.fromisoformat(last_change_str)
            time_diff = datetime.now() - last_change
            if time_diff.total_seconds() < cooldown_hours * 3600:
                return current_level
        except Exception:
            pass

    # 4. Calculate weighted score
    sentence_len = metrics.get("rolling_average_sentence_length", 0.0)
    retention = metrics.get("active_vocabulary_retention_score", 0.0)
    streak = metrics.get("quiz_accuracy_streak", 0)

    sentence_score = min(1.0, sentence_len / 12.0)
    retention_score = min(1.0, retention)
    streak_score = min(1.0, streak / 5.0)

    # Weights: 40% Sentence Length, 40% Vocabulary, 20% Quiz Streak
    score = 0.4 * sentence_score + 0.4 * retention_score + 0.2 * streak_score

    # 5. Apply hysteresis logic
    # Band for current_level L is [(L-1)*0.2, L*0.2]
    # To step UP, score must clear L_upper + margin (0.05)
    # To step DOWN, score must fall below L_lower - margin (0.05)
    margin = 0.05
    current_lower = (current_level - 1) * 0.2
    current_upper = current_level * 0.2

    new_level = current_level
    if score >= current_upper + margin:
        calculated = int(score // 0.2) + 1
        new_level = min(5, calculated)
    elif score < current_lower - margin:
        calculated = int(score // 0.2) + 1
        new_level = max(1, calculated)

    # Clamp to parent controls
    clamped_new_level = max(level_min, min(new_level, parent_level_cap))

    if clamped_new_level != current_level:
        metrics["current_conversational_level"] = clamped_new_level
        metrics["last_level_change_iso"] = datetime.now().isoformat()

    return clamped_new_level

