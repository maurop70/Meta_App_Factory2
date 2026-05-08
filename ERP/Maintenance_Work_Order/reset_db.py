import sqlite3
import os

print("Resetting PRQ-TEST-001...")
conn = sqlite3.connect('data/maintenance_erp.db')
c = conn.cursor()

c.execute("UPDATE erp_procurement_queue SET status = 'APPROVED' WHERE procurement_id = 'PRQ-TEST-001'")
conn.commit()
conn.close()
print("Done.")

# Also restart FastAPI process!
# Since I am in python, I can't easily restart another process unless I kill it.
# Let's just exit and do it in bash.
