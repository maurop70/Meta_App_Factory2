import sqlite3
import json

try:
    conn = sqlite3.connect('maintenance_erp.db')
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    with open('schema_dump.txt', 'w') as f:
        for t in tables:
            if t[0]:
                f.write(t[0] + '\n\n')
except Exception as e:
    with open('schema_dump.txt', 'w') as f:
        f.write(str(e))
