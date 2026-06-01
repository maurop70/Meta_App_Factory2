import os
import sys
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

# Ensure local script directory is in system path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from legal_engine import LegalEngine

app = FastAPI(title="CLO Agent Legal API", version="1.0.0")

class AnalyzeRequest(BaseModel):
    template_name: str
    data: Dict[str, Any]
    output_filename: str

@app.get("/api/health")
async def health():
    return {"status": "online", "agent": "CLO"}

@app.post("/api/legal/analyze")
async def analyze(req: AnalyzeRequest):
    try:
        # Create templates directory if not present
        os.makedirs(os.path.join(SCRIPT_DIR, "templates"), exist_ok=True)
        # Create fallback template if missing
        default_template_path = os.path.join(SCRIPT_DIR, "templates", f"{req.template_name}.txt")
        if not os.path.exists(default_template_path):
            with open(default_template_path, "w", encoding="utf-8") as f:
                f.write("CLO LEGAL AGREEMENT\nTemplate: {template_name}\nData:\n" + "\n".join([f"{k}: {{{k}}}" for k in req.data.keys()]))
        
        # Instantiate LegalEngine asynchronously
        engine = await LegalEngine.create(os.path.join(SCRIPT_DIR, "config.json"))
        # Force config directories to be relative to the CLO script directory
        engine.config["template_dir"] = os.path.join(SCRIPT_DIR, "templates")
        engine.config["output_dir"] = os.path.join(SCRIPT_DIR, "output")
        
        await engine.log_event(f"Orchestrated document generation: {req.template_name}")
        output_path = await engine.generate_document(
            template_name=req.template_name,
            data=req.data,
            output_filename=req.output_filename
        )
        return {
            "status": "success",
            "message": f"Legal document generated successfully at {output_path}",
            "output_path": output_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5080)
