import asyncio
import sqlite3
import sys
import os

sys.path.insert(0, 'C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order')
from maintenance_backend import archive_completed_mwo

conn = sqlite3.connect('C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/data/maintenance_erp.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT mwo_id, status, dm_urgency, hm_priority, description, assigned_tech, consumed_sku, manual_log, created_at, triaged_at, execution_start, execution_end, completed_at, start_date, equipment_id, location_id, material_cost, archival_pdf_path FROM work_orders WHERE status='COMPLETED'")
rows = c.fetchall()
for row in rows:
    asyncio.run(archive_completed_mwo(dict(row)))
