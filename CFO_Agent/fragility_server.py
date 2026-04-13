"""
fragility_server.py — CFO Fragility Engine (Isolated)
═══════════════════════════════════════════════════════
Port: 5041 | Antigravity-AI

Pure deterministic financial mathematics microservice.
Accepts FinancialPayload, returns CFOAnalysisResult.
Zero LLM dependency — this is the "Mathematical Soul" isolated.

Endpoints:
  POST /api/calculate     — Run financial math, return CFOAnalysisResult
  GET  /api/health        — Health check for Phantom QA Pulse
  GET  /api/schema        — Return Pydantic schema for FinancialPayload
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ═══════════════════════════════════════════════════════════
#  ENVIRONMENT
# ═══════════════════════════════════════════════════════════

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from cfo_logic import FinancialPayload, CFOAnalysisResult, calculate_financial_health

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("FragilityEngine")

# ═══════════════════════════════════════════════════════════
#  APP
# ═══════════════════════════════════════════════════════════

app = FastAPI(
    title="CFO Fragility Engine — Isolated Mathematical Core",
    version="1.0.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

server_start_time = datetime.now()
_request_count = 0
_total_latency_ms = 0.0


# ═══════════════════════════════════════════════════════════
#  ROUTES — Health
# ═══════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    """Health check — consumed by Phantom QA Pulse tab."""
    return {
        "status": "online",
        "agent": "CFO_Fragility_Engine",
        "version": "1.0.0",
        "port": PORT,
        "uptime_seconds": round((datetime.now() - server_start_time).total_seconds()),
        "requests_served": _request_count,
        "avg_latency_ms": round(_total_latency_ms / max(_request_count, 1), 2),
        "timestamp": datetime.now().isoformat(),
    }


# ═══════════════════════════════════════════════════════════
#  ROUTES — Calculate (Core Math)
# ═══════════════════════════════════════════════════════════

@app.post("/api/calculate")
async def calculate(request: Request):
    """
    Core math endpoint. Accepts FinancialPayload JSON, returns
    deterministic CFOAnalysisResult with fragility_index,
    runway_months, volatile_variables, and all campaign analysis.

    This is the single source of truth for all financial mathematics
    in the Antigravity ecosystem. The CFO Agent (port 5070) and
    Phantom QA Elite (port 5030) both consume this endpoint.
    """
    global _request_count, _total_latency_ms
    start = time.time()

    try:
        payload = await request.json()
        if not payload:
            return JSONResponse(
                {"error": "Empty payload. Send a FinancialPayload JSON."},
                status_code=400
            )

        # Validate through Pydantic
        financial_data = FinancialPayload(**payload)

        # Run deterministic math
        result = calculate_financial_health(financial_data)

        elapsed_ms = (time.time() - start) * 1000
        _request_count += 1
        _total_latency_ms += elapsed_ms

        logger.info(
            f"[CALCULATE] Fragility={result.fragility_index:.1f} | "
            f"Runway={result.runway_months:.1f}mo | "
            f"Volatiles={len(result.volatile_variables)} | "
            f"{elapsed_ms:.1f}ms"
        )

        return {
            "status": "ok",
            "result": json.loads(result.json()),
            "meta": {
                "engine": "CFO_Fragility_Engine",
                "version": "1.0.0",
                "latency_ms": round(elapsed_ms, 2),
                "timestamp": datetime.now().isoformat(),
            }
        }

    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000
        logger.error(f"[CALCULATE] Validation error: {e}")
        return JSONResponse(
            {
                "error": f"Financial payload validation failed: {str(e)[:300]}",
                "hint": "Ensure your payload matches the FinancialPayload schema. Use GET /api/schema to inspect.",
            },
            status_code=400
        )


# ═══════════════════════════════════════════════════════════
#  ROUTES — Schema Inspector
# ═══════════════════════════════════════════════════════════

@app.get("/api/schema")
async def schema():
    """Returns the FinancialPayload and CFOAnalysisResult Pydantic schemas."""
    return {
        "input_schema": FinancialPayload.schema(),
        "output_schema": CFOAnalysisResult.schema(),
    }


# ═══════════════════════════════════════════════════════════
#  STARTUP
# ═══════════════════════════════════════════════════════════

PORT = 5041

if __name__ == "__main__":
    print("")
    print("=" * 60)
    print("")
    print("   CFO FRAGILITY ENGINE — Isolated Mathematical Core")
    print("")
    print("   Port: %d" % PORT)
    print("   API Docs:  http://localhost:%d/docs" % PORT)
    print("")
    print("   Calculate: POST /api/calculate")
    print("   Health:    GET  /api/health")
    print("   Schema:    GET  /api/schema")
    print("")
    print("   Dependencies: cfo_logic.py (Pydantic + Pure Math)")
    print("   LLM: NONE (Deterministic Only)")
    print("")
    print("   Antigravity-AI | CFO Fragility Engine v1.0.0")
    print("")
    print("=" * 60)
    print("")

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
