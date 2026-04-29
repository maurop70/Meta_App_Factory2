import sqlite3
conn = sqlite3.connect('data/maintenance_erp.db')
cursor = conn.cursor()
cursor.execute("SELECT id, name, authorization_level FROM erp_employees")
for row in cursor.fetchall():
    print(row)
conn.close()
