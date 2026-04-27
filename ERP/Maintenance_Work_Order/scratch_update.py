import sqlite3
conn = sqlite3.connect('C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/data/maintenance_erp.db')
conn.execute("UPDATE erp_employees SET authorization_level='ADMIN' WHERE id='9999'")
conn.commit()
conn.close()
