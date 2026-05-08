import os

filepath = r"c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Maintenance_Work_Order\maintenance_backend.py"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

target = '@app.post("/work-orders/{mwo_id}/consume"'
idx = content.find(target)

if idx != -1:
    new_content = content[:idx] + """@app.post("/work-orders/{mwo_id}/consume", status_code=201)
def ingest_mwo_consumption(
    mwo_id: str,
    payload: MwoConsumptionPayload,
    token_payload: dict = Depends(verify_jwt_token)
):
    tech_id = token_payload.get("sub")
    if not tech_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Identity Gateway missing sub claim")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # 2. Enforce Strict Write-Lock to prevent SQLITE_BUSY deadlocks
        cursor.execute("BEGIN IMMEDIATE TRANSACTION;")
        
        # 3. Assert MWO Execution State
        cursor.execute("SELECT status FROM work_orders WHERE mwo_id = ?", (mwo_id,))
        mwo = cursor.fetchone()
        if not mwo or mwo["status"] not in ('ASSIGNED', 'IN_PROGRESS', 'DISPATCHED'):
            raise HTTPException(status_code=400, detail="Invalid or inactive MWO target.")

        import time
        import uuid
        
        # 4. Iterate and Execute Discrete Physical Math
        consumed_ledgers = []
        for part_id in payload.part_ids:
            cursor.execute("SELECT sku_id, status FROM erp_parts WHERE part_id = ?", (part_id,))
            part = cursor.fetchone()
            
            if not part or part["status"] != "IN_STOCK":
                raise HTTPException(status_code=400, detail=f"Part {part_id} is invalid or already consumed.")
                
            consumption_id = f"CNS-{uuid.uuid4().hex[:8].upper()}"
            
            # A. Log Junction Consumption (Strictly QTY 1 for discrete assets)
            cursor.execute(
                \"\"\"
                INSERT INTO mwo_consumed_parts 
                (consumption_id, mwo_id, part_id, quantity_consumed, consumed_at, logged_by_tech_id) 
                VALUES (?, ?, ?, ?, ?, ?)
                \"\"\",
                (consumption_id, mwo_id, part_id, 1, time.time(), tech_id)
            )
            
            # B. Mutate Physical Asset Status
            cursor.execute("UPDATE erp_parts SET status = 'CONSUMED' WHERE part_id = ?", (part_id,))
            
            # C. Deduct Exactly 1 from the SKU Ledger
            cursor.execute(
                "UPDATE erp_skus SET quantity_on_hand = quantity_on_hand - 1 WHERE sku_id = ?",
                (part["sku_id"],)
            )
            consumed_ledgers.append(part_id)

        conn.commit()
        return {
            "status": "success",
            "message": f"{len(consumed_ledgers)} discrete parts mathematically consumed against MWO {mwo_id}."
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        print(f"Consumption Execution Error: {e}")
        raise HTTPException(status_code=500, detail="Fatal execution error during part consumption.")
    finally:
        conn.close()
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Patched route.")
else:
    print("Route not found.")
