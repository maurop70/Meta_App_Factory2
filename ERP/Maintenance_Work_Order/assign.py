import sqlite3
import os
_here = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_here, "data", "maintenance_erp.db")
c = sqlite3.connect(DB_PATH)
c.execute("UPDATE work_orders SET assigned_tech='tech1' WHERE mwo_id='MWO-TEST-b8b8a7-0'")
c.commit()
