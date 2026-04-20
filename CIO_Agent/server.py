"""
server.py — CIO Agent (Chief Innovation Officer)
═══════════════════════════════════════════════════════
Sub-Agent of C-Suite | Port: 5090 | Antigravity-AI

Automated, read-only strategic intelligence agent.
Performs 24-hour intelligence sweeps: competitor analysis,
AI/LLM frontier news, tech integrations, and internal
architecture audits. Produces actionable Upgrade Memos.

Permission Sandbox:
  ✅ read_url(*)  — Unrestricted web research
  ✅ read_file    — Full local directory visibility
  ✅ write_file   — ONLY to App_Registry/Proposals/
  ❌ command(*)   — Completely blocked

Endpoints:
  GET  /                       — Dashboard
  GET  /api/health             — Health check
  POST /api/cio/process        — Trigger intelligence sweep
  GET  /api/cio/memos          — List generated memos
  GET  /api/cio/memos/{name}   — Read specific memo
  POST /api/cio/authorize      — Authorize Upgrade → Master Architect
"""

import os
import sys
import json
import asyncio
import logging
import traceback
from pathlib import Path
from datetime import datetime
from typing import List, Optional

import requests as sync_requests

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import aiohttp

# ═══════════════════════════════════════════════════════════
#  ENVIRONMENT
# ═══════════════════════════════════════════════════════════

ROOT = Path(__file__).parent
FACTORY_ROOT = ROOT.parent

for env_path in [ROOT / ".env", FACTORY_ROOT / ".env"]:
    if env_path.exists():
        load_dotenv(env_path)
        break

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("CIO_Agent")

sys.path.insert(0, str(ROOT))
from cio_engine import run_full_sweep, list_memos, read_memo

# ═══════════════════════════════════════════════════════════
#  APP
# ═══════════════════════════════════════════════════════════

app = FastAPI(
    title="CIO Agent — Chief Innovation Officer",
    version="1.0.0",
    docs_url="/docs",
)


