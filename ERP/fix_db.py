import sqlite3, time
conn = sqlite3.connect(r'c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Maintenance_Work_Order\data\maintenance_erp.db')
conn.execute('UPDATE work_orders SET status=''IN_PROGRESS'', execution_start=' + str(time.time()) + ' WHERE mwo_id IN (''MWO-001'', ''MWO-002'', ''MWO-003'')')
conn.commit()
