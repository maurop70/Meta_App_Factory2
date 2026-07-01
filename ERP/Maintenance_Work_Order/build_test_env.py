"""
WS-A2 SP2 — Test-Environment (Tenant 1) provisioning.

ONE reversible, all-or-nothing operation: back up both stores, then atomically
CLEANUP the old test records (ERP-1000 admin preserved) and BUILD the clean world
(5 departments, 7 people with logins, capabilities, department-tagged inventory,
the ERP-5000 orphan re-homed into the new CFO). Any failure restores both DBs from
the pre-operation backups (file-level rollback across the two SQLite files).

Reusable pattern: the DEPTS / PEOPLE / CAPS / CATEGORIES / SKUS tables below are the
template for provisioning Tenant 2 later — swap the data, keep the machinery.

Idempotent: a re-run deletes nothing new and inserts nothing new (existence-checked +
INSERT OR IGNORE), and never regenerates a PIN for an already-provisioned person.

Names (Option A, confirmed): the employee ledger stores the single combined `name`;
the gateway/login store splits it into first/last via the app's own _split_name and
displays the full name on login. No schema/code change.
"""
import os, sys, time, shutil, secrets, sqlite3

_HERE = os.path.dirname(os.path.abspath(__file__))
ERP_DB = os.path.join(_HERE, "data", "maintenance_erp.db")
ARCHIVES = os.path.join(_HERE, "archives")
CREDS_DIR = os.environ.get("TEST_ENV_CREDS_DIR", _HERE)  # override to a temp dir for out-of-repo creds

# The app's authoritative gateway-login dual-write + name splitter (no parallel copy).
import maintenance_backend as mb          # noqa: E402  (import runs init_tables on default DB; idempotent)
from local_db import GATEWAY_DB_PATH      # noqa: E402

# ---------------------------------------------------------------------------
# TEMPLATE DATA (swap for Tenant 2)
# ---------------------------------------------------------------------------
DEPTS = [("DEPT-PROD", "Production"), ("DEPT-MAINT", "Maintenance"),
         ("DEPT-ADMIN", "Administration"), ("DEPT-OPS", "Operation"), ("DEPT-QA", "QA")]

# (id, full_name, base_role, department_id)
PEOPLE = [
    ("U-BEDOYA",  "Dousander Bedoya", "DM",   "DEPT-PROD"),
    ("U-PEREZ",   "Cesar Perez",      "DM",   "DEPT-MAINT"),
    ("U-CASTRO",  "Monica Castro",    "DM",   "DEPT-ADMIN"),
    ("U-DELPINO", "Tomas Delpino",    "DM",   "DEPT-OPS"),
    ("U-MATTSON", "Raymond Mattson",  "TECH", "DEPT-MAINT"),
    ("U-ROSALES", "Karen Rosales",    "DM",   "DEPT-QA"),
    ("U-PASTORI", "Diego Pastori",    "CFO",  "DEPT-ADMIN"),  # dept nominal; PARTS_APPROVER is tenant-wide
]

# (employee_id, capability, department_id)   '*' = tenant-wide
CAPS = [
    ("U-BEDOYA",  "REQUESTER",      "DEPT-PROD"),
    ("U-PEREZ",   "REQUESTER",      "DEPT-MAINT"),
    ("U-PEREZ",   "PLANNER",        "DEPT-MAINT"),
    ("U-PEREZ",   "STOREKEEPER",    "DEPT-MAINT"),
    ("U-CASTRO",  "STOREKEEPER",    "DEPT-ADMIN"),
    ("U-DELPINO", "REQUESTER",      "DEPT-OPS"),
    ("U-ROSALES", "STOREKEEPER",    "DEPT-QA"),
    ("U-ROSALES", "REQUESTER",      "DEPT-QA"),
    ("U-PASTORI", "PARTS_APPROVER", "*"),
    # U-MATTSON: none
]

# (id, name, department_id, manager_id)
CATEGORIES = [
    ("CAT-ADMIN-OFFICE", "Administration Office Supplies", "DEPT-ADMIN", "U-CASTRO"),
    ("CAT-MAINT-PARTS",  "Maintenance Parts",             "DEPT-MAINT", "U-PEREZ"),
]

