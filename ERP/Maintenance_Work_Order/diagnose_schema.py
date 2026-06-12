
import sqlite3
import os

def get_table_schema(cursor, table_name):
    print(f"--- Schema for {table_name} ---")
    cursor.execute(f"PRAGMA table_info({table_name});")
    rows = cursor.fetchall()
    if not rows:
        print("Table not found or has no columns.")
        return
    for row in rows:
        print(f"  Column {row[0]} ('{row[1]}'): {row[2]}")
    print("\\n")

def main():
    db_path = os.path.join(os.path.dirname(__file__), "data", "maintenance_erp.db")
    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at {db_path}")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        get_table_schema(cursor, "work_orders")
        get_table_schema(cursor, "erp_equipment")
        get_table_schema(cursor, "erp_locations")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
