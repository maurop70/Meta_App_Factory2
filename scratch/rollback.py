import sqlite3
conn = sqlite3.connect(r'C:\dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Maintenance_Work_Order\data\maintenance_erp.db')
cur = conn.cursor()
cur.execute("UPDATE work_orders SET status='PENDING_REVIEW', consumed_sku='SKU-PLM-002', manual_log='Pending approval for pipe replacement.' WHERE mwo_id='MWO-1004'")
conn.commit()
conn.close()
