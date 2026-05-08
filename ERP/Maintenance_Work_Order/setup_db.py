import sqlite3
import uuid

conn = sqlite3.connect('data/maintenance_erp.db')
c = conn.cursor()

c.execute("SELECT * FROM erp_employees WHERE id='ERP-3000';")
print("ERP-3000:", c.fetchall())

# Let's insert ERP-3000 if not exists
c.execute("SELECT * FROM erp_employees WHERE id='ERP-3000';")
if not c.fetchall():
    c.execute("INSERT INTO erp_employees (id, name, role, pin_hash, is_active) VALUES ('ERP-3000', 'Test Tech', 'TECH', 'abc', 1);")
    conn.commit()
    print("Inserted ERP-3000")

# Update parts to IN_STOCK
c.execute("UPDATE erp_parts SET status='IN_STOCK' WHERE status='CONSUMED';")
# Also update sku quantity
c.execute("UPDATE erp_skus SET quantity_on_hand=quantity_on_hand+10;")
conn.commit()

c.execute("SELECT * FROM erp_parts LIMIT 5;")
print("Parts after update:", c.fetchall())

conn.close()
