import sqlite3
conn = sqlite3.connect('C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/data/maintenance_erp.db')
print(conn.execute("SELECT user_id, role FROM users").fetchall())
