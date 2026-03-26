"""
server.py — Phantom QA Elite Backend Server
=============================================
Autonomous Quality Assurance Command Center
Port: 5030 | Antigravity-AI

Multi-agent test bench: Architect + Ghost User + Skeptic
"""

import os
import sys
import json
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv

# ═══════════════════════════════════════════════════════════
#  ENVIRONMENT
# ═══════════════════════════════════════════════════════════

ROOT = Path(__file__).parent.parent
BACKEND_DIR = Path(__file__).parent

# Load .env from multiple possible locations
for env_path in [
    ROOT / ".env",
    ROOT.parent / ".env",
    ROOT.parent.parent / ".env",
]:
    if env_path.exists():
        load_dotenv(env_path)
        break

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("PhantomQA")

# Add backend to path for imports
sys.path.insert(0, str(BACKEND_DIR))

from memory_store import init_db, save_test_run, save_test_result, \
    get_test_runs, get_test_run, get_dashboard_stats, \
    save_repair_dispatch, mark_repair_complete, get_pending_repairs, get_repair_dispatches
from agents.architect import run_architect
from agents.ghost_user import run_ghost_user
from agents.skeptic import run_skeptic
from warroom_interface import warroom_respond

# ── Ghost Stream Event Queue ─────────────────────────────
_ghost_stream_clients: list[asyncio.Queue] = []

def ghost_event_callback(event: dict):
    """Push event to all connected Ghost Stream SSE clients."""
    for q in _ghost_stream_clients[:]:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass

# ═══════════════════════════════════════════════════════════
#  APP INITIALIZATION
# ═══════════════════════════════════════════════════════════

