"""
Idempotent migration: Dynamic Role Registry.

Transitions the ERP ledger from a hardcoded role whitelist to a dynamic role
registry so the Administrator can mint new roles at runtime:

  1. Create an `erp_roles` registry table and seed the six default roles.
  2. Rebuild `erp_employees` WITHOUT the static
     `CHECK(role IN ('ADMINISTRATOR', ...))` constraint, preserving every column,
     type, default, primary key, foreign key, and any attached index/trigger.

The migration runs across the live default database AND every isolated tenant
database under data/tenants/. The stale ERP-root copy of maintenance_erp.db is
deliberately NEVER touched -- only data/maintenance_erp.db is authoritative.

Idempotent & re-runnable:
  * erp_roles is created IF NOT EXISTS; seeds use INSERT OR IGNORE.
  * The rebuild is skipped for any DB whose erp_employees no longer carries the
    role CHECK constraint (already migrated) -- it never rebuilds twice.

Each DB is backed up (archives/<db>.pre_dynamic_roles.<ts>.db) before any
mutation, and its rebuild runs inside a single transaction with row-count
verification, so a mid-rebuild failure rolls back to the intact original.

Run from anywhere; paths resolve relative to this file.
"""
import glob
import os
import re
import shutil
import sqlite3
import sys
import time
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_HERE, "data")
_ARCHIVES_DIR = os.path.join(_HERE, "archives")

# Matches the inline `CHECK(role IN (...))` clause regardless of spacing/quoting
# of the listed values. The inner role list contains no nested parentheses.
_ROLE_CHECK_RE = re.compile(r"\s*CHECK\s*\(\s*role\s+IN\s*\([^)]*\)\s*\)", re.IGNORECASE)


def target_databases():
    """Authoritative migration targets: the live default DB plus every tenant DB.

    Excludes the stale ERP-root maintenance_erp.db by construction -- only the
    Maintenance_Work_Order/data tree is enumerated.
    """
    targets = []
    default_db = os.path.join(_DATA_DIR, "maintenance_erp.db")
    if os.path.exists(default_db):
        targets.append(default_db)
    targets.extend(sorted(glob.glob(os.path.join(_DATA_DIR, "tenants", "tenant_*.db"))))
    return targets


def _backup(db_path):
    """Timestamped pre-migration snapshot, matching the archives/ convention."""
    os.makedirs(_ARCHIVES_DIR, exist_ok=True)
    stem = os.path.splitext(os.path.basename(db_path))[0]
    dest = os.path.join(_ARCHIVES_DIR, f"{stem}.pre_dynamic_roles.{int(time.time())}.db")
    shutil.copy2(db_path, dest)
    return dest


def _ensure_roles_table(cursor):
    """Ensure the registry TABLE exists. Row seeding is owned solely by
    local_db.seed_canonical_baseline -- this migration no longer seeds."""
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS erp_roles ("
        "role_name TEXT PRIMARY KEY, description TEXT)"
    )


def _fk_violation_signature(cursor):
    """A multiset of (child_table, parent_table, fk_index) for every current FK
    violation. Row ids are deliberately excluded: the rebuild reassigns
    erp_employees rowids, so only the (table, parent, fk) shape is comparable
    across the swap."""
    rows = cursor.execute("PRAGMA foreign_key_check").fetchall()
    # PRAGMA foreign_key_check columns: (table, rowid, referred_table, fk_id)
    return Counter((r[0], r[2], r[3]) for r in rows)


def _employees_create_sql(cursor):
    row = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='erp_employees'"
    ).fetchone()
    return row[0] if row else None


def _build_new_table_sql(original_sql):
    """Produce the erp_employees_new DDL: identical schema minus the role CHECK.

    Only the table name in the CREATE clause is renamed; the self-referencing
    `REFERENCES erp_employees(id)` foreign key text is intentionally left as-is so
    that, after the drop+rename, it resolves back to the table itself.
    """
    # Strip the role CHECK constraint (and only that constraint).
    new_sql = _ROLE_CHECK_RE.sub("", original_sql)
    # Rename only the defined table (the token immediately after CREATE TABLE),
    # tolerating optional IF NOT EXISTS and "/`/[ quoting around the name.
    new_sql, n = re.subn(
        r'(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)(["`\[]?)erp_employees(["`\]]?)',
        r'\1"erp_employees_new"',
        new_sql,
        count=1,
        flags=re.IGNORECASE,
    )
    if n != 1:
        raise RuntimeError("Could not locate erp_employees in CREATE TABLE statement")
    return new_sql


