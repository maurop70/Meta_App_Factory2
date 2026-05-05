import sqlite3
db = sqlite3.connect('c:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/data/maintenance_erp.db')
db.row_factory = sqlite3.Row
cols = "mwo_id, status, dm_urgency, hm_priority, description, assigned_tech, consumed_sku, manual_log, created_at, triaged_at, execution_start, execution_end, completed_at, start_date, equipment_id, location_id, material_cost, archival_pdf_path"
rows = db.cursor().execute(f"SELECT {cols} FROM work_orders WHERE assigned_tech = 'ERP-1000' AND status IN ('ASSIGNED', 'IN_PROGRESS', 'PAUSED', 'PENDING_REVIEW', 'COMPLETED') ORDER BY mwo_id DESC LIMIT 50 OFFSET 0").fetchall()
print([dict(r) for r in rows])
