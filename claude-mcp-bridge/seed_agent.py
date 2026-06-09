"""
Seed Agent — MAF E2E Evaluator
-------------------------------
Reads the DB schema and TestPlan, then generates and inserts minimum viable
test data so every test case has something to work with.

No hardcoded data — everything is derived from actual schema discovery.

Safety rules:
  - Never DELETE or TRUNCATE existing records
  - INSERT OR IGNORE only
  - Never touch any DB that isn't app_config["db_path"] (resolved)
  - If db_path not found: errors recorded, success=False, return early
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import sqlite3

# ── Locate bridge root ────────────────────────────────────────────────────────
_BRIDGE_DIR = Path(__file__).parent.resolve()
_MAF_ROOT   = _BRIDGE_DIR.parent.resolve()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dataclasses
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SeedEntry:
    table: str
    records_inserted: int
    sample: dict          # one example record


@dataclass
class SeedReport:
    app_name: str
    run_id: str
    tables_seeded: list   # list of table names touched
    records_inserted: int
    seed_log: list        # list of SeedEntry as dicts
    errors: list
    success: bool


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _resolve_db_path(app_config: dict) -> Optional[Path]:
    """
    Resolve the actual database file path from app_config.

    Strategy (in order):
    1. db_path is absolute → use directly
    2. db_path relative to local_path
    3. Walk local_path tree for any .db file (up to 3 levels deep)
    Returns None if nothing found.
    """
    raw      = app_config.get("db_path", "")
    lp       = app_config.get("local_path", "")
    local    = Path(lp)

    # Absolute path given and exists
    p = Path(raw)
    if p.is_absolute() and p.exists():
        return p

    # Relative to local_path
    candidate = (local / raw).resolve()
    if candidate.exists() and candidate.stat().st_size > 0:
        return candidate

    # Walk local_path sub-dirs looking for any .db file with data
    # Prioritise deeper paths and larger sizes (more data = likely the real DB)
    best: Optional[Path] = None
    best_size = 0
    for depth, root, dirs, files in _walk_limited(local, max_depth=4):
        for fname in files:
            if fname.endswith(".db"):
                fp = Path(root) / fname
                try:
                    size = fp.stat().st_size
                    if size > best_size:
                        best_size = size
                        best = fp
                except OSError:
                    pass

    return best if best and best_size > 0 else None


def _walk_limited(root: Path, max_depth: int):
    """os.walk with a depth cap; yields (depth, dirpath, dirs, files)."""
    for dirpath, dirs, files in os.walk(root):
        depth = len(Path(dirpath).relative_to(root).parts)
        if depth >= max_depth:
            dirs[:] = []   # prune further descent
        yield depth, dirpath, dirs, files


def _get_tables(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [r[0] for r in cur.fetchall()]


def _get_columns(conn: sqlite3.Connection, table: str) -> list[dict]:
    """Return PRAGMA table_info rows as dicts."""
    cur = conn.execute(f"PRAGMA table_info(\"{table}\")")
    rows = cur.fetchall()
    return [
        {
            "cid":       r[0],
            "name":      r[1],
            "type":      r[2].upper() if r[2] else "TEXT",
            "notnull":   r[3],
            "dflt_value": r[4],
            "pk":        r[5],
        }
        for r in rows
    ]


def _count(conn: sqlite3.Connection, table: str) -> int:
    cur = conn.execute(f'SELECT COUNT(*) FROM "{table}"')
    return cur.fetchone()[0]


def _get_first_id(conn: sqlite3.Connection, table: str, pk_col: str) -> Optional[str]:
    """Return first PK value from a table, or None if empty."""
    try:
        cur = conn.execute(f'SELECT "{pk_col}" FROM "{table}" LIMIT 1')
        row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SeedAgent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SeedAgent:
    """
    Schema-driven DB seeding for E2E test runs.

    Reads PRAGMA table_info to discover columns, generates minimal test data
    based on column name heuristics, and inserts via INSERT OR IGNORE.
    """

    # Minimum records required per table-name keyword
    _KEYWORD_MINIMUMS = {
        "employee": 3,
        "user":     3,
        "work_order": 3,
        "workorder":  3,
        "equipment":  3,
        "department": 2,
        "location":   2,
        "category":   2,
        "sku":        3,
        "part":       3,
        "procurement": 2,
    }

    # Minimum for every other table (0 = don't seed unless test_plan says so)
    _DEFAULT_MINIMUM = 0

    def seed(self, app_config: dict, test_plan: Any, run_id: str) -> SeedReport:
        """
        Main entry-point.  Phases 1-7 as described in the module docstring.
        Returns a SeedReport regardless of errors.
        """
        app_name  = app_config.get("name", "Unknown App")
        errors: list[str] = []
        seed_log:  list[dict] = []
        total_inserted = 0

        print(f"[SeedAgent] Starting seed for '{app_name}' (run_id={run_id})")

        # ── Resolve DB path ─────────────────────────────────────────────────
        db_path = _resolve_db_path(app_config)
        if db_path is None:
            msg = (
                f"DB file not found.  "
                f"app_config db_path='{app_config.get('db_path')}' "
                f"local_path='{app_config.get('local_path')}'"
            )
            errors.append(msg)
            print(f"[SeedAgent] ERROR: {msg}")
            report = SeedReport(
                app_name=app_name, run_id=run_id, tables_seeded=[],
                records_inserted=0, seed_log=[], errors=errors, success=False,
            )
            self._save_report(report, run_id)
            return report

        print(f"[SeedAgent] Using DB: {db_path}")

        # ── Phase 1: Read DB schema ──────────────────────────────────────────
        # Use default isolation_level (NOT autocommit) so we can call conn.commit()
        conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=OFF")   # allow seeding without FK order concerns

        try:
            tables       = _get_tables(conn)
            schema_map: dict[str, list[dict]] = {}
            for t in tables:
                schema_map[t] = _get_columns(conn, t)

            print(f"[SeedAgent] Phase 1: found {len(tables)} tables")

            # ── Phase 2: Read existing counts ───────────────────────────────
            existing: dict[str, int] = {}
            for t in tables:
                existing[t] = _count(conn, t)
            print(f"[SeedAgent] Phase 2: counted existing rows per table")

            # ── Phase 3: Determine seeding targets ──────────────────────────
            targets: dict[str, int] = self._build_targets(tables, test_plan, app_config)
            print(f"[SeedAgent] Phase 3: {len(targets)} tables need seeding")
            for tbl, mn in targets.items():
                have = existing.get(tbl, 0)
                print(f"  {tbl}: need {mn}, have {have}")

            # ── Phase 4+5: Generate + Insert per table ───────────────────────
            auth_config = app_config.get("auth_config", {})

            # Pre-cache real existing PKs for all tables (for FK resolution)
            fk_cache: dict[str, list] = {}
            for t in tables:
                cols = schema_map.get(t, [])
                pk_cols = [c for c in cols if c["pk"]]
                if pk_cols:
                    pk_name = pk_cols[0]["name"]
                    try:
                        cur = conn.execute(f'SELECT "{pk_name}" FROM "{t}" LIMIT 20')
                        fk_cache[t] = [r[0] for r in cur.fetchall()]
                    except Exception:
                        fk_cache[t] = []
                else:
                    fk_cache[t] = []

            # Extra: cache HM employee IDs specifically (needed for assigned_hm_id)
            if "erp_employees" in schema_map:
                try:
                    cur = conn.execute(
                        "SELECT id FROM erp_employees WHERE role IN ('HM', 'ADMIN', 'ADMINISTRATOR') LIMIT 10"
                    )
                    hm_ids = [r[0] for r in cur.fetchall()]
                    if not hm_ids:
                        hm_ids = fk_cache.get("erp_employees", [])
                    fk_cache["erp_employees_hm"] = hm_ids
                except Exception:
                    fk_cache["erp_employees_hm"] = fk_cache.get("erp_employees", [])

            # Extra: cache work_order IDs
            if "work_orders" in schema_map:
                try:
                    cur = conn.execute("SELECT mwo_id FROM work_orders LIMIT 10")
                    fk_cache["work_orders"] = [r[0] for r in cur.fetchall()]
                except Exception:
                    pass

            # Seed order: lookup/reference tables first, then records that may FK to them
            ordered = self._order_tables(list(targets.keys()), tables)

            for tbl in ordered:
                min_req = targets[tbl]
                have    = existing.get(tbl, 0)
                need    = max(0, min_req - have)
                if need == 0:
                    print(f"[SeedAgent] {tbl}: already has {have} rows (>= {min_req}), skipping")
                    continue

                print(f"[SeedAgent] {tbl}: inserting {need} rows (have {have}, need {min_req})")
                cols = schema_map.get(tbl, [])
                if not cols:
                    errors.append(f"No schema found for {tbl}")
                    continue

                inserted, sample, err = self._insert_records(
                    conn, tbl, cols, need, schema_map, auth_config, fk_cache
                )
                total_inserted += inserted
                if err:
                    errors.extend(err)
                if inserted > 0:
                    seed_log.append(asdict(SeedEntry(table=tbl, records_inserted=inserted, sample=sample)))
                    existing[tbl] = existing.get(tbl, 0) + inserted
                    # Update fk_cache so downstream tables can reference just-inserted rows
                    pk_cols = [c for c in cols if c["pk"]]
                    if pk_cols:
                        pk_name = pk_cols[0]["name"]
                        try:
                            cur = conn.execute(f'SELECT "{pk_name}" FROM "{tbl}" LIMIT 20')
                            fk_cache[tbl] = [r[0] for r in cur.fetchall()]
                        except Exception:
                            pass

            # ── Phase 6: Verify ──────────────────────────────────────────────
            tables_seeded = [e["table"] for e in seed_log]
            final_counts: dict[str, int] = {}
            for tbl in tables:
                final_counts[tbl] = _count(conn, tbl)

            print(f"[SeedAgent] Phase 6: verification complete")
            for tbl, cnt in final_counts.items():
                if tbl in targets:
                    print(f"  {tbl}: {cnt} rows (target: {targets[tbl]})")

        except Exception as exc:
            errors.append(f"Unexpected error during seeding: {exc}")
            print(f"[SeedAgent] FATAL: {exc}")
            import traceback; traceback.print_exc()
        finally:
            conn.close()

        report = SeedReport(
            app_name         = app_name,
            run_id           = run_id,
            tables_seeded    = tables_seeded,
            records_inserted = total_inserted,
            seed_log         = seed_log,
            errors           = errors,
            success          = len(errors) == 0,
        )

        # ── Phase 7: Save report ─────────────────────────────────────────────
        self._save_report(report, run_id)
        return report

    # ── Internal: build seeding targets ─────────────────────────────────────

    def _build_targets(
        self,
        db_tables: list[str],
        test_plan: Any,
        app_config: dict,
    ) -> dict[str, int]:
        """
        Merge test_plan.seed_requirements with keyword-based minimums.
        Returns {table_name: min_required}.
        """
        targets: dict[str, int] = {}

        # From test_plan
        if test_plan is not None:
            sr = getattr(test_plan, "seed_requirements", None)
            if sr is None and isinstance(test_plan, dict):
                sr = test_plan.get("seed_requirements")

            if sr is not None:
                # Could be a SeedRequirements object with .tables, or a dict
                table_list = None
                if hasattr(sr, "tables"):
                    table_list = sr.tables
                elif isinstance(sr, dict):
                    table_list = sr.get("tables", [])

                if table_list:
                    for entry in table_list:
                        if hasattr(entry, "table_name"):
                            tn = entry.table_name
                            mr = entry.min_records
                        elif isinstance(entry, dict):
                            tn = entry.get("table_name", "")
                            mr = entry.get("min_records", 3)
                        else:
                            continue
                        # Map generic names to real table names
                        real = self._map_to_real_table(tn, db_tables)
                        if real:
                            targets[real] = max(targets.get(real, 0), mr)

        # Keyword-based minimums for tables that exist in the DB
        for tbl in db_tables:
            tbl_lower = tbl.lower()
            for keyword, minimum in self._KEYWORD_MINIMUMS.items():
                if keyword in tbl_lower:
                    targets[tbl] = max(targets.get(tbl, 0), minimum)
                    break

        return targets

    def _map_to_real_table(self, name: str, db_tables: list[str]) -> Optional[str]:
        """Map a logical table name to an actual DB table, by substring match."""
        name_lower = name.lower()
        # exact match first
        if name in db_tables:
            return name
        # try erp_ prefix
        with_prefix = "erp_" + name_lower
        if with_prefix in db_tables:
            return with_prefix
        # substring match
        for t in db_tables:
            if name_lower in t.lower():
                return t
        return None

    def _order_tables(self, target_tables: list[str], all_tables: list[str]) -> list[str]:
        """
        Return target_tables in dependency order:
        lookup/reference tables first (categories, departments, locations, skus),
        then transactional tables (employees, equipment, work_orders, etc.).
        """
        priority = {
            "erp_categories":       0,
            "erp_departments":      1,
            "erp_locations":        2,
            "erp_skus":             3,
            "erp_employees":        4,
            "users":                5,
            "erp_equipment":        6,
            "erp_parts":            7,
            "work_orders":          8,
            "erp_procurement_queue":9,
            "erp_inventory_ledger": 10,
            "mwo_consumed_parts":   11,
            "warehouse_inventory":  12,
        }
        def sort_key(t):
            return priority.get(t, 99)
        return sorted(target_tables, key=sort_key)

    # ── Internal: generate + insert records ──────────────────────────────────

    def _insert_records(
        self,
        conn: sqlite3.Connection,
        table: str,
        cols: list[dict],
        count: int,
        schema_map: dict[str, list[dict]],
        auth_config: dict,
        fk_cache: Optional[dict] = None,
    ) -> tuple[int, dict, list[str]]:
        """
        Generate `count` rows for `table` and INSERT OR IGNORE them.
        Returns (inserted_count, sample_record, error_list).
        """
        errors: list[str] = []
        inserted = 0
        sample: dict = {}
        tbl_lower = table.lower()

        # Determine which columns to fill (skip columns with defaults that
        # are not NOT NULL, unless they are PKs)
        writable_cols = [c for c in cols if not self._should_skip(c)]

        if not writable_cols:
            return 0, {}, [f"{table}: no writable columns found"]

        col_names = [c["name"] for c in writable_cols]
        placeholders = ", ".join("?" for _ in col_names)
        sql = (
            f'INSERT OR IGNORE INTO "{table}" '
            f'({", ".join(f"{chr(34)}{cn}{chr(34)}" for cn in col_names)}) '
            f'VALUES ({placeholders})'
        )

        for i in range(count):
            row_vals = self._generate_row(
                table, writable_cols, i, schema_map, auth_config, tbl_lower,
                fk_cache or {}
            )
            try:
                conn.execute(sql, row_vals)
                conn.commit()
                if inserted == 0:
                    sample = dict(zip(col_names, row_vals))
                inserted += 1
            except sqlite3.IntegrityError as exc:
                # May be duplicate or FK violation — log and continue
                errors.append(f"{table}[{i}] IntegrityError: {exc}")
            except Exception as exc:
                errors.append(f"{table}[{i}] Error: {exc}")

        return inserted, sample, errors

    def _should_skip(self, col: dict) -> bool:
        """
        True if the column should be skipped when inserting
        (has a default AND is not required AND is not a PK).
        We always include NOT NULL columns and PK columns.
        """
        has_default = col["dflt_value"] is not None
        is_notnull  = bool(col["notnull"])
        is_pk       = bool(col["pk"])
        # Always include PKs and NOT NULL columns
        if is_pk or is_notnull:
            return False
        # Columns with defaults and no NOT NULL constraint can be skipped
        # BUT we include them anyway to make records more meaningful
        return False   # include everything — safer for test data richness

    def _generate_row(
        self,
        table: str,
        cols: list[dict],
        idx: int,
        schema_map: dict[str, list[dict]],
        auth_config: dict,
        tbl_lower: str,
        fk_cache: dict,
    ) -> list:
        """
        Generate one row of values for the given columns.
        Uses column name heuristics + MWO-specific special handling.
        """
        roles_cycle = ["HM", "TECH", "TECH"]
        pins_cycle  = [
            auth_config.get("hm_pin",   "1234"),
            auth_config.get("tech_pin", "2345"),
            auth_config.get("dm_pin",   "4567"),
        ]

        row = []
        for col in cols:
            cname  = col["name"].lower()
            ctype  = col["type"]   # already uppercased
            is_pk  = bool(col["pk"])

            val = self._value_for_column(
                cname, ctype, is_pk, idx, table, tbl_lower,
                roles_cycle, pins_cycle, schema_map, auth_config, fk_cache
            )
            row.append(val)
        return row

    def _value_for_column(
        self,
        cname: str,
        ctype: str,
        is_pk: bool,
        idx: int,
        table: str,
        tbl_lower: str,
        roles_cycle: list,
        pins_cycle: list,
        schema_map: dict,
        auth_config: dict,
        fk_cache: dict,
    ) -> Any:
        """
        Heuristic value generator for a single column.
        Uses fk_cache (real existing PKs) for FK resolution.
        """
        # ── PK columns ───────────────────────────────────────────────────────
        if is_pk:
            return self._generate_pk(cname, ctype, idx, table, tbl_lower)

        # ── PIN / password / hash ────────────────────────────────────────────
        if any(kw in cname for kw in ("pin_hash", "pin_code", "password_hash")):
            raw_pin = pins_cycle[idx % len(pins_cycle)]
            return self._bcrypt_or_dummy(raw_pin)

        if "pin" in cname and "hash" not in cname:
            return pins_cycle[idx % len(pins_cycle)]

        # ── Employee / User FK columns ───────────────────────────────────────
        if cname == "department_id":
            return self._fk_real("erp_departments", fk_cache, idx) or f"DEP-SEED{idx:03d}"

        if cname == "category_id":
            return self._fk_real("erp_categories", fk_cache, idx) or f"CAT-SEED{idx:03d}"

        if cname == "location_id":
            return self._fk_real("erp_locations", fk_cache, idx) or None

        if cname == "sku_id":
            return self._fk_real("erp_skus", fk_cache, idx) or f"SKU-SEED{idx:03d}"

        if cname in ("equipment_id", "asset_id") and tbl_lower != "erp_equipment":
            return self._fk_real("erp_equipment", fk_cache, idx) or None

        if cname == "part_id":
            return self._fk_real("erp_parts", fk_cache, idx) or f"PRT-SEED{idx:03d}"

        if cname == "reports_to_hm_id":
            return None  # optional FK — safe NULL

        if cname == "assigned_hm_id":
            # Try HM-specific cache first, then any employee
            hm_id = self._fk_real("erp_employees_hm", fk_cache, idx)
            if hm_id is None:
                hm_id = self._fk_real("erp_employees", fk_cache, idx)
            return hm_id  # may be None → will cause IntegrityError, caught per-row

        if cname in ("assigned_tech", "assigned_tech_id"):
            return None  # optional FK

        if cname in ("tech_id", "logged_by_tech_id", "actor_user_id"):
            return self._fk_real("erp_employees", fk_cache, idx) or f"SEED-EMP-001"

        if cname == "target_user_id":
            return self._fk_real("erp_employees", fk_cache, idx) or f"SEED-EMP-001"

        if cname == "mwo_id" and tbl_lower != "work_orders":
            return self._fk_real("work_orders", fk_cache, idx) or f"MWO-SEED{idx:03d}"

        # ── Role ─────────────────────────────────────────────────────────────
        if cname == "role":
            if "employee" in tbl_lower or "erp_employee" in tbl_lower:
                return roles_cycle[idx % len(roles_cycle)]
            return roles_cycle[idx % len(roles_cycle)]

        if cname == "authorization_level":
            return ["TECH", "MANAGER", "ADMIN"][idx % 3]

        # ── Status columns ────────────────────────────────────────────────────
        if cname == "status":
            if "work_order" in tbl_lower:
                statuses = ["UNASSIGNED", "ASSIGNED", "COMPLETED"]
                return statuses[idx % len(statuses)]
            if "equipment" in tbl_lower:
                return "ACTIVE"
            if "part" in tbl_lower:
                return "IN_STOCK"
            if "procurement" in tbl_lower:
                statuses = ["PENDING", "APPROVED", "FULFILLED"]
                return statuses[idx % len(statuses)]
            return "ACTIVE"

        # ── Common name patterns ──────────────────────────────────────────────
        if cname in ("name", "nomenclature"):
            label = table.replace("erp_", "").replace("_", " ").title()
            return f"Test {label} {idx + 1}"

        if cname in ("description", "notes", "manual_log", "comment", "resolution_notes",
                     "issue_description"):
            return f"Test data for {table} record {idx + 1}"

        if cname in ("dm_urgency", "hm_priority"):
            return "Normal"

        if "email" in cname:
            return f"test{idx + 1}@example.com"

        if "phone" in cname:
            return f"555-{1000 + idx:04d}"

        if any(kw in cname for kw in ("url", "path", "file", "archival_pdf")):
            return ""

        if any(kw in cname for kw in ("created_at", "updated_at", "timestamp",
                                       "triaged_at", "completed_at", "triggered_at",
                                       "start_date", "execution_start", "execution_end",
                                       "revoked_at", "transaction_timestamp")):
            return datetime.now().isoformat()

        if any(kw in cname for kw in ("count", "quantity", "qty", "stock_level",
                                       "quantity_on_hand", "authorized_quantity",
                                       "quantity_consumed", "reorder_threshold")):
            return idx + 1

        if any(kw in cname for kw in ("cost", "unit_cost", "material_cost",
                                       "labor_hours", "amount", "price")):
            return float(idx + 1)

        if "priority" in cname and "hm_" not in cname and "dm_" not in cname:
            return (idx % 3) + 1

        if "is_active" in cname or cname.startswith("is_"):
            return 1

        if "token_version" in cname:
            return 1

        if "attempt_timestamp" in cname:
            return int(datetime.now().timestamp())

        if any(kw in cname for kw in ("accumulated", "labor_seconds")):
            return 0.0

        # ── Type-based fallbacks ─────────────────────────────────────────────
        base_type = ctype.split("(")[0].strip()  # strip precision

        if base_type in ("INTEGER", "INT", "BIGINT", "SMALLINT"):
            return idx + 1

        if base_type in ("REAL", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL"):
            return float(idx + 1)

        if base_type in ("BOOLEAN", "BOOL", "BIT"):
            return 1

        if base_type in ("DATETIME", "DATE", "TIMESTAMP"):
            return datetime.now().isoformat()

        # TEXT / BLOB / everything else
        return f"test_{cname}_{idx + 1}"

    def _generate_pk(self, cname: str, ctype: str, idx: int, table: str, tbl_lower: str) -> Any:
        """Generate a unique PK value based on column name / type conventions."""
        # Integer PK: use high base to avoid conflicts
        base_type = ctype.split("(")[0].strip()
        if base_type in ("INTEGER", "INT", "BIGINT", "SMALLINT"):
            return 9000 + idx

        # Text PKs — use prefix conventions matching the app's own patterns
        prefix_map = {
            "erp_employees":         "SEED-EMP",
            "erp_equipment":         "SEED-EQ",
            "erp_categories":        "SEED-CAT",
            "erp_departments":       "SEED-DEP",
            "erp_locations":         "SEED-LOC",
            "erp_skus":              "SEED-SKU",
            "erp_parts":             "SEED-PRT",
            "erp_procurement_queue": "SEED-PROC",
            "erp_inventory_ledger":  "SEED-TXN",
            "mwo_consumed_parts":    "SEED-CONS",
            "work_orders":           "SEED-MWO",
            "users":                 "SEED-USR",
            "warehouse_inventory":   "SEED-WH",
            "department_dispatch_rules": "SEED-DDR",
            "user_audit_logs":       "SEED-AUD",
        }
        prefix = prefix_map.get(table, f"SEED-{table[:4].upper()}")
        return f"{prefix}-{idx + 1:03d}"

    def _bcrypt_or_dummy(self, raw_pin: str) -> str:
        """Return a bcrypt hash of raw_pin if bcrypt available, else a dummy."""
        try:
            import bcrypt
            return bcrypt.hashpw(raw_pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        except ImportError:
            # Return a dummy hash string that looks like a bcrypt hash
            return f"$2b$12$seedagentdummyhashXXXXX{raw_pin.zfill(4)}XXXXXXXXXXXXXXXXXX"

    def _fk_real(
        self, ref_table: str, fk_cache: dict, idx: int
    ) -> Optional[Any]:
        """
        Return a real existing PK from fk_cache for ref_table at circular index.
        Returns None if the table is not cached or is empty.
        """
        ids = fk_cache.get(ref_table, [])
        if not ids:
            return None
        return ids[idx % len(ids)]

    def _fk_lookup(
        self, ref_table: str, schema_map: dict, idx: int
    ) -> Optional[str]:
        """
        Legacy: return synthetic PK for ref_table.
        Prefer _fk_real when fk_cache is available.
        """
        if ref_table not in schema_map:
            return None
        cols = schema_map[ref_table]
        pk_cols = [c for c in cols if c["pk"]]
        if not pk_cols:
            return None
        pk = pk_cols[0]
        return self._generate_pk(pk["name"], pk["type"], 0, ref_table, ref_table.lower())

    # ── Phase 7: Save report ─────────────────────────────────────────────────

    def _save_report(self, report: SeedReport, run_id: str) -> None:
        out_dir  = _MAF_ROOT / "logs" / "qa_runs"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{run_id}_seed_report.json"
        payload  = asdict(report)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"[SeedAgent] Report saved to {out_path}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# __main__ smoke test
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    import json, os, sys

    # Force UTF-8 on Windows consoles
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    # Load app config from registry
    registry_path = _BRIDGE_DIR / "e2e_app_registry.json"
    with open(registry_path, encoding="utf-8") as f:
        registry = json.load(f)
    app_config = registry["apps"][0]

    # Try to load test plan
    plan_path = _MAF_ROOT / "logs" / "qa_runs" / "smoke_test_plan.json"
    test_plan = None
    if plan_path.exists():
        with open(plan_path, encoding="utf-8") as f:
            plan_data = json.load(f)

        class SimplePlan:
            pass

        test_plan = SimplePlan()
        test_plan.seed_requirements = plan_data.get("seed_requirements", {})
        print(f"[Smoke] Loaded test plan: {len(plan_data.get('test_cases', []))} test cases")
    else:
        print("[Smoke] No smoke_test_plan.json found — using schema heuristics only")

    print("=" * 60)
    print("SeedAgent Smoke Test — MWO ERP")
    print("=" * 60)

    agent  = SeedAgent()
    report = agent.seed(app_config, test_plan, "smoke_test")

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Success:          {report.success}")
    print(f"Tables seeded:    {report.tables_seeded}")
    print(f"Records inserted: {report.records_inserted}")
    print(f"Errors ({len(report.errors)}):")
    for e in report.errors:
        print(f"  - {e}")
    print()
    if report.seed_log:
        print("Seed log:")
        for entry in report.seed_log:
            e = entry if isinstance(entry, dict) else asdict(entry)
            print(f"  {e['table']}: {e['records_inserted']} records inserted")
            if e.get("sample"):
                sample_str = str(e["sample"])
                if len(sample_str) > 120:
                    sample_str = sample_str[:117] + "..."
                print(f"    sample: {sample_str}")
