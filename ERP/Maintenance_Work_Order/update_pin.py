import sqlite3
import bcrypt

h = bcrypt.hashpw('1234'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
conn = sqlite3.connect('data/maintenance_erp.db')
c = conn.cursor()
c.execute("UPDATE erp_employees SET pin_hash=? WHERE id='ERP-1000'", (h,))
conn.commit()
conn.close()
print("Updated PIN for ERP-1000 to 1234")
