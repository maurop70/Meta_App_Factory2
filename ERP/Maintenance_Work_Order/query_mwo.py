import sqlite3
db = sqlite3.connect('c:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/data/maintenance_erp.db')
print(db.cursor().execute("SELECT status, assigned_tech FROM work_orders WHERE mwo_id='MWO-OFFLINE-01'").fetchone())
