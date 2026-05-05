import sqlite3
import glob

for db in glob.glob('*.db'):
    try:
        with sqlite3.connect(db) as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            print(f"DB: {db}, Tables: {[t[0] for t in tables]}")
    except Exception as e:
        print(f"Error reading {db}: {e}")
