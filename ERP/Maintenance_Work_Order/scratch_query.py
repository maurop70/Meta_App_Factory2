import sqlite3
conn = sqlite3.connect('C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/data/maintenance_erp.db')
cursor = conn.cursor()
cursor.execute("SELECT pin_code, name, authorization_level FROM erp_employees WHERE authorization_level IN ('ADMIN', 'ADMINISTRATOR')")
for row in cursor.fetchall():
    print(row)
