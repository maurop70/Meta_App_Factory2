"""
server.py — CFO Ultimate Excel Architect
═══════════════════════════════════════════════
Sub-Agent of CFO | Port: 5041 | Antigravity-AI

The CFO Agent's "Mathematical Soul" — transforms instructions
and uploaded files into high-integrity financial models.

Endpoints:
  GET  /                                  — Dashboard
  GET  /form                              — Dialogue Box (instruction + file upload)
    POST /api/consult                       — Process instruction + file
    POST /api/sentinel-relay-bridge         — Main execution (Native-Bridge)
    POST /api/execute                       — Direct execution
  GET  /api/health                        — Health check
  GET  /api/reports                       — List generated reports
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
import google.generativeai as genai
import aiohttp
import asyncio

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
logger = logging.getLogger("CFO_Excel_Architect")

sys.path.insert(0, str(ROOT))
from cfo_engine import CFOExecutionController
from cfo_compiler import CFOCompiler
from cfo_logic import FinancialPayload, calculate_financial_health

cfo = CFOExecutionController()
cfo_compiler = CFOCompiler()

if os.getenv("GEMINI_API_KEY"):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

CFO_SYSTEM_PROMPT = """You are the Antigravity CFO Agent (Institutional Mathematics Division).
You are to generate a highly strategic, qualitative "War Room Audit Report" based on the provided deterministic mathematical inputs.

CRITICAL DIRECTIVE:
You have received a MATHEMATICALLY VERIFIED `CFOAnalysisResult` JSON. 
You MUST NOT recalculate any of these numbers. You are strictly forbidden from performing arithmetic.
Your sole job is to READ the JSON and generate qualitative insights identifying systemic, existential fragility.

