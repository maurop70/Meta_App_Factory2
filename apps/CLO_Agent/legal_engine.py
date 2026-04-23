import os
import glob
import json
import logging
import asyncio
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import requests
import uvicorn

# PDF Parsing support
try:
    import fitz  # PyMuPDF
    PDF_ENABLED = True
except ImportError:
    PDF_ENABLED = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] CLO_Agent: %(message)s")
logger = logging.getLogger("CLO_Engine")

app = FastAPI(title="CLO Native Engine", version="1.0.0")

VAULT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Delegate_AI_Beta_Agreement_Vault", "vault_data"))
SOCRATIC_ENDPOINT = "http://localhost:5000/api/socratic/explain"

def extract_text(filepath: str) -> str:
    ext = filepath.lower().split('.')[-1]
    if ext in ['txt', 'md']:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    elif ext == 'pdf' and PDF_ENABLED:
        text = ""
        try:
            with fitz.open(filepath) as doc:
                for page in doc:
                    text += page.get_text()
            return text
        except Exception as e:
            logger.error(f"Failed to read PDF {filepath}: {e}")
            return f"[PDF_EXTRACTION_ERROR: {str(e)}]"
    elif ext == 'pdf' and not PDF_ENABLED:
        return "[PDF_SKIPPED: PyMuPDF not installed on host]"
    return ""

@app.get("/api/health")
def health_ping():
    return {"status": "ok", "service": "CLO_Agent"}

@app.post("/scan_vault")
async def scan_vault():
    """
    Crawls the Delegate_AI_Beta_Agreement vault and pushes findings to Socratic Trace.
    """
    if not os.path.exists(VAULT_DIR):
        return JSONResponse({"status": "error", "error": f"Vault not found at {VAULT_DIR}"}, status_code=404)

    logger.info(f"Scanning vault: {VAULT_DIR}")
    documents = []
    supported_extensions = ['*.txt', '*.md', '*.pdf']
    
    for ext in supported_extensions:
        pattern = os.path.join(VAULT_DIR, ext)
        for filepath in glob.glob(pattern):
            documents.append(filepath)

    if not documents:
        return {"status": "success", "message": "Vault is empty. No documents scanned.", "findings": []}

    results = []
    for doc in documents:
        content = extract_text(doc)
        if not content.strip():
            continue
            
        filename = os.path.basename(doc)
        logger.info(f"Processing document: {filename}...")
        
        # Route logic through the Socratic Engine
        payload = {
            "app_name": "CLO_Agent",
            "context": {
                "file": filename,
                "content_preview": content[:3000] # Limit chunking
            },
            "issue": "Perform a Structural Audit against the master IP protocol constraints.",
            "goal": "Verify active 'Native' compliance and identify legal fragility points.",
            "query": f"Analyze contract: {filename}"
        }
        
        socratic_trace = {}
        try:
            res = requests.post(SOCRATIC_ENDPOINT, json=payload, timeout=15)
            if res.ok:
                socratic_trace = res.json()
            else:
                socratic_trace = {"error": f"Socratic backend returned {res.status_code}"}
        except Exception as e:
            logger.error(f"Socratic bridge failed: {e}")
            socratic_trace = {"error": str(e)}
            
        results.append({
            "file": filename,
            "socratic_verdict": socratic_trace
        })

    return {"status": "success", "documents_scanned": len(documents), "findings": results}

if __name__ == "__main__":
    logger.info("Booting CLO Legal Engine on port 5080...")
    uvicorn.run(app, host="0.0.0.0", port=5080)
