import os
import json
import time
import tempfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, Form, File, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from docxtpl import DocxTemplate
from typing import List, Optional

import core

VALID_EXTS = {'.pdf', '.xlsx', '.xls', '.txt', '.csv', '.doc', '.docx'}

app = FastAPI(title="Corporate Secretary API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini setup via core.py
core.setup_gemini()

ui_path = Path(__file__).parent / "ui"
ui_path.mkdir(exist_ok=True)
app.mount("/ui", StaticFiles(directory=str(ui_path)), name="ui")

@app.get("/")
def serve_index():
    index_file = ui_path / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="UI not found. Create ui/index.html first.")

@app.post("/generate_minutes")
async def generate_minutes(
    target_month: str = Form(...),
    master_files: Optional[List[UploadFile]] = File(None),
    monthly_files: List[UploadFile] = File(...)
):
    print(f"Received request for {target_month}")
    
    if master_files is None:
        master_files = []
        
    target_folder_name = f"{target_month.replace(' ', '_')}_Minutes"
    archive_path = Path(__file__).parent / "archives" / target_folder_name
    sources_path = archive_path / "sources"
    sources_path.mkdir(parents=True, exist_ok=True)
    
    uploaded_gfiles = []
    
    try:
        for mf in master_files:
            if mf.filename:
                mf_path = sources_path / mf.filename
                if mf_path.suffix.lower() not in VALID_EXTS:
                    raise HTTPException(status_code=400, detail=f"Unsupported format: {mf.filename}")
                with open(mf_path, "wb") as f:
                    f.write(await mf.read())
                print(f"Uploading master file {mf.filename}")
                if mf_path.suffix.lower() == '.csv':
                    gfile = core.client.files.upload(file=str(mf_path), config={'mime_type': 'text/csv'})
                else:
                    gfile = core.client.files.upload(file=str(mf_path))
                uploaded_gfiles.append(gfile)
                
        for month_file in monthly_files:
            if month_file.filename:
                mf_path = sources_path / month_file.filename
                if mf_path.suffix.lower() not in VALID_EXTS:
                    raise HTTPException(status_code=400, detail=f"Unsupported format: {month_file.filename}")
                with open(mf_path, "wb") as f:
                    f.write(await month_file.read())
                print(f"Uploading monthly file {month_file.filename}")
                if mf_path.suffix.lower() == '.csv':
                    gfile = core.client.files.upload(file=str(mf_path), config={'mime_type': 'text/csv'})
                else:
                    gfile = core.client.files.upload(file=str(mf_path))
                uploaded_gfiles.append(gfile)
                
        if not uploaded_gfiles:
            raise HTTPException(status_code=400, detail="No files uploaded successfully.")
            
        time.sleep(2)
        dynamic_prompt = core.SYSTEM_PROMPT_TEMPLATE.format(target_month_year=target_month)
        print("Invoking Gemini...")
        response = core.client.models.generate_content(
            model="gemini-2.5-pro",
            contents=uploaded_gfiles,
            config={
                "system_instruction": dynamic_prompt,
                "response_mime_type": "application/json"
            }
        )
        
        result_text = response.text
        if result_text.startswith("```json"):
            result_text = result_text.split("```json")[1].rsplit("```", 1)[0].strip()
        elif result_text.startswith("```"):
            result_text = result_text.split("```")[1].rsplit("```", 1)[0].strip()
            
        data = json.loads(result_text)
        
        template_path = Path(__file__).parent / "template" / "template.docx"
        if not template_path.exists():
            raise HTTPException(status_code=500, detail="Template missing at " + str(template_path))
            
        doc = DocxTemplate(str(template_path))
        doc.render(data)
        
        output_filename = f"{target_month.replace(' ', '_')}_Minutes.docx"
        output_path = archive_path / output_filename
        doc.save(str(output_path))
        
        print(f"Returning {output_filename}")
        return FileResponse(path=str(output_path), filename=output_filename, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        finally:
            for gfile in uploaded_gfiles:
                try:
                    core.client.files.delete(name=gfile.name)
                except:
                    pass
