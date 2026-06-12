import bcrypt
import sqlite3

db = r'ERP\Module_0_Gateway\data\gateway_core.db'
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("SELECT emp_id, name, role, pin_hash FROM erp_employees ORDER BY emp_id")
users = cur.fetchall()
conn.close()

print("=== Checking known PINs against stored hashes ===\n")
test_pins = ['3456', '1234', '0000', '9999', '1111', '4321', '3000', '2000', '1000', '4000']

for emp_id, name, role, pin_hash in users:
    print(f"\n{emp_id} ({role}) — {name}")
    if not pin_hash:
        print("  NO HASH — skipping")
        continue
    h = pin_hash.encode()
    found = False
    for pin in test_pins:
        try:
            if bcrypt.checkpw(pin.encode(), h):
                print(f"  ✅ MATCH: PIN = {pin}")
                found = True
                break
        except Exception as e:
            print(f"  Error checking {pin}: {e}")
    if not found:
        print("  ❌ No match in test set")

print("\n=== Setting fresh PIN 3456 for all users ===")
new_hash = bcrypt.hashpw(b'3456', bcrypt.gensalt(12)).decode()
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("UPDATE erp_employees SET pin_hash = ?", (new_hash,))
conn.commit()
updated = cur.rowcount
conn.close()
print(f"Updated {updated} users → PIN is now 3456 for all")
