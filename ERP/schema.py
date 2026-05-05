import sqlite3
import os
db_path = os.path.join('C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order', 'data', 'maintenance_erp.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
for r in cursor.fetchall():
    print(r[0])
    print(r[1])
    print('---')
