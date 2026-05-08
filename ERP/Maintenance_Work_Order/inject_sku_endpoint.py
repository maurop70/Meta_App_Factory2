import os

filepath = r"c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Maintenance_Work_Order\maintenance_backend.py"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

new_endpoint = """
@app.get("/inventory/skus")
def get_skus(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM erp_skus")
        total_records = cursor.fetchone()["total"]

        cursor.execute(
            \"\"\"
            SELECT sku_id, nomenclature, unit_cost, reorder_threshold, quantity_on_hand
            FROM erp_skus
            ORDER BY sku_id ASC
            LIMIT ? OFFSET ?
            \"\"\",
            (limit, offset)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "items": rows, "total": total_records}
    except Exception as e:
        logger.error(f"Failed to fetch SKU ledger: {e}")
        raise HTTPException(status_code=500, detail="Matrix synchronization failed.")
    finally:
        conn.close()
"""

if "@app.get(\"/inventory/skus\")" not in content:
    with open(filepath, "a", encoding="utf-8") as f:
        f.write("\n" + new_endpoint + "\n")
    print("Injected /inventory/skus endpoint.")
else:
    print("Endpoint already exists.")
