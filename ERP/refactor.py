import sys
import re

with open('C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/maintenance_backend.py', 'r') as f:
    content = f.read()

# 1. Update archive_mwo_pdf_worker signature
content = content.replace(
    'def archive_mwo_pdf_worker(mwo_id: str):',
    'def archive_mwo_pdf_worker(mwo_id: str, resolution_notes: str, labor_hours: float):'
)

# Replace the data extraction in archive_mwo_pdf_worker
old_extract = """        # 1. Explicit Data Extraction (Strict Enumeration)
        cursor.execute(
            \"\"\"
            SELECT mwo_id, status, assigned_tech, equipment_id, description,
                   resolution_notes, labor_hours, completed_at
            FROM work_orders 
            WHERE mwo_id = ?
            \"\"\", 
            (mwo_id,)
        )
        mwo_data = cursor.fetchone()"""

new_extract = """        import time
        current_time = time.time()
        
        # 1. Explicit Data Extraction (Strict Enumeration)
        cursor.execute(
            \"\"\"
            SELECT mwo_id, status, assigned_tech, equipment_id, description
            FROM work_orders 
            WHERE mwo_id = ?
            \"\"\", 
            (mwo_id,)
        )
        row = cursor.fetchone()
        if not row:
            logger.error(f"[WORKER FATAL] MWO {mwo_id} not found during archival extraction.")
            return
            
        mwo_data = dict(row)
        mwo_data["resolution_notes"] = resolution_notes
        mwo_data["labor_hours"] = labor_hours
        mwo_data["completed_at"] = current_time"""

content = content.replace(old_extract, new_extract)

# Inside worker, update the status and completed_at
old_worker_update = """        # 4. State Mutation (Schema Linkage)
        cursor.execute(
            "UPDATE work_orders SET archival_pdf_path = ? WHERE mwo_id = ?",
            (file_path, mwo_id)
        )"""

new_worker_update = """        # 4. State Mutation (Schema Linkage & Time Telemetry)
        cursor.execute(
            \"\"\"
            UPDATE work_orders 
            SET archival_pdf_path = ?, status = 'COMPLETED', completed_at = ?, resolution_notes = ?, labor_hours = ? 
            WHERE mwo_id = ?
            \"\"\",
            (file_path, current_time, resolution_notes, labor_hours, mwo_id)
        )"""

content = content.replace(old_worker_update, new_worker_update)

# 2. Update complete_mwo decorator
content = content.replace(
    '@app.post("/api/mwo/{mwo_id}/complete")',
    '@app.post("/mwo/{mwo_id}/complete", status_code=202)'
)

# 3. Update state validation
old_val = "if mwo_record['status'] != 'IN_PROGRESS':\n            raise HTTPException(status_code=400, detail=f\"State Violation: MWO must be IN_PROGRESS to finalize. Current: {mwo_record['status']}\")"
new_val = "if mwo_record['status'] not in ['IN_PROGRESS', 'PENDING_REVIEW']:\n            raise HTTPException(status_code=400, detail=f\"State Violation: MWO must be IN_PROGRESS or PENDING_REVIEW to finalize. Current: {mwo_record['status']}\")"
content = content.replace(old_val, new_val)

# 4. Remove UPDATE block in complete_mwo and update BackgroundTasks
old_update_block = """        # 2. Mutation: Status -> COMPLETED + Log Insertion
        current_time = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            \"\"\"
            UPDATE work_orders 
            SET status = 'COMPLETED', 
                resolution_notes = ?, 
                labor_hours = ?,
                completed_at = ?
            WHERE mwo_id = ?
            \"\"\",
            (payload.resolution_notes, payload.labor_hours, current_time, mwo_id)
        )
        
        # 3. Commit: Physically seal the database ledger
        conn.commit()
        
        # 4. Asynchronous Dispatch (POST-COMMIT): PDF generation in background worker
        background_tasks.add_task(archive_mwo_pdf_worker, mwo_id)
        
        return {
            "status": "success", 
            "message": f"MWO {mwo_id} finalized. Resolution logged. PDF archival dispatched asynchronously."
        }"""

new_update_block = """        # 2. Asynchronous Dispatch: PDF generation & DB completion in background worker
        background_tasks.add_task(archive_mwo_pdf_worker, mwo_id, payload.resolution_notes, payload.labor_hours)
        
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=202, content={
            "status": "success", 
            "message": f"MWO {mwo_id} accepted. PDF archival and finalization dispatched asynchronously."
        })"""

content = content.replace(old_update_block, new_update_block)

with open('C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/maintenance_backend.py', 'w') as f:
    f.write(content)

print("Backend refactored")
