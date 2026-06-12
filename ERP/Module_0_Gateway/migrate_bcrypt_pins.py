"""
One-time migration: hash any un-hashed plain-text PINs, then null out the pin column.
Safe to run multiple times (idempotent).
"""
import sqlite3
import bcrypt
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "gateway_core.db"


def run():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT id, pin, pin_hash FROM erp_employees")
    rows = cur.fetchall()

    hashed = 0
    for row in rows:
        pin = row["pin"]
        pin_hash = row["pin_hash"]

        if pin and not pin_hash:
            new_hash = bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            cur.execute("UPDATE erp_employees SET pin_hash = ? WHERE id = ?", (new_hash, row["id"]))
            hashed += 1
            print(f"  Hashed PIN for id={row['id']}")

    # Null out plain-text pins for all rows
    cur.execute("UPDATE erp_employees SET pin = NULL")
    conn.commit()
    conn.close()

    print(f"Migration complete. Newly hashed: {hashed}. Plain-text pins cleared.")


if __name__ == "__main__":
    run()
