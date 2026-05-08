import sqlite3

def actuate():
    conn = sqlite3.connect('data/maintenance_erp.db')
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        
        cursor.execute("SELECT status, part_id, authorized_quantity FROM erp_procurement_queue WHERE procurement_id = ?", ("PRQ-TEST-001",))
        record = cursor.fetchone()
        
        current_status = record["status"]
        part_id = record["part_id"]
        db_authorized_qty = record["authorized_quantity"]
        
        payload_status = "FULFILLED"
        
        cursor.execute(
            "UPDATE erp_procurement_queue SET status = ? WHERE procurement_id = ?", 
            (payload_status, "PRQ-TEST-001")
        )
        
        # Autonomous Inventory Hook (FULFILLED only)
        if not db_authorized_qty:
            print("Fatal execution error: FULFILLED triggered without prior authorized_quantity.")
            return
        
        cursor.execute(
            "UPDATE erp_parts SET quantity_on_hand = quantity_on_hand + ? WHERE part_id = ?",
            (db_authorized_qty, part_id)
        )
        
        conn.commit()
        print("Success")
    except Exception as e:
        conn.rollback()
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

actuate()
