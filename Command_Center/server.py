"""
Aether Command Center — Standalone Dashboard Server
Admin/Developer-only dashboard for the Meta App Factory ecosystem.
Serves the dashboard UI and proxies data from registered apps.
"""

import os, sys, json, logging
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# UTF-8 for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CommandCenter] %(message)s")
logger = logging.getLogger("CommandCenter")

app = FastAPI(title="Aether Command Center", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
REGISTRY_PATH = os.path.join(FACTORY_DIR, "registry.json")

# ── Dashboard API ────────────────────────────────────────

@app.get("/")
def serve_dashboard():
    """Serves the dashboard HTML."""
    html_path = os.path.join(SCRIPT_DIR, "dashboard.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/api/projects")
def get_projects():
    """Returns the Project Index from registry.json."""
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            registry = json.load(f)
        apps = registry.get("apps", {})
        projects = []
        for name, data in apps.items():
            projects.append({
                "name": name,
                "status": data.get("status", "unknown"),
                "type": data.get("type", "Unknown"),
                "port": data.get("port"),
                "path": data.get("path", f"Meta_App_Factory/{name}"),
                "capabilities": data.get("capabilities", []),
                "last_build": data.get("last_build"),
            })
        return JSONResponse({
            "projects": projects,
            "total": len(projects),
            "last_updated": registry.get("last_updated"),
        })
    except FileNotFoundError:
        return JSONResponse({"projects": [], "total": 0, "error": "registry.json not found"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
def get_health():
    """Returns System Health with live service pings."""
    import requests as req_lib

    services = []
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            registry = json.load(f)

        for name, data in registry.get("apps", {}).items():
            port = data.get("port")
            status_val = "unknown"
            if port:
                try:
                    r = req_lib.get(f"http://localhost:{port}/api/health", timeout=2)
                    status_val = "online" if r.status_code == 200 else "error"
                except Exception:
                    status_val = "offline"
            else:
                status_val = "no_port"

            services.append({
                "name": name,
                "endpoint": f"localhost:{port}" if port else "N/A",
                "status": status_val,
                "port": port,
                "type": data.get("type", "Unknown"),
            })
    except Exception as e:
        logger.warning(f"Health check: registry load failed: {e}")

    infra = [
        {"name": "n8n Cloud", "endpoint": "humanresource.app.n8n.cloud", "status": "configured", "type": "Workflow Engine"},
        {"name": "Google Drive Sync", "endpoint": "Multi-PC", "status": "active", "type": "Storage"},
    ]

    security = [
        {"item": "Credential Exposure", "status": "green", "owner": "Compliance Officer", "note": "All hardcoded keys removed"},
        {"item": "Vault Encryption", "status": "green", "owner": "Compliance Officer", "note": "Fernet AES-128 active"},
        {"item": "Isolation Boundary", "status": "green", "owner": "All agents", "note": "forbidden_references enforced"},
        {"item": "Webhook Auth", "status": "yellow", "owner": "CTO", "note": "P1: Add bearer tokens"},
    ]

    return JSONResponse({
        "services": services,
        "infrastructure": infra,
        "security": security,
        "checked_at": datetime.now().isoformat(),
    })

@app.get("/api/fiscal")
def get_fiscal():
    """Returns Fiscal Oversight data from Project Aether."""
    try:
        sys.path.insert(0, os.path.join(FACTORY_DIR, "Project_Aether"))
        from fiscal_oversight import FiscalOversight
        fo = FiscalOversight()
        return JSONResponse(fo.get_status())
    except ImportError:
        return JSONResponse({
            "engine": "Not Available",
            "threshold": 10.0,
            "current_total_cost": 0.0,
            "budget_remaining": 10.0,
            "error": "fiscal_oversight module not found",
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CommandRequest(BaseModel):
    prompt: str

@app.post("/api/command")
def send_command(req: CommandRequest):
    """Universal Input: sends a prompt to the n8n Brain webhook."""
    from dotenv import load_dotenv
    load_dotenv(os.path.join(FACTORY_DIR, "Resonance", ".env"))
    webhook_url = os.getenv("WEBHOOK_URL", "https://humanresource.app.n8n.cloud/webhook/Resonance-webhook")

    import requests as req_lib
    try:
        response = req_lib.post(webhook_url, json={"prompt": req.prompt}, timeout=60)
        response.raise_for_status()
        try:
            data = response.json()
            output = data.get("text") or data.get("output") or json.dumps(data)
        except ValueError:
            output = response.text
        return JSONResponse({"response": output, "status": "ok"})
    except req_lib.exceptions.Timeout:
        return JSONResponse({"response": "Timeout: The Brain took too long to respond.", "status": "timeout"})
    except Exception as e:
        return JSONResponse({"response": f"Error: {str(e)}", "status": "error"})

@app.get("/api/health-check")
def health_check():
    return JSONResponse({"status": "ok", "app": "Aether Command Center"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5010)
