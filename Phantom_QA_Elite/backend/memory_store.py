"""
memory_store.py — Phantom QA Elite Persistent Test Memory
==========================================================
SQLite-based storage for test runs, individual results,
screenshots, and app registry with pass rate tracking.
"""

import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "phantom_memory.db"


def _conn():
    """Get SQLite connection with WAL mode for concurrent reads."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS test_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT NOT NULL,
            app_url TEXT,
            timestamp TEXT NOT NULL,
            verdict TEXT NOT NULL,
            score INTEGER NOT NULL,
            duration_seconds REAL,
            report_json TEXT,
            architect_plan TEXT,
            ghost_summary TEXT,
            skeptic_summary TEXT,
            fix_required TEXT
        );

        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            agent TEXT NOT NULL,
            test_name TEXT NOT NULL,
            passed INTEGER NOT NULL,
            details TEXT,
            duration_ms REAL,
            screenshot_path TEXT,
            FOREIGN KEY (run_id) REFERENCES test_runs(id)
        );

        CREATE TABLE IF NOT EXISTS app_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT UNIQUE NOT NULL,
            app_url TEXT,
            last_tested TEXT,
            total_runs INTEGER DEFAULT 0,
            total_passed INTEGER DEFAULT 0,
            last_score INTEGER,
            last_verdict TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_results_run ON test_results(run_id);
        CREATE INDEX IF NOT EXISTS idx_runs_app ON test_runs(app_name);

        CREATE TABLE IF NOT EXISTS repair_dispatches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            payloads_json TEXT,
            target_webhook TEXT,
            dispatched_at TEXT,
            completed_at TEXT,
            retest_run_id INTEGER,
            FOREIGN KEY (run_id) REFERENCES test_runs(id)
        );
    """)
    conn.close()


# ══════════════════════════════════════════════════════════
#  TEST RUNS
# ══════════════════════════════════════════════════════════

