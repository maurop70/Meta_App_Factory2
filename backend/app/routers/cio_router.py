import os
import uuid
import json
import logging
import asyncio
import httpx
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, status, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

try:
    from backend.schemas.intelligence import CIOIntelligenceSchema
    from backend.services.cio_crawler import CIOCrawlerService
    from backend.core.vector_store import VectorStore
    from backend.services.embedding_service import GoogleEmbeddingService
except ImportError:
    from schemas.intelligence import CIOIntelligenceSchema
    from services.cio_crawler import CIOCrawlerService
    from core.vector_store import VectorStore
    from services.embedding_service import GoogleEmbeddingService

logger = logging.getLogger("CioRouter")

router = APIRouter(prefix="/api/cio", tags=["CIO Extraction Pipeline"])

vector_store = VectorStore(persist_directory="./chroma_data")
embedding_service = GoogleEmbeddingService()
crawler_service = CIOCrawlerService()

# Global in-memory dictionary to track task statuses
extraction_status = {}

class ExtractRequest(BaseModel):
    url: str

ROUTER_DIR = os.path.dirname(os.path.abspath(__file__))

def find_registry_path():
    curr = ROUTER_DIR
    while True:
        candidate = os.path.join(curr, "registry.json")
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    return None

async def post_sre_alert(payload_id: str, target_url: str, exception_name: str, exception_msg: str):
    """
    Asynchronously dispatch SRE alert payload to the SRE node /api/qa/alerts.
    """
    alert_payload = {
        "alert_id": f"cio_alert_{payload_id}",
        "source": "CIO Ingestion Pipeline",
        "agent": "CIO_Agent",
        "severity": "CRITICAL",
        "exception": exception_name,
        "message": exception_msg,
        "staged_blueprint_path": "backend/app/routers/cio_router.py",
        "ast_payload_preview": f"Target URL: {target_url}"
    }
    logger.info(f"Dispatching SRE Alert: {alert_payload}")
    
    # Try different potential ports to be absolutely safe
    ports = [8000, 5000, 5009, 5070]
    for port in ports:
        url = f"http://127.0.0.1:{port}/api/qa/alerts"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.post(url, json=alert_payload)
                if res.status_code == 200:
                    logger.info(f"SRE Alert successfully logged on port {port}.")
                    return
        except Exception as e:
            logger.warning(f"Failed to post SRE alert to port {port}: {e}")

    # Fallback to local import integration if HTTP routing is completely offline
    try:
        from api_qa_telemetry import push_qa_event
        push_qa_event(
            agent="CIO_Agent",
            message=f"[SRE ALERT] {exception_name}: {exception_msg}",
            status="CRITICAL",
            filename="backend/app/routers/cio_router.py"
        )
        logger.info("Directly pushed SRE event to api_qa_telemetry.")
    except Exception as local_err:
        logger.error(f"SRE telemetry fallback failed: {local_err}")

