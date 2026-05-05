import sqlite3
import bcrypt

conn = sqlite3.connect('data/maintenance_erp.db')
cursor = conn.cursor()

# Set all pins to 1234
pin_hash = bcrypt.hashpw(b'1234', bcrypt.gensalt()).decode('utf-8')
cursor.execute("UPDATE erp_employees SET pin_hash = ?", (pin_hash,))
conn.commit()

cursor.execute("SELECT id, name, role FROM erp_employees LIMIT 10")
for row in cursor.fetchall():
    print(row)
conn.close()