# ── V3 Telemetry: Global Exception Hook ──────────────────
def global_exception_handler(exc_type, exc_value, exc_tb):
    """Catches fatal start-up/thread crashes and fires telemetry to the Operator."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.error(f"FATAL UNHANDLED EXCEPTION: {exc_value}\n{tb_str}")

    try:
        sync_requests.post(
            "http://localhost:5030/api/qa/ingest",
            json={
                "agent": "CIO_Agent",
                "status": "FAIL",
                "node": "FATAL UNHANDLED EXCEPTION",
                "result": "TEST_FAIL",
                "timestamp": datetime.now().isoformat()
            },
            timeout=5
        )
    except Exception:
        pass

    sys.exit(1)


sys.excepthook = global_exception_handler


# ── V3 Telemetry: FastAPI Exception Handler ──────────────
@app.exception_handler(Exception)
async def fastapi_exception_handler(request: Request, exc: Exception):
    """Catches 500 runtime errors and reports to central telemetry."""
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error(f"FASTAPI RUNTIME EXCEPTION: {exc}\n{tb_str}")
    try:
        sync_requests.post(
            "http://localhost:5030/api/qa/ingest",
            json={
                "agent": "CIO_Agent",
                "status": "FAIL",
                "node": f"FASTAPI RUNTIME EXCEPTION: {str(exc)}",
                "result": "TEST_FAIL",
                "timestamp": datetime.now().isoformat()
            },
            timeout=2
        )
    except Exception:
        pass
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)}
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5030", "http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════
#  SSE GHOST STREAM TELEMETRY
# ═══════════════════════════════════════════════════════════

async def sse_broadcast(status: str, node: str, result: str):
    """Broadcasts non-blocking SSE telemetry to Phantom QA Ghost Stream."""
    payload = {
        "agent": "CIO_Agent",
        "status": status,
        "node": node,
        "result": result,
        "timestamp": datetime.now().isoformat()
    }
    logger.info(f"[Ghost Stream] {status} | {node} | {result}")
    
    async def _post():
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    "http://localhost:5030/api/qa/ingest",
                    json=payload,
                    timeout=2
                )
        except Exception:
            pass
            
    asyncio.create_task(_post())

# ═══════════════════════════════════════════════════════════
#  PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════

class CIOProcessRequest(BaseModel):
    focus_areas: Optional[List[str]] = Field(
        default=None,
        description="Optional domain filter: 'competitors', 'ai_frontier', 'tech_integrations'"
    )


class AuthorizeUpgradeRequest(BaseModel):
    memo_filename: str = Field(..., description="Filename of the memo to authorize")
    directive: str = Field(..., description="User's authorization text / instructions for the Master Architect")


# ═══════════════════════════════════════════════════════════
#  SWEEP STATE (in-memory)
# ═══════════════════════════════════════════════════════════

sweep_state = {
    "last_sweep": None,
    "last_result": None,
    "sweep_count": 0,
    "is_running": False,
}


# ═══════════════════════════════════════════════════════════
#  24-HOUR SCHEDULED LOOP
# ═══════════════════════════════════════════════════════════

async def scheduled_sweep_loop():
    """Background async loop that triggers a sweep every 24 hours."""
    # Wait 60 seconds after boot before first sweep (let system stabilize)
    await asyncio.sleep(60)

    while True:
        if not sweep_state["is_running"]:
            logger.info("⏰ Scheduled 24-hour sweep triggered")
            try:
                sweep_state["is_running"] = True
                result = await asyncio.get_event_loop().run_in_executor(None, run_full_sweep, None)
                sweep_state["last_sweep"] = datetime.now().isoformat()
                sweep_state["last_result"] = result
                sweep_state["sweep_count"] += 1
                logger.info(f"⏰ Scheduled sweep complete: {result.get('memo_filename', 'no memo')}")
            except Exception as e:
                logger.error(f"Scheduled sweep failed: {e}")
            finally:
                sweep_state["is_running"] = False

        # Sleep 24 hours
        await asyncio.sleep(86400)


@app.on_event("startup")
async def startup_event():
    """Launch the 24-hour background sweep loop."""
    asyncio.create_task(scheduled_sweep_loop())
    logger.info("CIO Agent online — 24-hour sweep loop initialized")


# ═══════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════

@app.get("/")
async def dashboard():
    """Glassmorphic dashboard for the CIO Agent."""
    memos = list_memos()
    memo_count = len(memos)
    last_sweep = sweep_state.get("last_sweep", "Never")
    sweep_count = sweep_state.get("sweep_count", 0)
    is_running = sweep_state.get("is_running", False)

    status_color = "#f59e0b" if is_running else "#00c896"
    status_text = "Sweep In Progress..." if is_running else "Online — Idle"

    memo_rows = ""
    for m in memos[:8]:
        created = m["created"][:16].replace("T", " ")
        size_kb = round(m["size_bytes"] / 1024, 1)
        memo_rows += f"""
        <tr>
            <td><a href="/api/cio/memos/{m['filename']}" class="memo-link">📋 {m['filename']}</a></td>
            <td>{created}</td>
            <td>{size_kb} KB</td>
            <td>
                <button class="action-btn primary" style="padding: 4px 12px; font-size: 11px;" 
                        onclick="authorizeUpgrade('{m['filename']}')">Authorize</button>
            </td>
        </tr>"""

    if not memo_rows:
        memo_rows = '<tr><td colspan="3" style="color:rgba(255,255,255,0.3); text-align:center;">No memos yet — trigger a sweep below</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CIO Agent — Chief Innovation Officer</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ overflow-x: hidden; }}
body {{
    font-family: 'Inter', sans-serif;
    background: linear-gradient(135deg, #0a0a1a 0%, #0d1b2a 40%, #1b2838 100%);
    color: #e0e0e0;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
}}
.container {{
    max-width: 800px;
    width: 95%;
    padding: 40px;
    background: rgba(255,255,255,0.03);
    backdrop-filter: blur(24px);
    border-radius: 24px;
    border: 1px solid rgba(255,255,255,0.07);
    box-shadow: 0 24px 80px rgba(0,0,0,0.5);
    position: relative;
    overflow: hidden;
}}
.container::before {{
    content: '';
    position: absolute;
    top: -120px; right: -120px;
    width: 300px; height: 300px;
    background: radial-gradient(circle, rgba(56,189,248,0.06), transparent 70%);
    pointer-events: none;
}}
.container::after {{
    content: '';
    position: absolute;
    bottom: -80px; left: -80px;
    width: 220px; height: 220px;
    background: radial-gradient(circle, rgba(168,85,247,0.05), transparent 70%);
    pointer-events: none;
}}
.badge {{
    display: inline-block;
    background: linear-gradient(135deg, #38bdf8, #0ea5e9);
    color: white;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 16px;
}}
.badge.version {{
    background: linear-gradient(135deg, #a855f7, #7c3aed);
    margin-left: 8px;
}}
h1 {{
    font-size: 28px;
    font-weight: 700;
    background: linear-gradient(135deg, #38bdf8, #a855f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 8px;
}}
.subtitle {{
    font-size: 14px;
    color: rgba(255,255,255,0.45);
    margin-bottom: 28px;
    line-height: 1.6;
}}
.status {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: rgba({','.join(['245,158,11' if is_running else '0,200,150'])},0.05);
    border: 1px solid rgba({','.join(['245,158,11' if is_running else '0,200,150'])},0.15);
    border-radius: 12px;
    margin-bottom: 20px;
}}
.dot {{
    width: 8px; height: 8px;
    border-radius: 50%;
    background: {status_color};
    animation: pulse 2s infinite;
}}
@keyframes pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.4; }} }}
.stat-row {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 24px;
}}
.stat {{
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 14px;
    text-align: center;
}}
.stat-val {{ font-size: 22px; font-weight: 700; color: #38bdf8; }}
.stat-label {{ font-size: 10px; color: rgba(255,255,255,0.4); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }}
.card {{
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 16px;
    position: relative;
    z-index: 1;
}}
.card h3 {{
    font-size: 12px;
    color: rgba(255,255,255,0.4);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 14px;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th {{
    font-size: 10px;
    color: rgba(255,255,255,0.3);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    text-align: left;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}}
td {{
    font-size: 13px;
    padding: 10px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.03);
    color: rgba(255,255,255,0.6);
}}
.memo-link {{
    color: #38bdf8;
    text-decoration: none;
    transition: color 0.2s;
}}
.memo-link:hover {{ color: #a855f7; }}
.endpoint {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}}
.endpoint:last-child {{ border-bottom: none; }}
.method {{
    font-size: 10px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 6px;
    min-width: 44px;
    text-align: center;
}}
.method.post {{ background: rgba(168,85,247,0.2); color: #a855f7; }}
.method.get {{ background: rgba(56,189,248,0.2); color: #38bdf8; }}
.path {{ font-family: 'JetBrains Mono', 'Consolas', monospace; font-size: 12px; color: #e0e0e0; }}
.btn-row {{
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-top: 24px;
    position: relative;
    z-index: 1;
}}
.action-btn {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 14px 28px;
    color: white;
    border: none;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    text-decoration: none;
    transition: transform 0.2s, box-shadow 0.2s;
    font-family: inherit;
}}
.action-btn:hover {{ transform: translateY(-2px); }}
.action-btn.primary {{
    background: linear-gradient(135deg, #38bdf8, #0ea5e9);
}}
.action-btn.primary:hover {{ box-shadow: 0 8px 24px rgba(56,189,248,0.3); }}
.action-btn.secondary {{
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
}}
.action-btn.secondary:hover {{ background: rgba(255,255,255,0.1); }}
.action-btn:disabled {{
    opacity: 0.5;
    cursor: not-allowed;
    transform: none !important;
}}
#sweepResult {{
    display: none;
    margin-top: 16px;
    padding: 16px;
    border-radius: 12px;
    font-size: 13px;
    position: relative;
    z-index: 1;
}}
#sweepResult.success {{
    display: block;
    background: rgba(16,185,129,0.06);
    border: 1px solid rgba(16,185,129,0.2);
    color: #10b981;
}}
#sweepResult.error {{
    display: block;
    background: rgba(239,68,68,0.06);
    border: 1px solid rgba(239,68,68,0.2);
    color: #ef4444;
}}
@media (max-width: 600px) {{
    .container {{ padding: 20px 16px; }}
    h1 {{ font-size: 22px; }}
    .stat-row {{ grid-template-columns: repeat(2, 1fr); }}
    .btn-row {{ flex-direction: column; }}
}}
</style>
</head>
<body>
<div class="container">
    <div class="badge">C-Suite Intelligence</div>
    <span class="badge version">v1.0 — Read-Only</span>
    <h1>Chief Innovation Officer</h1>
    <p class="subtitle">Automated strategic intelligence — competitor analysis, AI frontier scanning, tech integration hunting, and internal architecture audits.</p>

    <div class="status">
        <div class="dot"></div>
        <span style="font-size:13px; font-weight:500; color:{status_color};">{status_text} — Port 5090</span>
    </div>

    <div class="stat-row">
        <div class="stat"><div class="stat-val">{memo_count}</div><div class="stat-label">Memos</div></div>
        <div class="stat"><div class="stat-val">{sweep_count}</div><div class="stat-label">Sweeps</div></div>
        <div class="stat"><div class="stat-val">5090</div><div class="stat-label">Port</div></div>
        <div class="stat"><div class="stat-val">24h</div><div class="stat-label">Interval</div></div>
    </div>

    <div class="card">
        <h3>Generated Upgrade Memos</h3>
        <table>
            <thead><tr><th>Memo</th><th>Created</th><th>Size</th><th>Action</th></tr></thead>
            <tbody>{memo_rows}</tbody>
        </table>
    </div>

    <div class="card">
        <h3>API Endpoints</h3>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/api/cio/process — Trigger intelligence sweep</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/cio/memos — List all memos</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/cio/memos/{{name}} — Read specific memo</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/api/cio/authorize — Authorize upgrade → Master Architect</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/health — Watchdog health check</span></div>
    </div>

    <div class="btn-row">
        <button class="action-btn primary" id="sweepBtn" onclick="triggerSweep()">🔍 Trigger Intelligence Sweep</button>
        <a href="/docs" class="action-btn secondary">📄 API Docs</a>
    </div>

    <div id="sweepResult"></div>
</div>

<script>
async function triggerSweep() {{
    const btn = document.getElementById('sweepBtn');
    const result = document.getElementById('sweepResult');
    btn.disabled = true;
    btn.textContent = '⏳ Sweep in progress...';
    result.className = '';
    result.style.display = 'none';

    try {{
        const res = await fetch('/api/cio/process', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{}})
        }});
        const data = await res.json();

        if (res.ok && data.memo_filename) {{
            result.className = 'success';
            result.innerHTML = '✅ Sweep complete! Memo: <strong>' + data.memo_filename + '</strong><br>Duration: ' + data.duration_seconds.toFixed(1) + 's | Sources: ' + data.external_sources_crawled + ' | Snippets: ' + data.external_snippets_total;
        }} else if (res.ok) {{
            result.className = 'success';
            result.innerHTML = '⚠️ Sweep finished but no memo was generated. Check server logs.';
        }} else {{
            result.className = 'error';
            result.innerHTML = '❌ ' + (data.error || data.detail || 'Unknown error');
        }}
    }} catch (err) {{
        result.className = 'error';
        result.innerHTML = '❌ Connection error: ' + err.message;
    }} finally {{
        btn.disabled = false;
        btn.textContent = '🔍 Trigger Intelligence Sweep';
    }}
}}

async function authorizeUpgrade(filename) {{
    const directive = prompt("Enter directive for Master Architect (e.g., 'Apply all high-priority fixes'):", "Apply CIO recommended architectural upgrades.");
    if (!directive) return;

    const result = document.getElementById('sweepResult');
    result.className = '';
    result.style.display = 'block';
    result.innerHTML = '⏳ Dispatching authorization to War Room...';

    try {{
        const res = await fetch('/api/cio/authorize', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                memo_filename: filename,
                directive: directive
            }})
        }});
        const data = await res.json();

        if (res.ok) {{
            result.className = 'success';
            result.innerHTML = '🚀 <strong>Authorization Sent!</strong><br>' + data.message;
        }} else {{
            result.className = 'error';
            result.innerHTML = '❌ ' + (data.error || 'Failed to dispatch.');
        }}
    }} catch (err) {{
        result.className = 'error';
        result.innerHTML = '❌ Connection error: ' + err.message;
    }}
}}
</script>
</body>
</html>"""
    return HTMLResponse(html)


