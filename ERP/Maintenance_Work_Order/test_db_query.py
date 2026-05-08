import sqlite3
import time
import uuid

conn = sqlite3.connect('data/maintenance_erp.db')
cursor = conn.cursor()

mwo_id = "MWO-2026-001"
part_id = "PRT-9D3CADBD"
tech_id = "ERP-3000"

try:
    cursor.execute("BEGIN IMMEDIATE TRANSACTION;")
    
    cursor.execute("SELECT status FROM work_orders WHERE mwo_id = ?", (mwo_id,))
    mwo = cursor.fetchone()
    if not mwo or mwo[0] not in ('ASSIGNED', 'IN_PROGRESS', 'DISPATCHED'):
        print("Invalid MWO")
    
    cursor.execute("SELECT sku_id, status FROM erp_parts WHERE part_id = ?", (part_id,))
    part = cursor.fetchone()
    if not part or part[1] != "IN_STOCK":
        print("Invalid Part")
    
    consumption_id = f"CNS-{uuid.uuid4().hex[:8].upper()}"
    
    print("Executing insert...")
    cursor.execute(
        """
        INSERT INTO mwo_consumed_parts 
        (consumption_id, mwo_id, part_id, quantity_consumed, consumed_at, logged_by_tech_id) 
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (consumption_id, mwo_id, part_id, 1, time.time(), tech_id)
    )
    
    print("Executing update erp_parts...")
    cursor.execute("UPDATE erp_parts SET status = 'CONSUMED' WHERE part_id = ?", (part_id,))
    
    print("Executing update erp_skus...")
    cursor.execute(
        "UPDATE erp_skus SET quantity_on_hand = quantity_on_hand - 1 WHERE sku_id = ?",
        (part[0],)
    )
    
    conn.commit()
    print("Success")
except Exception as e:
    conn.rollback()
    print(f"Error: {e}")
finally:
    conn.close()