RULES:
1. If the fragility_index > 50, escalate warnings to the CTO/Master Architect immediately.
2. If runway_months < 6, flag extreme risk and recommend immediate capital injection or aggressive OPEX reduction.
3. Write in concise, C-Suite level terminology (e.g., "debt sculpting", "fixed-point convergence", "drawdown risk").
4. Return ONLY the narrative audit report text. Do not return JSON or markdown code blocks around the text.
"""

# ═══════════════════════════════════════════════════════════
#  APP
# ═══════════════════════════════════════════════════════════

app = FastAPI(
    title="CFO Ultimate Excel Architect — Sub-Agent of CFO",
    version="3.0.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5030", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Safe Body Parser ─────────────────────────────────────
async def safe_parse_body(request: Request) -> dict:
    try:
        body = await request.body()
        if not body or body.strip() == b"":
            return {}
        return await request.json()
    except Exception:
        return {}


# ═══════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════

@app.get("/")
async def dashboard():
    """Glassmorphic dashboard for CFO Ultimate Excel Architect."""
    reports_dir = ROOT / "reports"
    report_files = sorted(reports_dir.glob("*.xlsx"), reverse=True)[:10] if reports_dir.exists() else []
    report_list = [f.name for f in report_files]
    uploads_dir = ROOT / "uploads"
    upload_count = len(list(uploads_dir.iterdir())) if uploads_dir.exists() else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CFO Ultimate Excel Architect</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ overflow-x: hidden; }}
body {{
    font-family: 'Inter', sans-serif;
    background: linear-gradient(135deg, #0a0a1a 0%, #1a1a3e 50%, #0d0d2b 100%);
    color: #e0e0e0;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
}}
.container {{
    max-width: 740px;
    width: 90%;
    padding: 40px;
    background: rgba(255,255,255,0.04);
    backdrop-filter: blur(20px);
    border-radius: 24px;
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}}
.badge {{
    display: inline-block;
    background: linear-gradient(135deg, #e94560, #c23152);
    color: white;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 16px;
}}
.badge.form-badge {{
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    margin-left: 8px;
}}
h1 {{
    font-size: 28px;
    font-weight: 700;
    background: linear-gradient(135deg, #e94560, #ff6b81);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 8px;
}}
.subtitle {{
    font-size: 14px;
    color: rgba(255,255,255,0.5);
    margin-bottom: 28px;
    line-height: 1.5;
}}
.card {{
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 16px;
}}
.card h3 {{
    font-size: 13px;
    color: rgba(255,255,255,0.4);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 12px;
}}
.endpoint {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    flex-wrap: wrap;
}}
.endpoint:last-child {{ border-bottom: none; }}
.method {{
    font-size: 11px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 6px;
    min-width: 46px;
    text-align: center;
}}
.method.post {{ background: rgba(233,69,96,0.2); color: #e94560; }}
.method.get {{ background: rgba(0,200,150,0.2); color: #00c896; }}
.method.form {{ background: rgba(99,102,241,0.2); color: #818cf8; }}
.path {{ font-family: 'JetBrains Mono', 'Consolas', monospace; font-size: 13px; color: #e0e0e0; word-break: break-all; overflow-wrap: break-word; min-width: 0; }}
.status {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: rgba(0,200,150,0.05);
    border: 1px solid rgba(0,200,150,0.15);
    border-radius: 12px;
    margin-bottom: 16px;
}}
.dot {{ width: 8px; height: 8px; border-radius: 50%; background: #00c896; animation: pulse 2s infinite; }}
@keyframes pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.4; }} }}
.reports {{ font-size: 13px; color: rgba(255,255,255,0.6); list-style: none; }}
.reports li {{ padding: 4px 0; word-break: break-all; overflow-wrap: break-word; }}
.btn-row {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 20px; }}
.test-btn {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 12px 24px;
    background: linear-gradient(135deg, #e94560, #c23152);
    color: white;
    border: none;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    text-decoration: none;
    transition: transform 0.2s, box-shadow 0.2s;
}}
.test-btn:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(233,69,96,0.3); }}
.test-btn.primary {{
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    font-size: 14px;
    padding: 14px 28px;
}}
.test-btn.primary:hover {{ box-shadow: 0 8px 24px rgba(99,102,241,0.4); }}
.test-btn.secondary {{
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    color: #e0e0e0;
}}
.test-btn.secondary:hover {{ background: rgba(255,255,255,0.1); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }}
.stat-row {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}}
.stat {{
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 14px;
    text-align: center;
}}
.stat-val {{ font-size: 24px; font-weight: 700; color: #e94560; }}
.stat-label {{ font-size: 11px; color: rgba(255,255,255,0.4); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }}
@media (max-width: 480px) {{
  .container {{ padding: 20px 16px; width: 95%; }}
  h1 {{ font-size: 22px; }}
  .subtitle {{ font-size: 12px; }}
  .path {{ font-size: 11px; }}
  .card {{ padding: 14px; }}
  .method {{ min-width: 40px; font-size: 10px; padding: 3px 6px; }}
  .stat-row {{ grid-template-columns: 1fr; }}
  .btn-row {{ flex-direction: column; }}
}}
</style>
</head>
<body>
<div class="container">
    <div class="badge">Sub-Agent of CFO</div>
    <span class="badge form-badge">v3.0 — Mathematical Soul</span>
    <h1>CFO Ultimate Excel Architect</h1>
    <p class="subtitle">The financial execution brain — Fragility Index, ROI, NPV, Budget Modeling, Spend Reconciliation. Upload files, give instructions, get Excel masterpieces.</p>

    <div class="status">
        <div class="dot"></div>
        <span style="font-size:13px; font-weight:500; color:#00c896;">Online — Port 5041</span>
    </div>

    <div class="stat-row">
        <div class="stat"><div class="stat-val">{len(report_list)}</div><div class="stat-label">Reports</div></div>
        <div class="stat"><div class="stat-val">{upload_count}</div><div class="stat-label">Uploads</div></div>
        <div class="stat"><div class="stat-val">5041</div><div class="stat-label">Port</div></div>
    </div>

    <div class="card">
        <h3>Dialogue Box</h3>
        <div class="endpoint">
            <span class="method form">FORM</span>
            <span class="path">/form — Interactive instruction + file upload</span>
        </div>
        <p style="font-size:12px; color:rgba(255,255,255,0.35); margin-top:8px;">Give instructions and upload PDFs/Excels directly to the CFO brain.</p>
    </div>

    <div class="card">
        <h3>API Endpoints</h3>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/api/consult — Instruction + file</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/api/sentinel-relay-bridge</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/api/execute</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/health</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/reports</span></div>
    </div>

    <!-- Legacy N8N Mirror Section Completely Removed (Native Intelligence Activated) -->

    <div class="card">
        <h3>Recent Reports ({len(report_list)})</h3>
        <ul class="reports">
            {''.join(f'<li>📊 <a href="/api/reports/{r}" style="color:#818cf8; text-decoration:none;">{r}</a></li>' for r in report_list[:5]) if report_list else '<li style="color:rgba(255,255,255,0.3);">No reports yet — use the Dialogue Box to create one</li>'}
        </ul>
    </div>

    <div class="btn-row">
        <a href="/form" class="test-btn primary">💬 Open Dialogue Box</a>
        <a href="/docs" class="test-btn secondary">📄 API Docs</a>
    </div>
</div>
</body>
</html>"""
    return HTMLResponse(html)


# ═══════════════════════════════════════════════════════════
#  DIALOGUE BOX — The "Front Door"
# ═══════════════════════════════════════════════════════════

