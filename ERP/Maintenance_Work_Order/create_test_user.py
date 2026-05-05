import sqlite3
import bcrypt

conn = sqlite3.connect('data/maintenance_erp.db')
cursor = conn.cursor()

pin_hash = bcrypt.hashpw(b'1234', bcrypt.gensalt()).decode('utf-8')
cursor.execute("INSERT OR REPLACE INTO erp_employees (id, name, role, pin_hash) VALUES ('ERP-1029', 'Test User 1029', 'ADMIN', ?)", (pin_hash,))
conn.commit()
conn.close()