# ── Health Check ──────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "online",
        "agent": "CIO_Agent",
        "role": "Chief Innovation Officer",
        "version": "1.0.0",
        "port": 5090,
        "last_sweep": sweep_state.get("last_sweep"),
        "sweep_count": sweep_state.get("sweep_count", 0),
        "is_running": sweep_state.get("is_running", False),
    }


# ── Process: Trigger Intelligence Sweep ──────────────────
@app.post("/api/cio/process")
async def process_sweep(req: CIOProcessRequest = CIOProcessRequest()):
    """Trigger a full intelligence sweep (on-demand)."""
    if sweep_state["is_running"]:
        return JSONResponse(
            status_code=409,
            content={"error": "A sweep is already in progress. Please wait."}
        )

    sweep_state["is_running"] = True
    asyncio.create_task(sse_broadcast("RUNNING", "Initiating 3-Phase Architecture Audit", "INFO"))
    
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, run_full_sweep, req.focus_areas)
        sweep_state["last_sweep"] = datetime.now().isoformat()
        sweep_state["last_result"] = result
        sweep_state["sweep_count"] += 1
        
        asyncio.create_task(sse_broadcast(
            "PASS" if result.get('memo_generated') else "FAIL", 
            f"Sweep Complete via {result.get('llm_provider', 'unknown')}", 
            "TEST_PASS" if result.get('memo_generated') else "TEST_FAIL"
        ))
        return result
    except Exception as e:
        logger.error(f"Sweep failed: {e}")
        asyncio.create_task(sse_broadcast("FAIL", f"Sweep failed: {e}", "TEST_FAIL"))
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        sweep_state["is_running"] = False


