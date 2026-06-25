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
        "last_updated_iso": None,
    },
}

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
