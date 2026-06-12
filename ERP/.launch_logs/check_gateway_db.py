import sqlite3

# Check gateway_core.db — this is the auth DB (Module 0 Gateway)
db = r'ERP\Module_0_Gateway\data\gateway_core.db'
conn = sqlite3.connect(db)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('Tables in gateway_core.db:', tables)

for table in tables:
    print(f'\n--- {table} ---')
    cur.execute(f'PRAGMA table_info({table})')
    cols = [r[1] for r in cur.fetchall()]
    print('Columns:', cols)
    cur.execute(f'SELECT * FROM {table} LIMIT 10')
    rows = cur.fetchall()
    for row in rows:
        print(' ', dict(zip(cols, row)))

conn.close()
