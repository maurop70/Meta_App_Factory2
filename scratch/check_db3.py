import sqlite3
import os

try:
    conn = sqlite3.connect('Master_Architect_Elite_Logic/architect_memory.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", tables)
except Exception as e:
    print(e)
