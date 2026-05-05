import sqlite3
import os
import uuid

db_path = os.path.join('C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order', 'data', 'maintenance_erp.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

try:
    c.execute("BEGIN TRANSACTION")
    
    # 1. Create table
    c.execute("""
    CREATE TABLE IF NOT EXISTS erp_locations (
        id TEXT PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
    )
    """)
    
    # 2. Extract existing distinct locations from erp_equipment
    c.execute("SELECT DISTINCT location_id FROM erp_equipment WHERE location_id IS NOT NULL")
    existing_locations = [row['location_id'] for row in c.fetchall()]
    
    # 3. Insert unique locations into erp_locations
    location_mapping = {}
    for loc_name in existing_locations:
        loc_id = f"LOC-{uuid.uuid4().hex[:6].upper()}"
        location_mapping[loc_name] = loc_id
        # Try to insert (ignore if exists by name)
        try:
            c.execute("INSERT INTO erp_locations (id, name) VALUES (?, ?)", (loc_id, loc_name))
        except sqlite3.IntegrityError:
            # Already exists
            c.execute("SELECT id FROM erp_locations WHERE name = ?", (loc_name,))
            location_mapping[loc_name] = c.fetchone()['id']
            
    # Add a fallback location just in case
    if 'Sector 7G' not in location_mapping:
        try:
            c.execute("INSERT INTO erp_locations (id, name) VALUES (?, ?)", (f"LOC-{uuid.uuid4().hex[:6].upper()}", "Sector 7G"))
        except: pass
    if 'Main Warehouse' not in location_mapping:
        try:
            c.execute("INSERT INTO erp_locations (id, name) VALUES (?, ?)", (f"LOC-{uuid.uuid4().hex[:6].upper()}", "Main Warehouse"))
        except: pass

    # 4. We cannot easily ALTER TABLE to add FOREIGN KEY in sqlite without recreating the table. 
    # But since SQLite loosely enforces them, we can just update the columns to hold the ID instead of the string.
    # Actually, in erp_equipment, location_id was previously a TEXT field holding the Name.
    # Let's map it to ID.
    for loc_name, loc_id in location_mapping.items():
        c.execute("UPDATE erp_equipment SET location_id = ? WHERE location_id = ?", (loc_id, loc_name))
        c.execute("UPDATE work_orders SET location_id = ? WHERE location_id = ?", (loc_id, loc_name))

    conn.commit()
    print("Migration successful.")

except Exception as e:
    conn.rollback()
    print(f"Migration failed: {e}")
finally:
    conn.close()
