import sqlite3
import os
db_path = os.path.join('C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Module_0_Gateway', 'data', 'gateway_core.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT * FROM erp_employees WHERE role = 'HM'")
for r in cursor.fetchall():
    print(r)