def _rebuild_employees(conn, cursor):
    """Rebuild erp_employees without the role CHECK. Returns True if rebuilt,
    False if the table was already migrated (CHECK absent)."""
    original_sql = _employees_create_sql(cursor)
    if original_sql is None:
        print("    [SKIP] erp_employees table absent; nothing to rebuild.")
        return False

    if not _ROLE_CHECK_RE.search(original_sql):
        print("    [SKIP] erp_employees already rebuilt (role CHECK absent).")
        return False

    new_sql = _build_new_table_sql(original_sql)

    # Columns to carry over (identical on both tables; explicit list keeps the
    # copy stable regardless of column order).
    cols = [r[1] for r in cursor.execute("PRAGMA table_info(erp_employees)").fetchall()]
    col_list = ", ".join(f'"{c}"' for c in cols)

    # Indexes & triggers attached to the original table that carry their own DDL
    # (the PK autoindex has sql IS NULL and is recreated by the new table's PK).
    attached = cursor.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE tbl_name='erp_employees' AND type IN ('index','trigger') "
        "AND sql IS NOT NULL"
    ).fetchall()

    before = cursor.execute("SELECT COUNT(*) FROM erp_employees").fetchone()[0]

    cursor.execute(new_sql)
    cursor.execute(
        f"INSERT INTO erp_employees_new ({col_list}) SELECT {col_list} FROM erp_employees"
    )
    cursor.execute("DROP TABLE erp_employees")
    cursor.execute("ALTER TABLE erp_employees_new RENAME TO erp_employees")

    # Recreate any user indexes / triggers that were dropped with the old table.
    for _type, name, sql in attached:
        cursor.execute(sql)
        print(f"    Recreated {_type}: {name}")

    after = cursor.execute("SELECT COUNT(*) FROM erp_employees").fetchone()[0]
    if before != after:
        raise RuntimeError(
            f"ROW COUNT MISMATCH after rebuild: before={before} after={after}"
        )

    print(f"    Rebuilt erp_employees without role CHECK ({after} rows preserved).")
    return True


def _migrate_db(db_path):
    print(f"\n>>> Migrating: {db_path}")
    backup = _backup(db_path)
    print(f"    Backup: {backup}")

    conn = sqlite3.connect(db_path)
    conn.isolation_level = None  # explicit transaction control
    cursor = conn.cursor()
    # FK enforcement must be toggled OUTSIDE a transaction; off during the
    # table-swap so the transient self-FK to the dropped table is not enforced.
    cursor.execute("PRAGMA foreign_keys=OFF")
    try:
        cursor.execute("BEGIN")
        # Baseline FK state: the live DB carries historical orphans (FKs were not
        # enforced at insert time). We only fail if the rebuild INTRODUCES new
        # breakage, not for pre-existing orphans outside this migration's scope.
        baseline = _fk_violation_signature(cursor)
        _ensure_roles_table(cursor)
        _rebuild_employees(conn, cursor)
        # Integrity gate: abort only on FK violations the rebuild itself added.
        after = _fk_violation_signature(cursor)
        introduced = after - baseline  # Counter subtraction keeps only increases
        if introduced:
            raise RuntimeError(f"rebuild introduced FK violations: {dict(introduced)}")
        if baseline:
            preexisting = ", ".join(
                f"{c}x {child}->{parent}(fk{fk})" for (child, parent, fk), c in baseline.items()
            )
            print(f"    [NOTE] pre-existing FK orphans preserved (out of scope): {preexisting}")
        cursor.execute("COMMIT")
        print("    [OK] Committed.")
    except Exception as e:
        cursor.execute("ROLLBACK")
        print(f"    [ABORT] {db_path} rolled back: {e}")
        print(f"    [ABORT] Original DB is intact; snapshot at {backup}")
        raise
    finally:
        cursor.execute("PRAGMA foreign_keys=ON")
        conn.close()


