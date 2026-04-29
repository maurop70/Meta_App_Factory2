import sqlite3
import bcrypt
conn = sqlite3.connect('data/maintenance_erp.db')
cursor = conn.cursor()
pin_hash = bcrypt.hashpw(b'1234', bcrypt.gensalt()).decode('utf-8')
cursor.execute("UPDATE erp_employees SET pin_hash = ? WHERE id = '9999'", (pin_hash,))
conn.commit()
conn.close()
print("PIN for 9999 set to 1234")
