import sqlite3
import os

db_files = []
for root, _, files in os.walk('c:\\Dev\\Antigravity_AI_Agents\\Meta_App_Factory'):
    for f in files:
        if f.endswith('.db'):
            db_files.append(os.path.join(root, f))

for db_file in db_files:
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for t in tables:
            table_name = t[0]
            try:
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                for row in rows:
                    if 'Aegis' in str(row):
                        print(f"FOUND IN {db_file} -> TABLE {table_name}: {row}")
            except Exception as e:
                pass
    except Exception as e:
        pass