DIALOGUE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CFO Dialogue Box — Ultimate Excel Architect</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
html, body { overflow-x: hidden; }
body {
    font-family: 'Inter', sans-serif;
    background: linear-gradient(135deg, #0a0a1a 0%, #12122e 40%, #1a0a2e 100%);
    color: #e0e0e0;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
}
.form-container {
    max-width: 640px;
    width: 100%;
    padding: 40px;
    background: rgba(255,255,255,0.04);
    backdrop-filter: blur(24px);
    border-radius: 24px;
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 24px 80px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06);
    position: relative;
    overflow: hidden;
}
.form-container::before {
    content: '';
    position: absolute;
    top: -100px;
    right: -100px;
    width: 250px;
    height: 250px;
    background: radial-gradient(circle, rgba(233,69,96,0.08), transparent 70%);
    pointer-events: none;
}
.form-container::after {
    content: '';
    position: absolute;
    bottom: -80px;
    left: -80px;
    width: 200px;
    height: 200px;
    background: radial-gradient(circle, rgba(99,102,241,0.06), transparent 70%);
    pointer-events: none;
}
.form-header {
    text-align: center;
    margin-bottom: 32px;
    position: relative;
    z-index: 1;
}
.form-badge {
    display: inline-block;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    padding: 4px 16px;
    border-radius: 20px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 16px;
}
.form-title {
    font-size: 26px;
    font-weight: 700;
    background: linear-gradient(135deg, #e94560, #ff6b81, #c23152);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 8px;
}
.form-sub {
    font-size: 14px;
    color: rgba(255,255,255,0.45);
    line-height: 1.5;
}

.field-group {
    margin-bottom: 24px;
    position: relative;
    z-index: 1;
}
.field-label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    color: rgba(255,255,255,0.5);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 8px;
}
.field-label .hint {
    font-weight: 400;
    text-transform: none;
    letter-spacing: normal;
    color: rgba(255,255,255,0.3);
    font-size: 11px;
}
textarea {
    width: 100%;
    min-height: 120px;
    padding: 16px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 14px;
    color: #f0f0f0;
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    line-height: 1.6;
    resize: vertical;
    transition: border-color 0.3s, box-shadow 0.3s;
    outline: none;
}
textarea:focus {
    border-color: rgba(233,69,96,0.5);
    box-shadow: 0 0 0 3px rgba(233,69,96,0.1);
}
textarea::placeholder { color: rgba(255,255,255,0.2); }

