import sqlite3
db = sqlite3.connect('c:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Module_0_Gateway/data/gateway_core.db')
print(db.cursor().execute("SELECT * FROM erp_employees WHERE emp_id='ERP-1000'").fetchone())
