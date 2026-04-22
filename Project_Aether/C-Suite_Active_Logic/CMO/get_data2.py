import sqlite3
import json

conn = sqlite3.connect('marketing_memory.db')
cur = conn.cursor()
cur.execute("SELECT name, display_name FROM projects")
projects = cur.fetchall()

print("Projects:")
for p in projects:
    print(p)

cur.execute("SELECT project_name, module, COUNT(*) FROM analyses GROUP BY project_name, module")
print("\nAnalyses counts:")
for r in cur.fetchall():
    print(r)