def _reconcile_default_registry():
    """Atomically reconcile the default DB registry to canonical-6: seed canonical
    rows, then drop the ADMIN/TECHNICIAN alias rows. If an alias is still HELD by an
    employee, ROLL BACK and RAISE -- WS-A1 never mutates employee data, and 'fail-loud'
    must mean 'no partial mutation' (the DB is left exactly as found). Reuses
    CANONICAL_ROLE_DEFS (single source of truth) rather than the auto-committing
    seed_canonical_baseline so the whole reconcile shares one commit boundary."""
    from local_db import CANONICAL_ROLE_DEFS
    db = os.path.join(_DATA_DIR, "maintenance_erp.db")
    if not os.path.exists(db):
        print("    [WARN] default DB not found; registry reconcile skipped.")
        return
    conn = sqlite3.connect(db)
    conn.isolation_level = None  # explicit transaction control
    cur = conn.cursor()
    try:
        cur.execute("BEGIN")
        cur.execute("CREATE TABLE IF NOT EXISTS erp_roles (role_name TEXT PRIMARY KEY, description TEXT)")
        cur.executemany(
            "INSERT OR IGNORE INTO erp_roles (role_name, description) VALUES (?, ?)",
            CANONICAL_ROLE_DEFS,
        )
        for alias in ("ADMIN", "TECHNICIAN"):
            held = cur.execute(
                "SELECT COUNT(*) FROM erp_employees WHERE role=?", (alias,)
            ).fetchone()[0]
            if held:
                raise RuntimeError(
                    f"Default DB has {held} employee(s) holding alias role '{alias}'. "
                    f"WS-A1 will not mutate employee data -- reassign them, then re-run."
                )
            cur.execute("DELETE FROM erp_roles WHERE role_name=?", (alias,))
        cur.execute("COMMIT")
        print("    [OK] default-DB registry reconciled to canonical-6.")
    except Exception:
        cur.execute("ROLLBACK")  # undoes the canonical seed + any alias delete already done
        raise
    finally:
        conn.close()


def _reconcile_gateway_roles():
    """Data-only: collapse the legacy TECHNICIAN label to canonical TECH in the shared
    gateway identity store. Reuses the app's authoritative GATEWAY_DB_PATH so it mutates
    the exact file the running app reads. (Ingest-side input normalization is OUT of
    WS-A1 scope -- handed to WS-A2.)"""
    from local_db import GATEWAY_DB_PATH
    if not os.path.exists(GATEWAY_DB_PATH):
        print("    [WARN] gateway DB not found; TECHNICIAN->TECH skipped.")
        return
    backup = _backup(GATEWAY_DB_PATH)  # mirror the migration's snapshot convention
    print(f"    Gateway backup: {backup}")
    conn = sqlite3.connect(GATEWAY_DB_PATH)
    try:
        n = conn.execute("UPDATE erp_employees SET role='TECH' WHERE role='TECHNICIAN'").rowcount
        conn.commit()
        print(f"    [OK] gateway TECHNICIAN->TECH reconciled ({n} row(s)).")
    finally:
        conn.close()


def run():
    targets = target_databases()
    print("Dynamic-roles migration targets:")
    default_db = os.path.join(_DATA_DIR, "maintenance_erp.db")
    if not os.path.exists(default_db):
        print(f"  [WARN] default DB not found: {default_db}")
    tenant_dbs = [t for t in targets if t != default_db]
    print(f"  default : {default_db if os.path.exists(default_db) else '(missing)'}")
    if tenant_dbs:
        for t in tenant_dbs:
            print(f"  tenant  : {t}")
    else:
        print("  tenant  : (none found; tenant branch is a no-op)")

    if not targets:
        print("No target databases found; nothing to do.")
        return

    failures = []
    for db_path in targets:
        try:
            _migrate_db(db_path)
        except Exception:
            failures.append(db_path)

    # TODO(WS-B1a-review): the per-DB pass above surfaces pre-existing FK orphans in
    # the TEMPLATE default DB (1x erp_employees->erp_departments fk1, 1x
    # work_orders->erp_employees fk4). They are out of WS-A1 scope, but the
    # work_orders->erp_employees orphan matters once identity is re-homed per-tenant:
    # the template is cloned into Tenant 1, so the dangling reference must be resolved
    # before that clone, not after.
    # Post-migration reconciliations (fail-loud: a held-alias raise halts the run).
    print("\n>>> Reconciling default-DB registry to canonical-6")
    _reconcile_default_registry()
    print("\n>>> Reconciling gateway identity store (TECHNICIAN -> TECH)")
    _reconcile_gateway_roles()

    print("\n=== Summary ===")
    print(f"  Migrated OK : {len(targets) - len(failures)}/{len(targets)}")
    if failures:
        print("  FAILED      :")
        for f in failures:
            print(f"    - {f}")
        sys.exit(1)


if __name__ == "__main__":
    run()