async def background_cio_extraction(payload_id: str, target_url: str):
    """
    Asynchronous background extraction pipeline.
    1. Scrapes URL using CIOCrawlerService (handles 502).
    2. Runs Gemini 2.5 Pro with response_schema=CIOIntelligenceSchema.
    3. Safe vector writes using asyncio.to_thread.
    4. SRE telemetry alerts dispatch on exception.
    """
    logger.info(f"Starting background CIO extraction for payload {payload_id} / URL: {target_url}")
    extraction_status[payload_id] = {"status": "PENDING", "url": target_url}
    
    try:
        # 1. Scraping using CIOCrawlerService
        scrape_res = await crawler_service.scrape(target_url)
        if isinstance(scrape_res, dict) and scrape_res.get("error") == "Gateway Unreachable":
            raise RuntimeError(f"Scraper error: {scrape_res.get('detail')}")
            
        raw_markdown = scrape_res
        
        # 2. Gemini 2.5 Pro analysis strictly schema-sanitized
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not defined in the environment.")
            
        import google.generativeai as genai
        genai.configure(api_key=api_key.strip("'\""))
        
        # Configure Gemini 2.5 Pro with strict response schema
        model_name = "gemini-2.5-pro"
        generation_config = {
            "response_mime_type": "application/json",
            "response_schema": CIOIntelligenceSchema
        }
        
        try:
            model = genai.GenerativeModel(model_name=model_name, generation_config=generation_config)
            prompt = f"""
            Analyze the raw markdown intelligence and extract structured insights.
            You MUST provide the final response strictly adhering to the JSON schema.
            Ensure that ALL three fields (core_concepts, market_signals, and threat_vectors) are populated in the JSON output as lists of strings.
            Even if no explicit signals or threats are found in the content, generate relevant high-level analytical points based on the technical stack details (e.g., security risks of exposed uvicorn servers, or market opportunities for automated API factories).

            RAW MARKDOWN INTELLIGENCE:
            {raw_markdown}
            """
            response = await asyncio.to_thread(model.generate_content, prompt)
            intel_json = response.text
        except Exception as gemini_err:
            logger.warning(f"gemini-2.5-pro generation failed: {gemini_err}. Trying gemini-2.5-flash fallback.")
            model = genai.GenerativeModel(model_name="gemini-2.5-flash", generation_config=generation_config)
            prompt = f"""
            Analyze the raw markdown intelligence and extract structured insights.
            You MUST provide the final response strictly adhering to the JSON schema.
            Ensure that ALL three fields (core_concepts, market_signals, and threat_vectors) are populated in the JSON output as lists of strings.
            Even if no explicit signals or threats are found in the content, generate relevant high-level analytical points based on the technical stack details (e.g., security risks of exposed uvicorn servers, or market opportunities for automated API factories).

            RAW MARKDOWN INTELLIGENCE:
            {raw_markdown}
            """
            response = await asyncio.to_thread(model.generate_content, prompt)
            intel_json = response.text
            
        # Parse and strictly validate with Pydantic
        intel_dict = json.loads(intel_json)
        validated_data = CIOIntelligenceSchema(**intel_dict)
        validated_json_str = validated_data.model_dump_json()
        
        # 3. Vectorization and safe ChromaDB write via asyncio.to_thread
        embedding_res = await embedding_service.get_embedding_async(validated_json_str)
        if isinstance(embedding_res, JSONResponse):
            raise RuntimeError(f"Embedding service failed: {embedding_res.body.decode()}")
            
        metadata = {
            "source": "cio_extraction",
            "url": target_url,
            "timestamp": datetime.now().isoformat(),
            "payload_id": payload_id
        }
        
        await vector_store.add_async(
            collection_name="maf_knowledge",
            ids=[payload_id],
            embeddings=[embedding_res],
            metadatas=[metadata],
            documents=[validated_json_str]
        )
        
        # Mark as successful
        extraction_status[payload_id] = {
            "status": "SUCCESS",
            "url": target_url,
            "data": intel_dict,
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"Background extraction SUCCESS for payload {payload_id}")
        
    except Exception as e:
        logger.error(f"Background extraction FAILED for payload {payload_id}: {e}")
        extraction_status[payload_id] = {
            "status": "FAILED",
            "url": target_url,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        # Asynchronously dispatch SRE alert payload
        await post_sre_alert(
            payload_id=payload_id,
            target_url=target_url,
            exception_name=type(e).__name__,
            exception_msg=str(e)
        )

@router.post("/extract", status_code=status.HTTP_202_ACCEPTED)
async def extract_cio(payload: ExtractRequest, background_tasks: BackgroundTasks):
    """
    Start CIO headless extraction process.
    Performs dynamic pre-flight validation on CIO_Agent registry status.
    Returns 202 Accepted and spools pipeline to BackgroundTasks.
    """
    # 1. Deterministic Lifecycle Pre-Flight Check
    registry_path = find_registry_path()
    cio_active = False
    
    if registry_path:
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                reg_data = json.load(f)
                status_val = reg_data.get("apps", {}).get("CIO_Agent", {}).get("status", "")
                if status_val in ["active", "running", "online", "ACTIVE"]:
                    cio_active = True
        except Exception as e:
            logger.error(f"Error querying App Registry: {e}")

    if not cio_active:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "Agent Offline",
                "detail": "CIO_Agent must be active in the App Registry before extraction can commence."
            }
        )
        
    # Generate deterministic or unique payload id
    payload_id = str(uuid.uuid4())
    
    # 2. Spool processing to background task
    background_tasks.add_task(
        background_cio_extraction,
        payload_id=payload_id,
        target_url=payload.url
    )
    
    return {
        "status": "ACCEPTED",
        "detail": "CIO extraction spooled to background tasks.",
        "payload_id": payload_id
    }

@router.get("/status/{payload_id}")
async def get_extraction_status(payload_id: str):
    """
    Query extraction status for E2E polling.
    """
    status_info = extraction_status.get(payload_id)
    if not status_info:
        # Check ChromaDB fallback in case of process restarts
        try:
            get_res = await vector_store.get_async(collection_name="maf_knowledge", ids=[payload_id])
            if get_res and get_res.get("ids"):
                return {
                    "status": "SUCCESS",
                    "url": "unknown",
                    "data": json.loads(get_res["documents"][0]),
                    "timestamp": datetime.now().isoformat()
                }
        except Exception:
            pass
            
        raise HTTPException(status_code=404, detail="No extraction task found for this payload ID.")
        
    return status_info
