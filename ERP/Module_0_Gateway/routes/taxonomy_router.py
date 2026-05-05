from fastapi import APIRouter, HTTPException, Depends
from core.database import get_db_connection

router = APIRouter()

@router.get("/employees")
def get_employees():
    """Read-only taxonomy endpoint for employees."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM erp_employees")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

@router.get("/departments")
def get_departments():
    """Read-only taxonomy endpoint for departments."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM erp_departments")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

@router.get("/employees/{emp_id}")
def get_employee(emp_id: str):
    """Read-only taxonomy endpoint for a specific employee."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM erp_employees WHERE emp_id = ?", (emp_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Employee not found")
        return dict(row)
    finally:
        conn.close()
