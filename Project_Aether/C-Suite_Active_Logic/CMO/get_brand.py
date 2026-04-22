import sqlite3

conn = sqlite3.connect('marketing_memory.db')
cur = conn.cursor()
cur.execute("SELECT result_json FROM analyses WHERE project_name = 'AntigravityWorkspace_Q3' AND module = 'brand_studio'")
row = cur.fetchone()

print(row[0] if row else "No data")
