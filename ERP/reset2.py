import sqlite3
import glob

for db in glob.glob('*.db'):
    with sqlite3.connect(db) as conn:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"DB: {db}, Tables: {tables}")