# ── List Memos ────────────────────────────────────────────
@app.get("/api/cio/memos")
async def get_memos():
    """List all generated Upgrade Memos."""
    return list_memos()


# ── Read Specific Memo ────────────────────────────────────
@app.get("/api/cio/memos/{filename}")
async def get_memo(filename: str):
    """Read a specific memo by filename."""
    content = read_memo(filename)
    if content is None:
        return JSONResponse(status_code=404, content={"error": "Memo not found"})
    return PlainTextResponse(content, media_type="text/markdown")


# ── Authorize Upgrade → Master Architect ──────────────────
@app.post("/api/cio/authorize")
async def authorize_upgrade(req: AuthorizeUpgradeRequest):
    """
    Bundles a memo with user directive and routes it to the
    Master Architect via the War Room dispatch endpoint.
    """
    memo_content = read_memo(req.memo_filename)
    if memo_content is None:
        return JSONResponse(status_code=404, content={"error": f"Memo '{req.memo_filename}' not found"})

    # Build the dispatch payload for the Master Architect
    dispatch_payload = {
        "message": (
            f"[CIO AUTHORIZED UPGRADE]\n\n"
            f"Director Directive: {req.directive}\n\n"
            f"--- BEGIN CIO MEMO ---\n"
            f"{memo_content[:8000]}\n"
            f"--- END CIO MEMO ---"
        ),
        "strategy_mode": "cio_authorized_upgrade",
        "stress_test": False,
    }

    try:
        resp = sync_requests.post(
            "http://localhost:5000/api/war-room/dispatch",
            json=dispatch_payload,
            headers={
                "X-Antigravity-Agent": "CIO_Agent",
                "X-Sentinel-Relay": "secure-signature-verified",
            },
            timeout=10
        )
        logger.info(f"Authorized upgrade dispatched to Master Architect: {resp.status_code}")
        return {
            "status": "dispatched",
            "message": f"Upgrade memo '{req.memo_filename}' authorized and sent to Master Architect.",
            "war_room_status": resp.status_code,
        }
    except Exception as e:
        logger.error(f"Failed to dispatch authorized upgrade: {e}")
        return JSONResponse(
            status_code=502,
            content={"error": f"Failed to reach Master Architect: {str(e)}"}
        )


# ═══════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=5090, reload=True)