app = FastAPI(
    title="Phantom QA Elite — Autonomous Quality Assurance",
    version="1.0.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Serve Frontend ────────────────────────────────────────
FRONTEND_DIR = ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Global Exception Handler ─────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg = str(exc)[:300]
    logger.error(f"[ERROR] {request.method} {request.url.path}: {error_msg}")
    return JSONResponse(
        {"error": f"Engine error: {error_msg}", "agent": "Phantom_QA_Elite"},
        status_code=500
    )


# ── Safe Body Parser ─────────────────────────────────────
async def safe_parse_body(request: Request) -> dict:
    """Parse JSON body safely — returns {} on failure."""
    try:
        body = await request.body()
        if not body or body.strip() == b"":
            return {}
        return await request.json()
    except Exception:
        return {}


# ═══════════════════════════════════════════════════════════
#  ROUTES — Frontend
# ═══════════════════════════════════════════════════════════

@app.get("/")
async def serve_frontend():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return JSONResponse({"error": "Frontend not found"})


# ═══════════════════════════════════════════════════════════
#  ROUTES — Health & Dashboard
# ═══════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    # Check Playwright availability
    pw_status = "unknown"
    try:
        import playwright
        pw_status = "installed"
    except ImportError:
        pw_status = "not_installed"

    return {
        "status": "online",
        "agent": "Phantom_QA_Elite",
        "version": "1.0.0",
        "port": 5030,
        "gemini": "configured" if os.environ.get("GEMINI_API_KEY") else "missing",
        "playwright": pw_status,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/dashboard")
async def dashboard():
    stats = get_dashboard_stats()
    return {
        "agent": "Phantom_QA_Elite",
        "stats": stats,
        "timestamp": datetime.now().isoformat(),
    }


# ═══════════════════════════════════════════════════════════
#  ROUTES — Pulse (System Health Scan)
# ═══════════════════════════════════════════════════════════

KNOWN_PORTS = {
    "Meta_App_Factory": {"url": "http://localhost:8000", "health": "/api/health"},
    "Alpha_Architect": {"url": "http://localhost:5008", "health": "/api/health"},
    "CMO_Elite": {"url": "http://localhost:5020", "health": "/api/health"},
    "Phantom_QA_Elite": {"url": "http://localhost:5030", "health": "/api/health"},
}


@app.get("/api/pulse")
async def pulse_scan():
    """Scan all known C-Suite ports and report health."""
    import aiohttp
    results = {}

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
        for name, info in KNOWN_PORTS.items():
            try:
                async with session.get(f"{info['url']}{info['health']}") as r:
                    if r.status == 200:
                        data = await r.json()
                        results[name] = {
                            "status": "online",
                            "url": info["url"],
                            "details": data,
                        }
                    else:
                        results[name] = {"status": "degraded", "url": info["url"],
                                          "http_status": r.status}
            except Exception:
                results[name] = {"status": "offline", "url": info["url"]}

    online = sum(1 for r in results.values() if r["status"] == "online")
    return {
        "timestamp": datetime.now().isoformat(),
        "total_apps": len(KNOWN_PORTS),
        "online": online,
        "offline": len(KNOWN_PORTS) - online,
        "apps": results,
    }


# ═══════════════════════════════════════════════════════════
#  ROUTES — Discovery
# ═══════════════════════════════════════════════════════════

@app.post("/api/discover")
async def discover_app(request: Request):
    data = await safe_parse_body(request)
    target_url = data.get("target_url", "").strip()
    if not target_url:
        return JSONResponse({"error": "target_url is required"}, status_code=400)

    from agents.architect import discover_endpoints
    discovery = await discover_endpoints(target_url)
    return {"discovery": discovery}


# ═══════════════════════════════════════════════════════════
#  ROUTES — Individual Agents
# ═══════════════════════════════════════════════════════════

@app.post("/api/test/architect")
async def test_architect(request: Request):
    data = await safe_parse_body(request)
    target_url = data.get("target_url", "").strip()
    if not target_url:
        return JSONResponse({"error": "target_url is required"}, status_code=400)

    description = data.get("description", "")
    plan = await run_architect(target_url, description)
    return {"agent": "architect", "test_plan": plan}


@app.post("/api/test/ghost")
async def test_ghost(request: Request):
    data = await safe_parse_body(request)
    target_url = data.get("target_url", "").strip()
    if not target_url:
        return JSONResponse({"error": "target_url is required"}, status_code=400)

    headed = data.get("headed", False)
    result = await run_ghost_user(target_url, test_plan=None, headed=headed,
                                   event_callback=ghost_event_callback)
    return {"agent": "ghost_user", "result": result}


@app.post("/api/test/skeptic")
async def test_skeptic(request: Request):
    data = await safe_parse_body(request)
    target_url = data.get("target_url", "").strip()
    if not target_url:
        return JSONResponse({"error": "target_url is required"}, status_code=400)

    result = await run_skeptic(target_url)
    return {"agent": "skeptic", "result": result}


# ═══════════════════════════════════════════════════════════
#  ROUTES — Full Test Bench
# ═══════════════════════════════════════════════════════════

@app.post("/api/test/full")
async def test_full(request: Request):
    """
    Run the complete 3-agent test bench:
    1. Architect → generates test plan
    2. Ghost User → Playwright UI tests
    3. Skeptic → API stress/break tests

    Returns composite verdict with Repair Payloads.
    """
    data = await safe_parse_body(request)
    target_url = data.get("target_url", "").strip()
    if not target_url:
        return JSONResponse({"error": "target_url is required"}, status_code=400)

    app_name = data.get("app_name", target_url.split("://")[-1].split("/")[0])
    description = data.get("description", "")
    skip_ghost = data.get("skip_ghost", False)
    start = time.time()

    logger.info(f"{'='*60}")
    logger.info(f"  PHANTOM QA ELITE — Full Test Bench")
    logger.info(f"  Target: {target_url}")
    logger.info(f"  App: {app_name}")
    logger.info(f"{'='*60}")

    # ── Phase 1: Architect ────────────────────────────────
    logger.info("▶ Phase 1/3: The Architect — Planning test strategy...")
    architect_result = await run_architect(target_url, description)

    # ── Phase 2: Ghost User ───────────────────────────────
    ghost_result = None
    if not skip_ghost and architect_result.get("_discovery", {}).get("has_frontend"):
        logger.info("▶ Phase 2/3: The Ghost User — Playwright UI testing...")
        try:
            ghost_result = await run_ghost_user(target_url, test_plan=architect_result,
                                                event_callback=ghost_event_callback)
        except Exception as e:
            logger.error(f"Ghost User failed: {e}")
            ghost_result = {
                "agent": "ghost_user", "score": 0, "total_tests": 0,
                "passed": 0, "failed": 0, "results": [],
                "error": str(e)[:200],
            }
    else:
        reason = "skipped by user" if skip_ghost else "no frontend detected"
        logger.info(f"▶ Phase 2/3: Ghost User — SKIPPED ({reason})")
        ghost_result = {
            "agent": "ghost_user", "score": 0, "skipped": True,
            "reason": reason, "results": [],
        }

    # ── Phase 3: Skeptic ──────────────────────────────────
    logger.info("▶ Phase 3/3: The Skeptic — API stress testing...")
    skeptic_result = await run_skeptic(target_url, test_plan=architect_result)

    # ── Composite Verdict ─────────────────────────────────
    scores = []
    weights = []

    if not ghost_result.get("skipped"):
        scores.append(ghost_result.get("score", 0))
        weights.append(0.5)  # UI weight

    scores.append(skeptic_result.get("score", 0))
    weights.append(0.5 if ghost_result.get("skipped") else 0.5)

    total_weight = sum(weights)
    composite = sum(s * w for s, w in zip(scores, weights)) / total_weight if total_weight > 0 else 0
    composite = round(composite)

    if composite >= 80:
        verdict = "PASS"
    elif composite >= 50:
        verdict = "WARN"
    else:
        verdict = "FAIL"

    elapsed = time.time() - start

    # ── Collect Repair Payloads ───────────────────────────
    repairs = skeptic_result.get("repair_payloads", [])

    # ── Save to Memory ────────────────────────────────────
    run_id = save_test_run(
        app_name=app_name,
        app_url=target_url,
        verdict=verdict,
        score=composite,
        duration=round(elapsed, 1),
        report_data={
            "verdict": verdict, "score": composite,
            "ghost_score": ghost_result.get("score"),
            "skeptic_score": skeptic_result.get("score"),
        },
        architect_plan=architect_result,
        ghost_summary=ghost_result,
        skeptic_summary=skeptic_result,
        fix_required=repairs if repairs else None,
    )

    # Save individual results
    for r in ghost_result.get("results", []):
        save_test_result(run_id, "ghost_user", r["test_name"], r["passed"],
                          r.get("details", ""), r.get("duration_ms", 0),
                          r.get("screenshot"))

    for r in skeptic_result.get("results", []):
        save_test_result(run_id, "skeptic", r["test_name"], r["passed"],
                          r.get("details", ""), r.get("duration_ms", 0))

    logger.info(f"{'='*60}")
    logger.info(f"  VERDICT: {verdict} (Score: {composite}/100)")
    logger.info(f"  Duration: {elapsed:.1f}s | Repairs: {len(repairs)}")
    logger.info(f"  Run saved: #{run_id}")
    logger.info(f"{'='*60}")

    return {
        "run_id": run_id,
        "verdict": verdict,
        "score": composite,
        "duration_seconds": round(elapsed, 1),
        "app_name": app_name,
        "target_url": target_url,
        "phases": {
            "architect": {
                "status": "complete",
                "endpoints_found": len(architect_result.get("_discovery", {}).get("endpoints", [])),
                "ui_tests_planned": len(architect_result.get("ui_tests", [])),
                "api_tests_planned": len(architect_result.get("api_tests", [])),
                "edge_cases_planned": len(architect_result.get("edge_cases", [])),
                "app_profile": architect_result.get("app_profile", {}),
                "persona": architect_result.get("persona_recommendation", {}),
            },
            "ghost_user": {
                "status": "skipped" if ghost_result.get("skipped") else "complete",
                "score": ghost_result.get("score", 0),
                "total": ghost_result.get("total_tests", 0),
                "passed": ghost_result.get("passed", 0),
                "failed": ghost_result.get("failed", 0),
                "results": ghost_result.get("results", []),
                "console_errors": ghost_result.get("console_errors", []),
            },
            "skeptic": {
                "status": "complete",
                "score": skeptic_result.get("score", 0),
                "total": skeptic_result.get("total_tests", 0),
                "passed": skeptic_result.get("passed", 0),
                "failed": skeptic_result.get("failed", 0),
                "results": skeptic_result.get("results", []),
                "vulnerabilities": skeptic_result.get("vulnerabilities_found", 0),
            },
        },
        "fix_required": repairs,
        "timestamp": datetime.now().isoformat(),
    }


# ═══════════════════════════════════════════════════════════
#  ROUTES — Reports & History
# ═══════════════════════════════════════════════════════════

@app.get("/api/reports")
async def list_reports():
    runs = get_test_runs(limit=20)
    return {"reports": runs, "total": len(runs)}


@app.get("/api/reports/{run_id}")
async def get_report(run_id: int):
    report = get_test_run(run_id)
    if not report:
        return JSONResponse({"error": "Report not found"}, status_code=404)
    return {"report": report}


# ═══════════════════════════════════════════════════════════
#  ROUTES — War Room
# ═══════════════════════════════════════════════════════════

@app.post("/api/warroom/respond")
async def warroom_handler(request: Request):
    data = await safe_parse_body(request)
    question = data.get("question", data.get("input", "")).strip()
    if not question:
        return JSONResponse({"error": "question is required"}, status_code=400)

    context = data.get("context", {})
    response = await warroom_respond(question, context)
    return response


# ═══════════════════════════════════════════════════════════
#  ROUTES — Ghost Stream (SSE)
# ═══════════════════════════════════════════════════════════

@app.get("/api/ghost-stream")
async def ghost_stream():
    """Server-Sent Events stream for real-time Ghost User activity."""

    async def event_generator() -> AsyncGenerator[str, None]:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        _ghost_stream_clients.append(q)
        try:
            # Send initial connected event
            yield f"data: {json.dumps({'type': 'CONNECTED', 'timestamp': datetime.now().isoformat()})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat
                    yield f"data: {json.dumps({'type': 'HEARTBEAT', 'timestamp': datetime.now().isoformat()})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if q in _ghost_stream_clients:
                _ghost_stream_clients.remove(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ═══════════════════════════════════════════════════════════
#  ROUTES — Repair Loop (Loop of Perfection)
# ═══════════════════════════════════════════════════════════

ATOMIZER_WEBHOOK = os.environ.get("ATOMIZER_WEBHOOK_URL", "http://localhost:8000/api/atomizer/repair")


@app.post("/api/repair/dispatch")
async def dispatch_repairs(request: Request):
    """Dispatch repair payloads from a failed test run to Atomizer V2."""
    data = await safe_parse_body(request)
    run_id = data.get("run_id")
    if not run_id:
        return JSONResponse({"error": "run_id is required"}, status_code=400)

    # Get the test run
    run = get_test_run(run_id)
    if not run:
        return JSONResponse({"error": "Test run not found"}, status_code=404)

    repairs = run.get("fix_required") or []
    if not repairs:
        return {"status": "no_repairs_needed", "run_id": run_id}

    # Save dispatch record
    dispatch_id = save_repair_dispatch(run_id, repairs, ATOMIZER_WEBHOOK)

    # Attempt to send to Atomizer
    import aiohttp
    dispatch_status = "dispatched"
    atomizer_response = None
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            payload = {
                "source": "Phantom_QA_Elite",
                "run_id": run_id,
                "dispatch_id": dispatch_id,
                "repairs": repairs,
                "callback_url": f"http://localhost:5030/api/repair/complete",
            }
            async with session.post(ATOMIZER_WEBHOOK, json=payload) as r:
                atomizer_response = await r.text()
                if r.status != 200:
                    dispatch_status = "atomizer_error"
    except Exception as e:
        dispatch_status = "atomizer_unreachable"
        atomizer_response = str(e)[:200]
        logger.warning(f"Atomizer unreachable: {e}")

    logger.info(f"🔧 Repair dispatch #{dispatch_id} for run #{run_id}: {dispatch_status} ({len(repairs)} payloads)")

    return {
        "dispatch_id": dispatch_id,
        "run_id": run_id,
        "status": dispatch_status,
        "repair_count": len(repairs),
        "atomizer_response": atomizer_response,
    }


@app.post("/api/repair/complete")
async def repair_complete(request: Request):
    """Webhook: called by Atomizer V2 when repair is complete."""
    data = await safe_parse_body(request)
    dispatch_id = data.get("dispatch_id")
    if not dispatch_id:
        return JSONResponse({"error": "dispatch_id is required"}, status_code=400)

    success = data.get("success", True)

    if dispatch_id:
        mark_repair_complete(dispatch_id, success)
        logger.info(f"🔧 Repair #{dispatch_id} marked {'complete' if success else 'failed'}")

        # Auto-retest if requested
        if data.get("auto_retest") and success:
            logger.info(f"🔧 Auto-retesting after repair #{dispatch_id}...")
            # This would trigger a re-test of the original run's target

    return {"status": "acknowledged", "dispatch_id": dispatch_id}


@app.post("/api/repair/retest/{run_id}")
async def retest_run(run_id: int):
    """Re-run a previous test configuration (e.g., after a repair)."""
    original = get_test_run(run_id)
    if not original:
        return JSONResponse({"error": "Original run not found"}, status_code=404)

    target_url = original.get("app_url", "")
    app_name = original.get("app_name", "")
    if not target_url:
        return JSONResponse({"error": "No target URL in original run"}, status_code=400)

    logger.info(f"🔁 Re-testing run #{run_id}: {app_name} @ {target_url}")

    # Re-run the full test bench
    architect_result = await run_architect(target_url)

    ghost_result = None
    if architect_result.get("_discovery", {}).get("has_frontend"):
        try:
            ghost_result = await run_ghost_user(target_url, test_plan=architect_result,
                                                 event_callback=ghost_event_callback)
        except Exception as e:
            ghost_result = {"agent": "ghost_user", "score": 0, "results": [], "error": str(e)[:200]}
    else:
        ghost_result = {"agent": "ghost_user", "score": 0, "skipped": True, "results": []}

    skeptic_result = await run_skeptic(target_url, test_plan=architect_result)

    # Score
    scores = []
    if not ghost_result.get("skipped"):
        scores.append(ghost_result.get("score", 0))
    scores.append(skeptic_result.get("score", 0))
    composite = round(sum(scores) / len(scores)) if scores else 0
    verdict = "PASS" if composite >= 80 else ("WARN" if composite >= 50 else "FAIL")

    new_run_id = save_test_run(
        app_name=app_name, app_url=target_url, verdict=verdict,
        score=composite, duration=0,
        report_data={"verdict": verdict, "score": composite, "retest_of": run_id},
        architect_plan=architect_result, ghost_summary=ghost_result,
        skeptic_summary=skeptic_result,
    )

    return {
        "retest_of": run_id,
        "new_run_id": new_run_id,
        "verdict": verdict,
        "score": composite,
    }


@app.get("/api/repairs")
async def list_repairs():
    """List all repair dispatches."""
    repairs = get_repair_dispatches()
    pending = get_pending_repairs()
    return {"repairs": repairs, "pending_count": len(pending)}


# ═══════════════════════════════════════════════════════════
#  STARTUP
# ═══════════════════════════════════════════════════════════

PORT = 5030

if __name__ == "__main__":
    init_db()

    print("")
    print("=" * 60)
    print("")
    print("   PHANTOM QA ELITE -- Autonomous Quality Assurance")
    print("")
    print("   Port: %d" % PORT)
    print("   Dashboard: http://localhost:%d" % PORT)
    print("   API Docs:  http://localhost:%d/docs" % PORT)
    print("")
    print("   War Room:  /api/warroom/respond")
    print("   Health:    /api/health")
    print("   Pulse:     /api/pulse")
    print("")
    print("   Agents:")
    print("     [A]  The Architect (Test Planner)")
    print("     [G]  The Ghost User (Playwright UI)")
    print("     [S]  The Skeptic (API Bug Hunter)")
    print("")
    print("   Antigravity-AI | Phantom QA Elite v1.0.0")
    print("")
    print("=" * 60)
    print("")

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