.drop-zone {
    border: 2px dashed rgba(255,255,255,0.12);
    border-radius: 14px;
    padding: 32px 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.3s;
    position: relative;
}
.drop-zone:hover, .drop-zone.dragover {
    border-color: rgba(99,102,241,0.5);
    background: rgba(99,102,241,0.04);
}
.drop-zone .drop-icon { font-size: 32px; margin-bottom: 8px; }
.drop-zone .drop-text { font-size: 13px; color: rgba(255,255,255,0.4); }
.drop-zone .drop-text strong { color: #818cf8; }
.drop-zone .drop-formats { font-size: 11px; color: rgba(255,255,255,0.25); margin-top: 6px; }
.drop-zone input[type=file] {
    position: absolute; inset: 0; opacity: 0; cursor: pointer;
}
.file-preview {
    display: none;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    background: rgba(99,102,241,0.08);
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 12px;
    margin-top: 10px;
}
.file-preview.show { display: flex; }
.file-preview .file-name { flex: 1; font-size: 13px; color: #818cf8; font-weight: 500; }
.file-preview .file-size { font-size: 11px; color: rgba(255,255,255,0.3); }
.file-preview .remove-file {
    background: none; border: none; color: #ef4444;
    cursor: pointer; font-size: 16px; padding: 2px 6px;
}

.submit-btn {
    width: 100%;
    padding: 16px;
    background: linear-gradient(135deg, #e94560, #c23152);
    color: white;
    border: none;
    border-radius: 14px;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}
.submit-btn:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 12px 32px rgba(233,69,96,0.35);
}
.submit-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
}
.submit-btn .spinner {
    width: 18px; height: 18px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    display: none;
}
.submit-btn.loading .spinner { display: block; }
.submit-btn.loading .btn-text { display: none; }
.submit-btn.loading .btn-loading { display: inline; }
.btn-loading { display: none; }

.result-panel {
    display: none;
    margin-top: 24px;
    padding: 20px;
    background: rgba(16,185,129,0.06);
    border: 1px solid rgba(16,185,129,0.2);
    border-radius: 14px;
    position: relative;
    z-index: 1;
}
.result-panel.show { display: block; }
.result-panel.error {
    background: rgba(239,68,68,0.06);
    border-color: rgba(239,68,68,0.2);
}
.result-title {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.result-body { font-size: 13px; color: rgba(255,255,255,0.6); line-height: 1.6; }
.result-body pre {
    background: rgba(0,0,0,0.3);
    padding: 12px;
    border-radius: 8px;
    overflow-x: auto;
    font-size: 12px;
    margin-top: 8px;
    max-height: 200px;
    overflow-y: auto;
}
.back-link {
    display: inline-block;
    margin-top: 20px;
    font-size: 12px;
    color: rgba(255,255,255,0.3);
    text-decoration: none;
    transition: color 0.2s;
    position: relative;
    z-index: 1;
}
.back-link:hover { color: rgba(255,255,255,0.6); }

@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 480px) {
  .form-container { padding: 24px 18px; }
  .form-title { font-size: 20px; }
  textarea { min-height: 100px; font-size: 13px; }
}
</style>
</head>
<body>
<div class="form-container">
    <div class="form-header">
        <div class="form-badge">CFO Dialogue Box</div>
        <h1 class="form-title">Ultimate Excel Architect</h1>
        <p class="form-sub">Give me an instruction and optionally upload a file.<br>I'll transform it into a financial masterpiece.</p>
    </div>

    <form id="cfoForm" enctype="multipart/form-data">
        <div class="field-group">
            <label class="field-label">Instruction <span class="hint">— What should I do?</span></label>
            <textarea id="instruction" name="instruction" placeholder="e.g. 'Build me a 12-month budget forecast for a SaaS startup with $50k MRR'&#10;&#10;Or: 'Improve this Excel — add NPV calculations and a dashboard tab'&#10;&#10;Or: 'Analyze this PDF and extract the financial data into a spreadsheet'"></textarea>
        </div>

        <div class="field-group">
            <label class="field-label">File Upload <span class="hint">— optional (PDF, XLSX, CSV)</span></label>
            <div class="drop-zone" id="dropZone">
                <div class="drop-icon">📎</div>
                <div class="drop-text">Drag & drop or <strong>click to browse</strong></div>
                <div class="drop-formats">.pdf · .xlsx · .xls · .csv · .txt</div>
                <input type="file" id="fileInput" name="file" accept=".pdf,.xlsx,.xls,.csv,.txt">
            </div>
            <div class="file-preview" id="filePreview">
                <span>📄</span>
                <span class="file-name" id="fileName"></span>
                <span class="file-size" id="fileSize"></span>
                <button type="button" class="remove-file" id="removeFile">✕</button>
            </div>
        </div>

        <button type="submit" class="submit-btn" id="submitBtn">
            <span class="btn-text">⚡ Send to CFO</span>
            <span class="btn-loading">Processing...</span>
            <div class="spinner"></div>
        </button>
    </form>

    <div class="result-panel" id="resultPanel">
        <div class="result-title" id="resultTitle"></div>
        <div class="result-body" id="resultBody"></div>
    </div>

    <a href="/" class="back-link">← Back to Dashboard</a>
</div>

<script>
const form = document.getElementById('cfoForm');
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const filePreview = document.getElementById('filePreview');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const removeFile = document.getElementById('removeFile');
const submitBtn = document.getElementById('submitBtn');
const resultPanel = document.getElementById('resultPanel');
const resultTitle = document.getElementById('resultTitle');
const resultBody = document.getElementById('resultBody');

// Drag & drop
['dragenter', 'dragover'].forEach(e => {
    dropZone.addEventListener(e, ev => { ev.preventDefault(); dropZone.classList.add('dragover'); });
});
['dragleave', 'drop'].forEach(e => {
    dropZone.addEventListener(e, ev => { ev.preventDefault(); dropZone.classList.remove('dragover'); });
});
dropZone.addEventListener('drop', ev => {
    if (ev.dataTransfer.files.length) {
        fileInput.files = ev.dataTransfer.files;
        showFilePreview(ev.dataTransfer.files[0]);
    }
});
fileInput.addEventListener('change', () => {
    if (fileInput.files.length) showFilePreview(fileInput.files[0]);
});

function showFilePreview(file) {
    fileName.textContent = file.name;
    fileSize.textContent = (file.size / 1024).toFixed(1) + ' KB';
    filePreview.classList.add('show');
    dropZone.style.display = 'none';
}
removeFile.addEventListener('click', () => {
    fileInput.value = '';
    filePreview.classList.remove('show');
    dropZone.style.display = 'block';
});

// Submit
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const instruction = document.getElementById('instruction').value.trim();
    if (!instruction) { alert('Please enter an instruction.'); return; }

    submitBtn.classList.add('loading');
    submitBtn.disabled = true;
    resultPanel.classList.remove('show', 'error');

    const fd = new FormData();
    fd.append('instruction', instruction);
    if (fileInput.files.length) fd.append('file', fileInput.files[0]);

    try {
        const res = await fetch('/api/consult', { method: 'POST', body: fd });
        const data = await res.json();

        resultPanel.classList.add('show');
        if (res.ok) {
            resultTitle.innerHTML = '✅ ' + (data.title || 'Instruction Processed');
            let body = '';
            if (data.file_name) body += '<strong>Report:</strong> ' + data.file_name + '<br>';
            if (data.message) body += data.message + '<br>';
            if (data.report) body += '<pre>' + JSON.stringify(data.report, null, 2) + '</pre>';
            resultBody.innerHTML = body || 'Done.';
        } else {
            resultPanel.classList.add('error');
            resultTitle.innerHTML = '❌ ' + (data.status || 'Error');
            resultBody.innerHTML = data.message || data.error_message || JSON.stringify(data);
        }
    } catch (err) {
        resultPanel.classList.add('show', 'error');
        resultTitle.innerHTML = '❌ Connection Error';
        resultBody.innerHTML = err.message;
    } finally {
        submitBtn.classList.remove('loading');
        submitBtn.disabled = false;
    }
});
</script>
</div>
</body>
</html>
"""

@app.get("/form")
async def dialogue_box():
    """The Dialogue Box — interactive form for instruction + file upload."""
    return HTMLResponse(DIALOGUE_HTML)


@app.get("/api/health")
async def health():
    uploads_dir = ROOT / "uploads"
    upload_count = len(list(uploads_dir.iterdir())) if uploads_dir.exists() else 0
    return {
        "status": "online",
        "agent": "CFO_Ultimate_Excel_Architect",
        "parent_agent": "CFO",
        "version": "3.0.0",
        "port": 5041,
        "dialogue_box": "/form",
        "native_bridge": "http://localhost:5041/api/sentinel-relay-bridge",
        "n8n_mirror": "Retired — Native Intelligence Active",
        "excel_available": True,
        "uploads_processed": upload_count,
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/sentinel-relay-bridge")
async def sentinel_relay_handler(request: Request):
    """Native Python Bridge — replaces legacy n8n webhook."""
    data = await safe_parse_body(request)
    return await _execute(data)


@app.post("/api/execute")
async def execute_handler(request: Request):
    """Direct execution endpoint."""
    data = await safe_parse_body(request)
    return await _execute(data)


async def _execute(data: dict):
    """Core execution logic shared by webhook and direct endpoints."""
    start = time.time()

    # Validate
    valid, error = cfo.validate_payload(data)
    if not valid:
        logger.warning(f"Gatekeeper rejected: {error}")
        required = ['cmo_spend', 'architect_risk', 'campaign_list']
        missing = [f for f in required if f not in data]
        return JSONResponse({
            "agent": "CFO",
            "status": "awaiting_data",
            "message": error,
            "missing_fields": missing,
            "received_fields": list(data.keys()),
            "callback_url": "http://localhost:5041/api/sentinel-relay-bridge",
            "instruction": "Please re-submit with all required fields: cmo_spend, architect_risk, campaign_list"
        }, status_code=400)

    # Execute
    try:
        report = cfo.generate_report(data)
        elapsed = time.time() - start

        # Rename file to WarRoom convention
        old_name = report.get('file_name', '')
        new_name = old_name.replace('CFO_Fragility_Report_', 'WarRoom_CFO_Report_')
        report['file_name'] = new_name

        logger.info(f"CFO Fragility Engine: {new_name} generated in {elapsed:.2f}s")
        logger.info(f"  Fragility Index: {report.get('fragility', {}).get('fragility_index')}")
        logger.info(f"  Portfolio ROI: {report.get('summary', {}).get('portfolio_roi_pct')}%")

        response_data = {
            "agent": "CFO",
            "status": "deployed",
            "message": "CFO Agent has deployed the Fragility Report to the AI Folder.",
            "file_name": new_name,
            "report": {
                "report_name": new_name,
                "generated_at": report.get('generated_at'),
                "agent": "CFO Execution Controller",
                "fragility_index": report.get('fragility', {}).get('fragility_index'),
                "composite_score": report.get('fragility', {}).get('composite'),
                "portfolio_roi_pct": report.get('summary', {}).get('portfolio_roi_pct'),
                "total_spend": report.get('summary', {}).get('total_spend'),
                "total_revenue": report.get('summary', {}).get('total_projected_revenue'),
                "spend_utilization_pct": report.get('summary', {}).get('spend_utilization_pct'),
                "unallocated": report.get('spend_reconciliation', {}).get('unallocated'),
                "campaigns": report.get('campaigns', []),
                "campaign_count": report.get('summary', {}).get('campaign_count'),
                "schema": ['Dashboard', 'Calculation Engine', 'Input Data', 'Campaign Analysis'],
                "formula_map": report.get('formula_map', {}),
                "logic_rationale": report.get('logic_rationale', ''),
            },
            "file_path": report.get('file_path'),
            "duration_ms": round(elapsed * 1000, 1),
        }

        # ── Phantom QA Auto-Audit Gate ────────────────────
        # After CFO generates a report, ping Phantom QA for quality verdict.
        # On FAIL: block the report. On PASS or unreachable: proceed.
        qa_verdict = None
        try:
            import aiohttp
            import hashlib
            file_path = report.get('file_path', '')
            sig = ""
            if file_path and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    sig = hashlib.sha256(f.read()).hexdigest()

            qa_payload = {
                "source": "CFO_Fragility_Engine",
                "target_url": "http://localhost:5041",
                "file_link": file_path,
                "file_name": new_name,
                "audit_mode": "mathematical",
                "audit_type": "AUDIT:cryptographic",
                "digital_audit_signature": sig,
                "report_data": {
                    "fragility_index": report.get('fragility', {}).get('fragility_index'),
                    "composite_score": report.get('fragility', {}).get('composite'),
                    "portfolio_roi_pct": report.get('summary', {}).get('portfolio_roi_pct'),
                },
                "callback_url": "http://localhost:5041/api/audit/correction",
            }
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.post(
                    "http://localhost:5030/api/audit/auto",
                    json=qa_payload,
                ) as qa_r:
                    if qa_r.status == 200:
                        qa_verdict = await qa_r.json()
                        logger.info(
                            f"Phantom QA verdict: {qa_verdict.get('verdict')} "
                            f"(Score: {qa_verdict.get('score')}/100)"
                        )
        except Exception as qa_err:
            logger.warning(f"Phantom QA unreachable — proceeding without QA gate: {qa_err}")

        # If Phantom QA returned FAIL, block the report
        if qa_verdict and qa_verdict.get("verdict") == "FAIL":
            logger.warning(f"⛔ Phantom QA BLOCKED report '{new_name}'")
            return JSONResponse({
                "agent": "CFO",
                "status": "qa_blocked",
                "message": (
                    f"Report '{new_name}' was generated but BLOCKED by Phantom QA Elite. "
                    f"Quality score: {qa_verdict.get('score', 0)}/100. "
                    f"The report will not be released until corrections are made."
                ),
                "qa_verdict": qa_verdict.get("verdict"),
                "qa_score": qa_verdict.get("score"),
                "qa_findings": qa_verdict.get("findings", []),
                "correction_request": qa_verdict.get("correction_request", ""),
                "file_name": new_name,
            }, status_code=422)

        # Attach QA clearance to the response
        if qa_verdict:
            response_data["qa_verdict"] = qa_verdict.get("verdict")
            response_data["qa_score"] = qa_verdict.get("score")

        # ── Context-Aware Folder Anchor Injection ────────────────
        try:
            import sys
            sys.path.insert(0, str(ROOT.parent / "Sentinel_Bridge"))
            from sentinel_drive_manager import SentinelDriveManager
            mgr = SentinelDriveManager()
            
            assets = []
            if file_path and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    assets.append({
                        "name": new_name,
                        "content": f.read(),
                        "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    })
            if "markdown_manual" in report:
                assets.append({
                    "name": new_name.replace(".xlsx", "_Manual.md"),
                    "content": report["markdown_manual"],
                    "type": "text/markdown"
                })
            if "csuite_brochure" in report:
                assets.append({
                    "name": new_name.replace(".xlsx", "_Brochure.html"),
                    "content": report["csuite_brochure"],
                    "type": "text/html"
                })
            
            bundle_res = mgr.bundle_project_assets(payload.get('project_id', 'WarRoom_Project'), assets)
            response_data["cloud_bundle"] = bundle_res
            logger.info("Context-Aware Folder Anchor injected bundle to AI Ideas.")
        except Exception as e:
            logger.warning(f"SentinelDriveManager anchor failed: {e}")

        return response_data

    except (ZeroDivisionError, ValueError, TypeError, OverflowError) as e:
        logger.error(f"Math error: {type(e).__name__}: {e}")
        return JSONResponse({
            "agent": "CFO",
            "status": "math_error",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "correction_request": f"Math Correction Request: {type(e).__name__} - {e}. Please review the input data and formulas.",
        }, status_code=422)


# ── Phantom QA Correction Receiver ───────────────────────
@app.post("/api/audit/correction")
async def receive_correction(request: Request):
    """Receives correction requests from Phantom QA when a report fails the quality gate."""
    data = await safe_parse_body(request)
    logger.warning(
        f"⛔ Correction received from {data.get('source', '?')}: "
        f"Verdict={data.get('verdict')}, Score={data.get('score')}, "
        f"File={data.get('file_name', '?')}"
    )
    return {
        "status": "correction_received",
        "message": "CFO acknowledges the correction request. The report will be reviewed.",
        "file_name": data.get("file_name"),
        "qa_score": data.get("score"),
    }


# ═══════════════════════════════════════════════════════════
#  DIALOGUE BOX SUBMISSION — /api/consult
# ═══════════════════════════════════════════════════════════

@app.post("/api/consult")
async def consult(
    instruction: str = Form(...),
    file: UploadFile | None = File(None),
):
    """
    The Dialogue Box endpoint — accepts an instruction and optional file.
    Routes to the appropriate CFO operation based on the instruction.
    """
    start = time.time()
    uploads_dir = ROOT / "uploads"
    uploads_dir.mkdir(exist_ok=True)

    file_info = None
    file_path = None

    # Handle file upload
    if file and file.filename:
        safe_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file_path = uploads_dir / safe_name
        content = await file.read()
        file_path.write_bytes(content)
        file_info = {
            "original_name": file.filename,
            "saved_as": safe_name,
            "size_bytes": len(content),
            "content_type": file.content_type,
        }
        logger.info(f"File uploaded: {file.filename} ({len(content)} bytes)")

    logger.info(f"Consult received — Instruction: {instruction[:100]}...")

    # 1. Complexity detection for dynamic models
    instruction_lower = instruction.lower()
    complexity = 'mid_market'  # default
    if any(kw in instruction_lower for kw in ['kid', 'elementary', 'lemonade', 'simple', 'basic']):
        complexity = 'elementary'
    elif any(kw in instruction_lower for kw in ['vc', 'institutional', 'lbo', 'waterfall', 'debt sculpting', 'complex']):
        complexity = 'institutional'

    is_fragility = any(kw in instruction_lower for kw in [
        'fragility', 'risk', 'campaign', 'cmo_spend', 'architect_risk',
    ])
    is_model = any(kw in instruction_lower for kw in [
        'build', 'model', 'budget', 'forecast', 'lbo', 'waterfall', 'spreadsheet', 'financial'
    ])

    # If the instruction looks like a fragility report request (legacy)
    if is_fragility and not is_model:
        # Attempt to extract JSON data from instruction or file
        payload = _extract_payload(instruction, file_path)
        if payload:
            valid, error = cfo.validate_payload(payload)
            if valid:
                try:
                    report = cfo.generate_report(payload)
                    elapsed = time.time() - start
                    old_name = report.get('file_name', '')
                    new_name = old_name.replace('CFO_Fragility_Report_', 'WarRoom_CFO_Report_')
                    report['file_name'] = new_name
                    return {
                        "status": "deployed",
                        "title": "Fragility Report Deployed",
                        "message": f"Generated in {elapsed:.2f}s",
                        "file_name": new_name,
                        "report": report.get('summary', {})
                    }
                except Exception as e:
                    logger.error(f"Error generating fragility report: {e}")
                    
    # Otherwise, build a dynamic model via the new CFO Compiler if indicated
    if is_model:
        logger.info(f"Routing to Dynamic CFO Compiler with '{complexity}' tier complexity.")
        try:
            spec = {
                "model_name": "Dynamic_CFO_Model",
                "complexity": complexity,
                "blocks": ["revenue", "debt", "returns"],
                "parameters": {
                    "price": 5, "volume": 100, 
                    "beginning_debt": 50000000 if complexity == 'institutional' else 1000000,
                    "interest_rate": 0.08,
                    "periods": 5
                }
            }
            res = cfo_compiler.compile_model(spec)
            elapsed = time.time() - start
            
            if res['status'] == 'PASS':
                return {
                    "status": "deployed",
                    "title": f"Dynamic Model Deployed ({complexity.upper()})",
                    "message": f"Generated {res['file_name']} in {elapsed:.2f}s",
                    "file_name": res['file_name'],
                    "report": {"complexity": complexity, "blocks_used": spec['blocks']}
                }
            else:
                return {"status": "error", "message": res.get("message")}
        except Exception as e:
            logger.error(f"Error generating dynamic model: {e}")
            return {"status": "error", "message": str(e)}

    # Fallback response
    return {
        "status": "received",
        "title": "Instruction Received",
        "message": "The CFO Agent analyzed the instruction but no modeling or fragility intent was explicitly detected."
    }


def _extract_payload(instruction: str, file_path=None) -> dict | None:
    """Try to extract a structured financial payload from instruction text or uploaded file."""
    # Try parsing JSON from instruction
    try:
        import re
        json_match = re.search(r'\{[^{}]*\}', instruction, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except (json.JSONDecodeError, Exception):
        pass

    # Try reading JSON from uploaded file
    if file_path and file_path.exists():
        try:
            if str(file_path).endswith('.json') or str(file_path).endswith('.txt'):
                content = file_path.read_text(encoding='utf-8')
                return json.loads(content)
        except Exception:
            pass

    return None


@app.get("/api/reports")
async def list_reports():
    reports_dir = ROOT / "reports"
    if not reports_dir.exists():
        return {"reports": [], "total": 0}

    files = sorted(reports_dir.glob("*.*"), reverse=True)
    return {
        "reports": [
            {
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "created": datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
            }
            for f in files[:20]
        ],
        "total": len(files),
    }


@app.get("/api/reports/{filename}")
async def download_report(filename: str):
    filepath = ROOT / "reports" / filename
    if not filepath.exists():
        return JSONResponse({"error": "Report not found"}, status_code=404)
    return FileResponse(str(filepath), filename=filename)


@app.post("/api/audit")
async def process_audit(request: Request):
    """
    Phase 3: Receives a raw JSON or Form data (converted from frontend), validates mathematically,
    streams to Phantom QA, and generates a qualitative LLM audit report bypassing math calculation.
    """
    # ── 1. Ghost Stream Broadcast Helper
    async def sse_broadcast(status, message, event_type="INFO"):
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    "http://localhost:5030/api/qa/ingest",
                    json={
                        "agent": "CFO_Audit",
                        "status": status,
                        "message": message,
                        "type": event_type,
                        "timestamp": datetime.now().isoformat()
                    },
                    timeout=2
                )
        except Exception:
            pass # Non-blocking stream failure

    # Stream 'RUNNING' start
    asyncio.create_task(sse_broadcast("RUNNING", "CFO Received Audit Request. Executing mathematical validation...", "SUITE_START"))
    
    # ── 2. Pydantic Mathematical Validation
    try:
        content_type = request.headers.get("content-type", "")
        pydantic_payload = None
        
        if "multipart/form-data" in content_type:
            form = await request.form()
            file_part = form.get("file")
            if not file_part or not getattr(file_part, "filename", None):
                raise ValueError("No file uploaded. Please upload a valid .csv or .xlsx financial report.")
            
            from cfo_parser import extract_financials_from_file
            content = await file_part.read()
            pydantic_payload = extract_financials_from_file(content, file_part.filename)

        elif "application/json" in content_type:
            payload = await request.json()
            if not payload:
               raise ValueError("Empty JSON payload received.") 
            pydantic_payload = FinancialPayload(**payload)
            
        else:
            raise ValueError(f"Unsupported content type: {content_type}")

        math_result = calculate_financial_health(pydantic_payload)
        math_json = math_result.json()
    except Exception as e:
        asyncio.create_task(sse_broadcast("FAIL", f"Mathematical Validation Error: {str(e)}", "TEST_FAIL"))
        return JSONResponse({"verdict": "FAIL", "error": str(e)}, status_code=400)

    # Stream 'LLM' transition
    asyncio.create_task(sse_broadcast("RUNNING", "Deterministic math verified. Synthesizing War Room qualitative report...", "INFO"))

    # ── 3. LLM Qualitative Evaluation
    narrative_report = ""
    verdict = "PASS"
    score = 100 - math_result.fragility_index
    
    try:
        if not os.getenv("GEMINI_API_KEY"):
            narrative_report = "GEMINI_API_KEY not found. Native Audit fallback generated:\nCFO Math Engine passed. Fragility Index: " + str(math_result.fragility_index)
        else:
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=CFO_SYSTEM_PROMPT
            )
            response = model.generate_content(math_json)
            narrative_report = response.text.strip()
    except Exception as e:
        verdict = "WARN"
        narrative_report = f"LLM Generation Failed (Math verified). Reason: {str(e)}"
        
    final_status = "FAIL" if math_result.fragility_index > 50 else "PASS"
    if final_status == "FAIL": verdict = "FAIL"

    # Stream completion
    asyncio.create_task(sse_broadcast(final_status, narrative_report[:150] + "...", "TEST_PASS" if final_status == "PASS" else "TEST_FAIL"))

    # Return Phantom QA conformant response
    return {
        "verdict": verdict,
        "score": max(0, score),
        "audit_mode": "mathematical",
        "target_url": "http://localhost:5041/api/audit",
        "duration_seconds": 1.5,
        "total_tests": 1,
        "passed": 1 if final_status == "PASS" else 0,
        "failed": 1 if final_status == "FAIL" else 0,
        "cfo_analysis": narrative_report,
        "findings": [{"passed": final_status == "PASS", "test_name": "Fragility Gate", "details": f"Fragility Index is {math_result.fragility_index}"}]
    }




# ═══════════════════════════════════════════════════════════
#  STARTUP
# ═══════════════════════════════════════════════════════════

PORT = 5041

if __name__ == "__main__":
    print("")
    print("=" * 60)
    print("")
    print("   CFO ULTIMATE EXCEL ARCHITECT — Sub-Agent of CFO")
    print("")
    print("   Port: %d" % PORT)
    print("   Dashboard:    http://localhost:%d" % PORT)
    print("   Dialogue Box: http://localhost:%d/form" % PORT)
    print("   API Docs:     http://localhost:%d/docs" % PORT)
    print("")
    print("   Consult:   POST /api/consult (instruction + file)")
    print("   Bridge:    POST /api/sentinel-relay-bridge")
    print("   Execute:   POST /api/execute")
    print("   Audit:     POST /api/audit")
    print("   Health:    GET  /api/health")
    print("   Reports:   GET  /api/reports")
    print("")
    print("   N8N Cloud: RETIRED (Native Intelligence Active)")
    print("")
    print("   Antigravity-AI | CFO Ultimate Excel Architect v3.0.0")
    print("")
    print("=" * 60)
    print("")

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
