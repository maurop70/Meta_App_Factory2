import sqlite3
import os

try:
    conn = sqlite3.connect('factory_ephemeral.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", tables)
except Exception as e:
    print(e)