# (sku_id, nomenclature, category_id, qty, reorder_threshold, unit_cost, supplier_id, moq)
SKUS = [
    ("SKU-ADM-PAPER",  "A4 Paper Ream",            "CAT-ADMIN-OFFICE", 50, 20, 4.50,  "SUP-ADMIN-01", 5),
    ("SKU-ADM-STAPLE", "Staples Box",              "CAT-ADMIN-OFFICE", 30, 10, 1.20,  "SUP-ADMIN-01", 5),
    ("SKU-ADM-PEN",    "Ballpoint Pens (12pk)",    "CAT-ADMIN-OFFICE",  8, 10, 3.00,  "SUP-ADMIN-01", 5),  # low
    ("SKU-ADM-GLOVE",  "Nitrile Gloves (100)",     "CAT-ADMIN-OFFICE", 15,  8, 6.00,  "SUP-ADMIN-01", 4),
    ("SKU-ADM-FOLDER", "File Folders (25)",        "CAT-ADMIN-OFFICE", 40, 15, 2.75,  "SUP-ADMIN-01", 5),
    ("SKU-ADM-INK",    "Printer Ink Cartridge",    "CAT-ADMIN-OFFICE",  6,  8, 18.00, "SUP-ADMIN-01", 2),  # low
    ("SKU-ADM-TAPE",   "Packing Tape",             "CAT-ADMIN-OFFICE", 22, 10, 1.90,  "SUP-ADMIN-01", 6),
    ("SKU-ADM-MARKER", "Whiteboard Markers (4)",   "CAT-ADMIN-OFFICE", 18, 10, 4.20,  "SUP-ADMIN-01", 4),
    ("SKU-ADM-NOTE",   "Notepads (10)",            "CAT-ADMIN-OFFICE", 35, 12, 5.50,  "SUP-ADMIN-01", 5),
    ("SKU-MNT-SPRING", "Compression Spring",       "CAT-MAINT-PARTS",  40, 15, 2.10,  "SUP-MAINT-01", 10),
    ("SKU-MNT-SENSOR", "Proximity Sensor",         "CAT-MAINT-PARTS",   6, 10, 22.00, "SUP-MAINT-01", 3),  # low
    ("SKU-MNT-VALVE1", "Valve Type-1",             "CAT-MAINT-PARTS",  18,  8, 14.00, "SUP-MAINT-01", 4),
    ("SKU-MNT-VALVE2", "Valve Type-2",             "CAT-MAINT-PARTS",  12,  8, 16.50, "SUP-MAINT-01", 4),
    ("SKU-MNT-BELT",   "Conveyor Belt 2m",         "CAT-MAINT-PARTS",   5,  5, 80.00, "SUP-MAINT-01", 2),  # low (<=)
    ("SKU-MNT-BEARING","Ball Bearing",             "CAT-MAINT-PARTS",  30, 12, 3.30,  "SUP-MAINT-01", 8),
    ("SKU-MNT-GASKET", "Gasket Set",               "CAT-MAINT-PARTS",  25, 10, 7.75,  "SUP-MAINT-01", 5),
    ("SKU-MNT-BOLT",   "Bolt Kit (50)",            "CAT-MAINT-PARTS",  60, 20, 9.90,  "SUP-MAINT-01", 6),
    ("SKU-MNT-LUBE",   "Industrial Lubricant 1L",  "CAT-MAINT-PARTS",   9, 10, 12.40, "SUP-MAINT-01", 3),  # low
]

# Old test records to remove (ERP-1000 admin is NOT in any of these).
OLD_DEPTS = ["DEPT-ELEC", "DEPT-MECH"]
OLD_EMPS  = ["ERP-4000", "ERP-1030", "U-5FCDE1", "ERP-1029", "ERP-3000", "U-F0FB1C", "ERP-5000"]
OLD_CATS  = ["CAT-ADMIN", "CAT-MAINT", "CAT-MOTORS", "CAT-SENSORS"]
OLD_SKUS  = ["SKU-9901", "SKU-9902", "SKU-ADM-001", "SKU-ADM-002", "SKU-ADM-003", "SKU-ADM-004", "SKU-ID-9010"]
OLD_GW_EMPS = ["ERP-2000", "ERP-3000", "ERP-4000", "ERP-5000", "U-5FCDE1", "U-F0FB1C"]  # gateway; ERP-1000 preserved
ADMIN_ID = "ERP-1000"
SUPPLIERS = [("SUP-ADMIN-01", "Office Supplies Co"), ("SUP-MAINT-01", "Maintenance Parts Ltd")]


