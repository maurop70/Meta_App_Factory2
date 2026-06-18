import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from local_db import get_db_connection
import maintenance_backend as mb


def recover():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT mwo_id, resolution_notes, labor_hours FROM work_orders WHERE status = 'COMPLETED' AND archival_pdf_path IS NULL"
        ).fetchall()

        print(f"Found {len(rows)} completed work orders missing PDF archives.")
        for r in rows:
            mwo_id = r["mwo_id"]
            notes = r["resolution_notes"] or "Completed by technician."
            hours = r["labor_hours"] or 1.0
            print(f"Regenerating PDF for {mwo_id}...")
            mb.archive_mwo_pdf_worker(mwo_id, notes, hours)
            print(f"Successfully generated and linked archive for {mwo_id}.")
    finally:
        conn.close()


if __name__ == "__main__":
    recover()
