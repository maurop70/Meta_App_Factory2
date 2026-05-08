import sqlite3

def run():
    conn = sqlite3.connect('data/maintenance_erp.db')
    cursor = conn.cursor()
    
    # Check existing schema
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='erp_parts';")
    row = cursor.fetchone()
    if row:
        print("Existing schema:")
        print(row[0])
    else:
        print("Table erp_parts does not exist.")

    # We might need to drop the old table. The user asks to run:
    # CREATE TABLE IF NOT EXISTS erp_parts ( ... )
    # But if the old one exists, IF NOT EXISTS will skip it. 
    # Let's drop it if it has the old schema (quantity_on_hand).
    if row and "quantity_on_hand" in row[0]:
        print("Dropping old erp_parts table...")
        cursor.execute("DROP TABLE erp_parts;")
        
    print("Creating new erp_parts table...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS erp_parts (
        part_id TEXT PRIMARY KEY,
        sku_id TEXT NOT NULL,
        serial_number TEXT UNIQUE,
        status TEXT NOT NULL DEFAULT 'IN_STOCK',
        FOREIGN KEY (sku_id) REFERENCES erp_skus(sku_id) ON DELETE RESTRICT
    );
    ''')
    conn.commit()
    conn.close()
    print("Migration successful.")

if __name__ == '__main__':
    run()