def _backup(path, tag):
    os.makedirs(ARCHIVES, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    dest = os.path.join(ARCHIVES, f"{stem}.{tag}.{int(time.time())}.db")
    shutil.copy2(path, dest)
    return dest, os.path.getsize(dest)


def _q(cur, sql, *a):
    return cur.execute(sql, a).fetchone()


def run():
    import bcrypt

    # 1. BACKUP both stores (rollback point).
    erp_bak, erp_sz = _backup(ERP_DB, "pre_test_env")
    gw_bak, gw_sz = _backup(GATEWAY_DB_PATH, "pre_test_env")
    print(f"[BACKUP] ERP     : {erp_bak} ({erp_sz} bytes)")
    print(f"[BACKUP] GATEWAY : {gw_bak} ({gw_sz} bytes)")

    creds = []  # (id, name, dept, role, pin) for newly-provisioned people only
    try:
        # ================= ERP DB (atomic) =================
        conn = sqlite3.connect(ERP_DB)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        cur = conn.cursor()
        if not _q(cur, "SELECT 1 FROM erp_employees WHERE id=?", ADMIN_ID):
            raise RuntimeError(f"Admin {ADMIN_ID} missing from ledger BEFORE cleanup — aborting.")
        cur.execute("BEGIN")

        # --- CLEANUP (FK-safe order; scoped to old ids / build-untouched tables) ---
        cur.execute("DELETE FROM mwo_consumed_parts")
        cur.execute("DELETE FROM erp_purchase_order_items")
        cur.execute("DELETE FROM erp_purchase_orders")
        cur.execute("DELETE FROM work_orders")
        cur.execute("DELETE FROM erp_equipment")
        cur.execute("DELETE FROM erp_parts")
        cur.executemany("DELETE FROM erp_skus WHERE sku_id=?", [(s,) for s in OLD_SKUS])
        cur.executemany("DELETE FROM erp_employee_capabilities WHERE employee_id=?", [(e,) for e in OLD_EMPS])
        cur.executemany("DELETE FROM erp_categories WHERE id=?", [(c,) for c in OLD_CATS])
        # Break the self-referential reports_to_hm_id chain (e.g. U-F0FB1C -> U-5FCDE1,
        # both old) so the employee deletes don't trip the self-FK regardless of order.
        cur.execute("UPDATE erp_employees SET reports_to_hm_id=NULL WHERE reports_to_hm_id IN (%s)"
                    % ",".join("?" * len(OLD_EMPS)), OLD_EMPS)
        cur.executemany("DELETE FROM erp_employees WHERE id=?", [(e,) for e in OLD_EMPS])   # ERP-1000 not listed
        cur.executemany("DELETE FROM erp_departments WHERE id=?", [(d,) for d in OLD_DEPTS])

        # --- BUILD ---
        cur.executemany("INSERT OR IGNORE INTO erp_suppliers (supplier_id, name) VALUES (?, ?)", SUPPLIERS)
        cur.executemany("INSERT OR IGNORE INTO erp_departments (id, name) VALUES (?, ?)", DEPTS)

        provisioned = []  # (id, name, role, pin_hash, dept)
        for pid, name, role, dept in PEOPLE:
            if _q(cur, "SELECT 1 FROM erp_employees WHERE id=?", pid):
                continue  # idempotent: never regenerate a PIN for an existing person
            pin = f"{secrets.randbelow(9000) + 1000}"  # 4-digit
            pin_hash = bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()
            cur.execute(
                "INSERT INTO erp_employees (id, name, role, pin_hash, is_active, department_id, is_inventory_manager) "
                "VALUES (?, ?, ?, ?, 1, ?, 0)", (pid, name, role, pin_hash, dept))
            provisioned.append((pid, name, role, pin_hash, dept))
            creds.append((pid, name, dept, role, pin))

        cur.executemany(
            "INSERT OR IGNORE INTO erp_categories (id, name, department_id, manager_id) VALUES (?, ?, ?, ?)", CATEGORIES)
        cur.executemany(
            "INSERT OR IGNORE INTO erp_skus (sku_id, nomenclature, category_id, quantity_on_hand, reorder_threshold, unit_cost, supplier_id, min_order_qty) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7]) for s in SKUS])
        cur.executemany(
            "INSERT OR IGNORE INTO erp_employee_capabilities (employee_id, capability, department_id) VALUES (?, ?, ?)", CAPS)

        # --- ERP ASSERTIONS (inside txn; any failure -> rollback+restore) ---
        assert _q(cur, "SELECT 1 FROM erp_employees WHERE id=?", ADMIN_ID), "ERP-1000 vanished"
        assert _q(cur, "SELECT COUNT(*) FROM erp_departments WHERE id IN (%s)" % ",".join("?"*5),
                  *[d[0] for d in DEPTS])[0] == 5, "5 new depts"
        assert _q(cur, "SELECT COUNT(*) FROM erp_departments WHERE id IN ('DEPT-ELEC','DEPT-MECH')")[0] == 0, "old depts gone"
        assert _q(cur, "SELECT COUNT(*) FROM erp_employees WHERE id IN (%s)" % ",".join("?"*7),
                  *[p[0] for p in PEOPLE])[0] == 7, "7 people"
        assert _q(cur, "SELECT COUNT(*) FROM erp_employee_capabilities")[0] == len(CAPS), "cap count exact"
        # every test SKU resolves to exactly one department
        bad = _q(cur, "SELECT COUNT(*) FROM erp_skus s LEFT JOIN erp_categories c ON c.id=s.category_id "
                       "WHERE s.category_id IS NULL OR c.department_id IS NULL")[0]
        assert bad == 0, f"{bad} test SKU(s) do not resolve to a department"
        # orphans: no employee points at a missing department; no '*' department
        orph = _q(cur, "SELECT COUNT(*) FROM erp_employees WHERE department_id IS NOT NULL "
                        "AND department_id NOT IN (SELECT id FROM erp_departments)")[0]
        assert orph == 0, f"{orph} employee(s) reference a missing department"
        assert _q(cur, "SELECT COUNT(*) FROM erp_departments WHERE id='*'")[0] == 0, "sentinel dept"
        fk = cur.execute("PRAGMA foreign_key_check").fetchall()
        assert not fk, f"foreign_key_check not clean: {fk[:5]}"

        conn.commit()
        conn.close()

        # ================= GATEWAY (login store) =================
        gw = sqlite3.connect(GATEWAY_DB_PATH)
        gw.row_factory = sqlite3.Row
        if not gw.execute("SELECT 1 FROM erp_employees WHERE emp_id=?", (ADMIN_ID,)).fetchone():
            raise RuntimeError(f"Admin {ADMIN_ID} missing from gateway — aborting.")
        gw.executemany("DELETE FROM erp_employees WHERE emp_id=?", [(e,) for e in OLD_GW_EMPS])  # ERP-1000 preserved
        gw.commit()
        gw.close()

        dept_names = dict(DEPTS)
        for pid, name, role, pin_hash, dept in provisioned:
            mb.sync_employee_to_gateway(pid, name, role, pin_hash,
                                        department_id=dept, department_name=dept_names.get(dept),
                                        is_inventory_manager=0)

        # --- GATEWAY ASSERTIONS ---
        gw = sqlite3.connect(GATEWAY_DB_PATH); gw.row_factory = sqlite3.Row
        assert gw.execute("SELECT 1 FROM erp_employees WHERE emp_id=?", (ADMIN_ID,)).fetchone(), "gateway admin gone"
        got = gw.execute("SELECT COUNT(*) FROM erp_employees WHERE emp_id IN (%s)" % ",".join("?"*7),
                         [p[0] for p in PEOPLE]).fetchone()[0]
        assert got == 7, f"gateway has {got}/7 test logins"
        assert gw.execute("SELECT COUNT(*) FROM erp_employees WHERE emp_id IN (%s)" % ",".join("?"*len(OLD_GW_EMPS)),
                          OLD_GW_EMPS).fetchone()[0] == 0, "old gateway rows remain"
        gw.close()

        # ================= CREDENTIALS (out of chat) =================
        creds_path = os.path.join(CREDS_DIR, "test_env_credentials.txt")
        if creds:
            with open(creds_path, "w", encoding="utf-8") as f:
                f.write("WS-A2 Tenant 1 test logins — DISTRIBUTE THEN DELETE. First login prompts activation.\n")
                f.write("USER_ID | FULL_NAME | DEPARTMENT | BASE_ROLE | TEMP_PIN\n")
                for cid, cname, cdept, crole, cpin in creds:
                    f.write(f"{cid} | {cname} | {cdept} | {crole} | {cpin}\n")
            print(f"[CREDENTIALS] {creds_path} ({len(creds)} new login(s))")
        else:
            print("[CREDENTIALS] no new people provisioned (idempotent re-run) — no file written.")

        print("[OK] Test environment built.")
        return {"erp_backup": erp_bak, "gw_backup": gw_bak, "provisioned": len(creds),
                "creds_path": creds_path if creds else None}

    except Exception as e:
        # File-level rollback of BOTH stores — never a partial world.
        shutil.copy2(erp_bak, ERP_DB)
        shutil.copy2(gw_bak, GATEWAY_DB_PATH)
        print(f"[ROLLBACK] {type(e).__name__}: {e}")
        print(f"[ROLLBACK] Restored ERP + gateway from backups. State is exactly as before.")
        raise


if __name__ == "__main__":
    run()
