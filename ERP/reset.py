import sqlite3
conn = sqlite3.connect(r'c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Maintenance_Work_Order\data\maintenance_erp.db')
conn.execute('UPDATE maintenance_work_orders SET status=''IN_PROGRESS'' WHERE mwo_id=''MWO-003''')
conn.commit()
