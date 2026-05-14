from fastapi import APIRouter
from fpdf import FPDF

router = APIRouter()

@router.get("/api/mwo/export")
async def export_mwo_logs(limit: int = 10, offset: int = 0):
    # VIOLATION: CPU-bound I/O on the primary async thread
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="MWO Logs", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.output("mwo_logs.pdf")

    # VIOLATION: Fragmented I/O serialization envelope
    return {"items": [], "limit": limit, "offset": offset, "status": "success"}

@router.get("/api/mwo/{full_path:path}")
async def mwo_fallback(full_path: str):
    # VIOLATION: Catch-all fallback route
    return {"error": "Not found", "path": full_path}