def save_test_run(app_name, app_url, verdict, score, duration,
                  report_data=None, architect_plan=None,
                  ghost_summary=None, skeptic_summary=None,
                  fix_required=None):
    """Save a complete test run and return its ID."""
    conn = _conn()
    cur = conn.execute("""
        INSERT INTO test_runs
            (app_name, app_url, timestamp, verdict, score, duration_seconds,
             report_json, architect_plan, ghost_summary, skeptic_summary, fix_required)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        app_name, app_url, datetime.now().isoformat(), verdict, score, duration,
        json.dumps(report_data) if report_data else None,
        json.dumps(architect_plan) if architect_plan else None,
        json.dumps(ghost_summary) if ghost_summary else None,
        json.dumps(skeptic_summary) if skeptic_summary else None,
        json.dumps(fix_required) if fix_required else None,
    ))
    run_id = cur.lastrowid

    # Update app registry
    conn.execute("""
        INSERT INTO app_registry (app_name, app_url, last_tested, total_runs, total_passed, last_score, last_verdict)
        VALUES (?, ?, ?, 1, ?, ?, ?)
        ON CONFLICT(app_name) DO UPDATE SET
            app_url = excluded.app_url,
            last_tested = excluded.last_tested,
            total_runs = total_runs + 1,
            total_passed = total_passed + excluded.total_passed,
            last_score = excluded.last_score,
            last_verdict = excluded.last_verdict
    """, (app_name, app_url, datetime.now().isoformat(),
          1 if verdict == "PASS" else 0, score, verdict))

    conn.commit()
    conn.close()

    # Auto-prune: keep last 10 runs per app
    _prune_old_runs(app_name, keep=10)

    return run_id


def save_test_result(run_id, agent, test_name, passed, details="",
                     duration_ms=0, screenshot_path=None):
    """Save an individual test result linked to a run."""
    conn = _conn()
    conn.execute("""
        INSERT INTO test_results (run_id, agent, test_name, passed, details, duration_ms, screenshot_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (run_id, agent, test_name, 1 if passed else 0, details, duration_ms, screenshot_path))
    conn.commit()
    conn.close()


def get_test_runs(app_name=None, limit=20):
    """Get recent test runs, optionally filtered by app."""
    conn = _conn()
    if app_name:
        rows = conn.execute(
            "SELECT * FROM test_runs WHERE app_name = ? ORDER BY id DESC LIMIT ?",
            (app_name, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM test_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_test_run(run_id):
    """Get a specific test run with all its results."""
    conn = _conn()
    run = conn.execute("SELECT * FROM test_runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        conn.close()
        return None
    results = conn.execute(
        "SELECT * FROM test_results WHERE run_id = ? ORDER BY id", (run_id,)
    ).fetchall()
    conn.close()

    run_dict = dict(run)
    run_dict["results"] = [dict(r) for r in results]

    # Parse JSON fields
    for field in ["report_json", "architect_plan", "ghost_summary", "skeptic_summary", "fix_required"]:
        if run_dict.get(field):
            try:
                run_dict[field] = json.loads(run_dict[field])
            except (json.JSONDecodeError, TypeError):
                pass

    return run_dict


# ══════════════════════════════════════════════════════════
#  DASHBOARD STATS
# ══════════════════════════════════════════════════════════

def get_dashboard_stats():
    """Get aggregate stats for the dashboard."""
    conn = _conn()

    total_runs = conn.execute("SELECT COUNT(*) FROM test_runs").fetchone()[0]
    total_passed = conn.execute("SELECT COUNT(*) FROM test_runs WHERE verdict = 'PASS'").fetchone()[0]
    total_apps = conn.execute("SELECT COUNT(DISTINCT app_name) FROM test_runs").fetchone()[0]
    total_results = conn.execute("SELECT COUNT(*) FROM test_results").fetchone()[0]
    total_results_passed = conn.execute("SELECT COUNT(*) FROM test_results WHERE passed = 1").fetchone()[0]

    avg_score = conn.execute("SELECT AVG(score) FROM test_runs").fetchone()[0] or 0

    # Recent runs
    recent = conn.execute(
        "SELECT id, app_name, verdict, score, timestamp, duration_seconds FROM test_runs ORDER BY id DESC LIMIT 5"
    ).fetchall()

    # App registry
    apps = conn.execute("SELECT * FROM app_registry ORDER BY last_tested DESC").fetchall()

    conn.close()

    return {
        "total_runs": total_runs,
        "total_passed": total_passed,
        "total_apps": total_apps,
        "total_tests": total_results,
        "tests_passed": total_results_passed,
        "avg_score": round(avg_score),
        "pass_rate": round(total_passed / total_runs * 100) if total_runs > 0 else 0,
        "recent_runs": [dict(r) for r in recent],
        "app_registry": [dict(a) for a in apps],
    }


# ══════════════════════════════════════════════════════════
#  REPAIR DISPATCHES
# ══════════════════════════════════════════════════════════

def save_repair_dispatch(run_id: int, payloads: list, target_webhook: str) -> int:
    """Save a repair dispatch and return its ID."""
    conn = _conn()
    cur = conn.execute("""
        INSERT INTO repair_dispatches
            (run_id, status, payloads_json, target_webhook, dispatched_at)
        VALUES (?, 'pending', ?, ?, ?)
    """, (run_id, json.dumps(payloads), target_webhook, datetime.now().isoformat()))
    dispatch_id = cur.lastrowid
    conn.commit()
    conn.close()
    return dispatch_id


def mark_repair_complete(dispatch_id: int, success: bool = True):
    """Mark a repair dispatch as complete or failed."""
    conn = _conn()
    conn.execute("""
        UPDATE repair_dispatches
        SET status = ?, completed_at = ?
        WHERE id = ?
    """, ("complete" if success else "failed", datetime.now().isoformat(), dispatch_id))
    conn.commit()
    conn.close()


def get_pending_repairs() -> list:
    """Get all pending repair dispatches."""
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM repair_dispatches WHERE status = 'pending' ORDER BY id DESC"
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["payloads"] = json.loads(d.pop("payloads_json"))
        except (json.JSONDecodeError, KeyError):
            d["payloads"] = []
        results.append(d)
    return results


def get_repair_dispatches(run_id: int = None) -> list:
    """Get repair dispatches, optionally filtered by run."""
    conn = _conn()
    if run_id:
        rows = conn.execute(
            "SELECT * FROM repair_dispatches WHERE run_id = ? ORDER BY id DESC", (run_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM repair_dispatches ORDER BY id DESC LIMIT 20"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════
#  CLEANUP
# ══════════════════════════════════════════════════════════

def _prune_old_runs(app_name, keep=10):
    """Keep only the last N runs per app."""
    conn = _conn()
    rows = conn.execute(
        "SELECT id FROM test_runs WHERE app_name = ? ORDER BY id DESC",
        (app_name,)
    ).fetchall()

    if len(rows) > keep:
        old_ids = [r["id"] for r in rows[keep:]]
        placeholders = ",".join("?" * len(old_ids))
        conn.execute(f"DELETE FROM test_results WHERE run_id IN ({placeholders})", old_ids)
        conn.execute(f"DELETE FROM test_runs WHERE id IN ({placeholders})", old_ids)
        conn.commit()

    conn.close()


# Initialize on import
init_db()
