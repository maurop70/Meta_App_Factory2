"""
Sentinel Bridge — Categorization Engine (ML Feedback Loop)
===========================================================
Sorts reminders into: AI, Work, Leo's School, Family.
Learns from user overrides via a lightweight feedback loop that
updates keyword weights and custom rules.

User Sovereignty: The user can always override any category, and the
engine will adjust its future predictions accordingly.
"""

# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

from auto_heal import healed_post, auto_heal, diagnose

def _v3_preflight():
    """V3: Ping Resonance_Watchdog_V3 before execution."""
    if not _V3_AVAILABLE:
        return True
    try:
        import json as _j
        _cfg_path = _os.path.join(_FACTORY_DIR, "resilience_config.json")
        if not _os.path.exists(_cfg_path):
            return True
        with open(_cfg_path) as _f:
            _cfg = _j.load(_f)
        _url = _cfg.get("cloud_health", {}).get("watchdog_url", "")
        if not _url:
            return True
        import requests as _rq
        _r = _rq.get(_url, timeout=5)
        return _r.status_code == 200
    except Exception:
        return False


import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger("sentinel.categorization")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DEFAULT_CATEGORIES = ["AI", "Work", "Leo's School", "Family"]


class CategorizationEngine:
    """
    ML-lite categorization with keyword boosting and user feedback loop.

    The engine maintains:
    - Base keyword weights (seeded from HIGH_STAKES_KEYWORDS)
    - Override history (user corrections become training data)
    - Custom rules (user-defined patterns → category mappings)
    """

    def __init__(self):
        self.categories = list(DEFAULT_CATEGORIES)
        self.keyword_weights: dict[str, dict[str, float]] = {}
        self.custom_rules: list[dict] = []
        self.override_history: list[dict] = []
        self._load_state()

    # ── Public API ───────────────────────────────────────────────────
    def categorize(self, text: str, hints: dict | None = None) -> dict:
        """
        Categorize text and return result with confidence.

        Returns:
            {
                "category": "Work",
                "confidence": 0.82,
                "method": "keyword_match"|"custom_rule"|"override_learned",
                "alternatives": [{"category": "AI", "confidence": 0.15}]
            }
        """
        text_lower = text.lower()

        # 1. Check custom rules first (highest priority)
        for rule in self.custom_rules:
            if rule["pattern"].lower() in text_lower:
                return {
                    "category": rule["category"],
                    "confidence": 0.95,
                    "method": "custom_rule",
                    "alternatives": [],
                }

        # 2. Score against keyword weights
        scores: dict[str, float] = defaultdict(float)
        for category, keywords in self.keyword_weights.items():
            for keyword, weight in keywords.items():
                if keyword in text_lower:
                    scores[category] += weight

        # 3. Apply hints from calendar source
        if hints:
            source = hints.get("calendar_label", "")
            if source in self.categories:
                scores[source] += 0.3

        # 4. Rank results
        if not scores:
            return {
                "category": "Uncategorized",
                "confidence": 0.0,
                "method": "none",
                "alternatives": [],
            }

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_cat, best_score = ranked[0]
        total = sum(s for _, s in ranked)
        confidence = best_score / total if total > 0 else 0.0

        alternatives = [
            {"category": cat, "confidence": round(score / total, 2)}
            for cat, score in ranked[1:3]
            if score / total > 0.1
        ]

        return {
            "category": best_cat,
            "confidence": round(confidence, 2),
            "method": "keyword_match",
            "alternatives": alternatives,
        }

    def override_category(self, reminder_id: str, original_text: str,
                          old_category: str, new_category: str) -> dict:
        """
        Record a user override and update keyword weights.
        This is the ML feedback loop — future similar items will
        be categorized correctly.
        """
        # Record the override
        override = {
            "reminder_id": reminder_id,
            "text": original_text,
            "old_category": old_category,
            "new_category": new_category,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.override_history.append(override)

        # Extract keywords from the text and boost them for the new category
        words = self._extract_keywords(original_text)
        for word in words:
            # Boost new category
            if new_category not in self.keyword_weights:
                self.keyword_weights[new_category] = {}
            current = self.keyword_weights[new_category].get(word, 0.0)
            self.keyword_weights[new_category][word] = min(current + 0.3, 2.0)

            # Penalize old category
            if old_category in self.keyword_weights:
                old_weight = self.keyword_weights[old_category].get(word, 0.0)
                if old_weight > 0:
                    self.keyword_weights[old_category][word] = max(
                        old_weight - 0.15, 0.0)

        # Add as custom rule if this is a repeated override (3+ times)
        similar_overrides = [
            o for o in self.override_history
            if o["new_category"] == new_category
            and self._text_similarity(o["text"], original_text) > 0.6
        ]
        if len(similar_overrides) >= 3:
            # Create a custom rule from the common pattern
            pattern = self._find_common_pattern(
                [o["text"] for o in similar_overrides])
            if pattern and not any(r["pattern"] == pattern
                                   for r in self.custom_rules):
                self.custom_rules.append({
                    "pattern": pattern,
                    "category": new_category,
                    "created_from": "ml_feedback",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                logger.info("ML Loop: Created custom rule '%s' → '%s'",
                            pattern, new_category)

        # Ensure category exists in master list
        if new_category not in self.categories:
            self.categories.append(new_category)

        self._save_state()
        logger.info("Override recorded: '%s' → '%s' (was '%s')",
                     original_text[:40], new_category, old_category)

        return {
            "status": "override_applied",
            "new_category": new_category,
            "keywords_updated": len(words),
            "custom_rule_created": len(similar_overrides) >= 3,
        }

    def add_category(self, name: str) -> bool:
        """Add a new user-defined category."""
        if name not in self.categories:
            self.categories.append(name)
            self.keyword_weights[name] = {}
            self._save_state()
            logger.info("New category added: '%s'", name)
            return True
        return False

    def add_custom_rule(self, pattern: str, category: str) -> dict:
        """Add a manual custom rule."""
        if category not in self.categories:
            self.categories.append(category)

        rule = {
            "pattern": pattern,
            "category": category,
            "created_from": "manual",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.custom_rules.append(rule)
        self._save_state()
        return rule

    def get_stats(self) -> dict:
        """Return engine statistics for telemetry."""
        return {
            "categories": self.categories,
            "total_keywords": sum(len(v) for v in self.keyword_weights.values()),
            "custom_rules": len(self.custom_rules),
            "total_overrides": len(self.override_history),
            "overrides_by_category": self._override_counts(),
        }

    # ── Internal Helpers ─────────────────────────────────────────────
    def _extract_keywords(self, text: str) -> list[str]:
        """Extract meaningful keywords from text."""
        stop_words = {"the", "a", "an", "is", "to", "for", "of", "in",
                      "at", "on", "and", "or", "but", "my", "me", "i",
                      "it", "do", "not", "with", "from", "this", "that",
                      "be", "have", "has", "had", "will", "can", "could",
                      "should", "would", "was", "were", "been", "being"}
        words = text.lower().split()
        return [w.strip(".,!?;:'\"") for w in words
                if len(w) > 2 and w.lower() not in stop_words]

    def _text_similarity(self, a: str, b: str) -> float:
        """Simple word-overlap similarity."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    def _find_common_pattern(self, texts: list[str]) -> str:
        """Find the longest common substring among override texts."""
        if not texts:
            return ""
        # Use the shortest text's words as candidates
        base_words = texts[0].lower().split()
        for length in range(len(base_words), 0, -1):
            for start in range(len(base_words) - length + 1):
                candidate = " ".join(base_words[start:start + length])
                if all(candidate in t.lower() for t in texts):
                    if len(candidate) > 3:
                        return candidate
        return ""

    def _override_counts(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for o in self.override_history:
            counts[o["new_category"]] += 1
        return dict(counts)

    # ── Persistence ──────────────────────────────────────────────────
    def _load_state(self) -> None:
        state_file = DATA_DIR / "categorization_state.json"
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
                self.categories = state.get("categories", DEFAULT_CATEGORIES)
                self.keyword_weights = state.get("keyword_weights", {})
                self.custom_rules = state.get("custom_rules", [])
                self.override_history = state.get("override_history", [])
                return
            except Exception as exc:
                logger.error("Failed to load state: %s", exc)

        # Seed default keyword weights
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        """Initialize with baseline keyword weights."""
        from aether_ingestion import HIGH_STAKES_KEYWORDS
        for category, keywords in HIGH_STAKES_KEYWORDS.items():
            self.keyword_weights[category] = {
                kw: 0.5 for kw in keywords
            }

    def _save_state(self) -> None:
        state_file = DATA_DIR / "categorization_state.json"
        state = {
            "categories": self.categories,
            "keyword_weights": self.keyword_weights,
            "custom_rules": self.custom_rules,
            "override_history": self.override_history[-1000:],  # cap history
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        state_file.write_text(json.dumps(state, indent=2))
# V3 AUTO-HEAL ACTIVE
