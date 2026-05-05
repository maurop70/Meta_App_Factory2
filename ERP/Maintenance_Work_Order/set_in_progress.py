import sqlite3
db = sqlite3.connect('c:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/data/maintenance_erp.db')
db.cursor().execute("UPDATE work_orders SET status='IN_PROGRESS' WHERE mwo_id='MWO-OFFLINE-01'")
db.commit()
print("Updated to IN_PROGRESS")
