import sqlite3

conn = sqlite3.connect('marketing_memory.db')
cur = conn.cursor()
cur.execute("SELECT module, created_at, input_summary FROM analyses WHERE project_name = 'Antigravityworkspace Q3'")
rows = cur.fetchall()

for r in rows:
    print(r)

print("\nAssets:")
cur.execute("SELECT company_name, tagline FROM brand_identities WHERE project_name = 'Antigravityworkspace Q3'")
brands = cur.fetchall()
for b in brands:
    print("Brand:", b)
