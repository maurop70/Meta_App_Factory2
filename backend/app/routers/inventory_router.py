from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import List
import sqlite3
from app.db import get_db_connection

router = APIRouter(prefix="/api/inventory", tags=["Inventory"])

class StockUpdateRequest(BaseModel):
    stock: int

class InventoryItem(BaseModel):
    id: int
    sku: str
    name: str
    category: str
    stock: int
    price: float
    status: str

class InventoryResponse(BaseModel):
    items: List[InventoryItem]
    total: int
    limit: int
    offset: int

@router.get("", response_model=InventoryResponse)
async def get_inventory(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Enforce direct binding to SQLite layer for count and paginated query
        try:
            cursor.execute("SELECT COUNT(*) FROM inventory")
            total = cursor.fetchone()[0]
            
            cursor.execute(
                "SELECT id, sku, name, category, stock, price, status FROM inventory LIMIT ? OFFSET ?",
                (limit, offset)
            )
            rows = cursor.fetchall()
            
            items = []
            for row in rows:
                items.append({
                    "id": row["id"],
                    "sku": row["sku"],
                    "name": row["name"],
                    "category": row["category"],
                    "stock": row["stock"],
                    "price": row["price"],
                    "status": row["status"]
                })
        except sqlite3.OperationalError:
            # Handle uninitialized database (table doesn't exist)
            items = []
            total = 0
            
        conn.close()
        
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{item_id}/stock")
async def update_stock(item_id: int, payload: StockUpdateRequest):
    if payload.stock < 0:
        raise HTTPException(status_code=400, detail="Stock level cannot be negative.")
    
    # Determine status based on stock level
    if payload.stock == 0:
        status = "Out of Stock"
    elif payload.stock < 10:
        status = "Critical"
    else:
        status = "Active"
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify item existence
        cursor.execute("SELECT id FROM inventory WHERE id = ?", (item_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Inventory item not found.")
            
        # Update stock and calculated status
        cursor.execute(
            "UPDATE inventory SET stock = ?, status = ? WHERE id = ?",
            (payload.stock, status, item_id)
        )
        conn.commit()
        
        # Retrieve updated item
        cursor.execute(
            "SELECT id, sku, name, category, stock, price, status FROM inventory WHERE id = ?",
            (item_id,)
        )
        row = cursor.fetchone()
        updated_item = {
            "id": row["id"],
            "sku": row["sku"],
            "name": row["name"],
            "category": row["category"],
            "stock": row["stock"],
            "price": row["price"],
            "status": row["status"]
        }
        conn.close()
        return updated_item
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Database update error: {str(e)}")
