"""
memory_engine.py — Architect Memory (SQLite)
═════════════════════════════════════════════
Master_Architect_Elite_Logic | Meta App Factory

CRUD interface for architect_memory.db — stores winning architecture
patterns, review logs, and regression trackers.
"""

import os
import json
import hashlib
import sqlite3
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("ArchitectMemory")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Default config ──────────────────────────────────────
_DEFAULT_DB_PATH = os.path.join(SCRIPT_DIR, "architect_memory.db")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_hash    TEXT UNIQUE NOT NULL,
    domain          TEXT NOT NULL,
    category        TEXT NOT NULL,
    pattern         TEXT NOT NULL,
    rationale       TEXT,
    technologies    TEXT,
    triad_score     INTEGER,
    gate_status     TEXT DEFAULT 'approved',
    use_count       INTEGER DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reviews (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    request_hash        TEXT NOT NULL,
    request_summary     TEXT NOT NULL,
    structural_score    INTEGER,
    logic_score         INTEGER,
    security_score      INTEGER,
    composite_score     INTEGER,
    verdict             TEXT NOT NULL,
    gate_result         TEXT,
    weaknesses          TEXT,
    user_reasoning      TEXT,
    reviewed_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS regressions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_id      INTEGER REFERENCES patterns(id),
    app_name        TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    match_type      TEXT NOT NULL,
    severity        TEXT NOT NULL,
    resolved        BOOLEAN DEFAULT FALSE,
    detected_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at     TIMESTAMP
);
"""


class ArchitectMemory:
    """
    CRUD interface for architect_memory.db.
    Thread-safe via check_same_thread=False.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or _DEFAULT_DB_PATH
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_schema()

    # ── Connection ───────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                self.db_path, check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _ensure_schema(self):
        conn = self._get_conn()
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
        logger.info(f"Architect memory ready: {self.db_path}")

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Pattern CRUD ─────────────────────────────────────

    @staticmethod
    def _hash_pattern(category: str, pattern: str, technologies: list) -> str:
        """Deterministic hash for deduplication."""
        blob = f"{category}::{pattern}::{sorted(technologies)}".lower()
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    def store_pattern(self, pattern_data: dict, gate_status: str = "approved") -> int:
        """
        Store a winning architecture pattern. Upserts on pattern_hash.
        Returns the pattern ID.
        """
        conn = self._get_conn()
        category = pattern_data.get("category", "general")
        pattern_name = pattern_data.get("pattern", "unknown")
        techs = pattern_data.get("technologies", [])
        if isinstance(techs, str):
            techs = [techs]

        p_hash = self._hash_pattern(category, pattern_name, techs)

        # Check if exists
        row = conn.execute(
            "SELECT id, use_count FROM patterns WHERE pattern_hash = ?", (p_hash,)
        ).fetchone()

        if row:
            conn.execute(
                "UPDATE patterns SET use_count = ?, last_used = ?, gate_status = ? WHERE id = ?",
                (row["use_count"] + 1, datetime.now().isoformat(), gate_status, row["id"]),
            )
            conn.commit()
            logger.info(f"Pattern updated (use_count={row['use_count'] + 1}): {pattern_name}")
            return row["id"]

        cursor = conn.execute(
            """INSERT INTO patterns
               (pattern_hash, domain, category, pattern, rationale, technologies,
                triad_score, gate_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                p_hash,
                pattern_data.get("domain", "general"),
                category,
                pattern_name,
                pattern_data.get("rationale", ""),
                json.dumps(techs),
                pattern_data.get("triad_score", 0),
                gate_status,
            ),
        )
        conn.commit()
        logger.info(f"Pattern stored (id={cursor.lastrowid}): {pattern_name}")
        return cursor.lastrowid

    def find_similar(self, category: str, technologies: list = None,
                     limit: int = 5) -> list[dict]:
        """
        Find similar past patterns by category and technology overlap.
        Returns list of pattern dicts sorted by relevance.
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM patterns WHERE category = ? ORDER BY use_count DESC, last_used DESC LIMIT ?",
            (category, limit * 3),
        ).fetchall()

        results = []
        for row in rows:
            row_dict = dict(row)
            try:
                row_techs = json.loads(row_dict.get("technologies", "[]"))
            except (json.JSONDecodeError, TypeError):
                row_techs = []

            # Score by technology overlap
            if technologies:
                overlap = len(set(t.lower() for t in row_techs) & set(t.lower() for t in technologies))
                row_dict["relevance"] = overlap / max(len(technologies), 1)
            else:
                row_dict["relevance"] = 0.5

            row_dict["technologies"] = row_techs
            results.append(row_dict)

        results.sort(key=lambda r: (r["relevance"], r["use_count"]), reverse=True)
        return results[:limit]

    def get_all_patterns(self, limit: int = 50) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM patterns ORDER BY use_count DESC, last_used DESC LIMIT ?",
            (limit,),
        ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            try:
                d["technologies"] = json.loads(d.get("technologies", "[]"))
            except (json.JSONDecodeError, TypeError):
                d["technologies"] = []
            results.append(d)
        return results

    # ── Review CRUD ──────────────────────────────────────

    def record_review(self, review: dict) -> int:
        """Record a Triad review with all agent scores."""
        conn = self._get_conn()
        summary = review.get("request_summary", "")
        r_hash = hashlib.sha256(summary.encode()).hexdigest()[:16]

        cursor = conn.execute(
            """INSERT INTO reviews
               (request_hash, request_summary, structural_score, logic_score,
                security_score, composite_score, verdict, gate_result,
                weaknesses, user_reasoning)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                r_hash,
                summary[:500],
                review.get("structural_score"),
                review.get("logic_score"),
                review.get("security_score"),
                review.get("composite_score"),
                review.get("verdict", "PENDING"),
                review.get("gate_result"),
                json.dumps(review.get("weaknesses", [])),
                review.get("user_reasoning"),
            ),
        )
        conn.commit()
        return cursor.lastrowid

    def get_recent_reviews(self, limit: int = 20) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM reviews ORDER BY reviewed_at DESC LIMIT ?", (limit,)
        ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            try:
                d["weaknesses"] = json.loads(d.get("weaknesses", "[]"))
            except (json.JSONDecodeError, TypeError):
                d["weaknesses"] = []
            results.append(d)
        return results

    # ── Regression CRUD ──────────────────────────────────

    def record_regression(self, regression: dict) -> int:
        conn = self._get_conn()
        cursor = conn.execute(
            """INSERT INTO regressions
               (pattern_id, app_name, file_path, match_type, severity)
               VALUES (?, ?, ?, ?, ?)""",
            (
                regression.get("pattern_id"),
                regression.get("app_name", "unknown"),
                regression.get("file_path", ""),
                regression.get("match_type", "keyword_match"),
                regression.get("severity", "MEDIUM"),
            ),
        )
        conn.commit()
        return cursor.lastrowid

    def get_active_regressions(self) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM regressions WHERE resolved = FALSE ORDER BY detected_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def resolve_regression(self, regression_id: int) -> bool:
        conn = self._get_conn()
        conn.execute(
            "UPDATE regressions SET resolved = TRUE, resolved_at = ? WHERE id = ?",
            (datetime.now().isoformat(), regression_id),
        )
        conn.commit()
        return True

    # ── Stats ────────────────────────────────────────────

    def get_stats(self) -> dict:
        conn = self._get_conn()
        patterns_count = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
        reviews_count = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        regressions_active = conn.execute(
            "SELECT COUNT(*) FROM regressions WHERE resolved = FALSE"
        ).fetchone()[0]
        battle_tested = conn.execute(
            "SELECT COUNT(*) FROM patterns WHERE gate_status = 'battle_tested'"
        ).fetchone()[0]

        return {
            "patterns": patterns_count,
            "battle_tested": battle_tested,
            "reviews": reviews_count,
            "active_regressions": regressions_active,
            "db_path": self.db_path,
        }
