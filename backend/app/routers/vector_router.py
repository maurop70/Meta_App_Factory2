import logging
from fastapi import APIRouter, BackgroundTasks, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

try:
    from backend.core.vector_store import VectorStore
    from backend.services.embedding_service import GoogleEmbeddingService
except ImportError:
    from core.vector_store import VectorStore
    from services.embedding_service import GoogleEmbeddingService

logger = logging.getLogger("VectorRouter")

router = APIRouter(prefix="/api/vector", tags=["Vector Store Engine"])

# Instantiations
vector_store = VectorStore(persist_directory="./chroma_data")
embedding_service = GoogleEmbeddingService()

class IngestPayload(BaseModel):
    id: str
    text: str
    metadata: Optional[Dict[str, Any]] = None

class QueryPayload(BaseModel):
    query: str
    n_results: int = 5

async def background_vector_ingestion(payload_id: str, text: str, metadata: Optional[Dict[str, Any]]):
    """
    Background worker task to fetch embedding and write to vector store.
    STRICT GUARDRAIL: chroma client disk writes run in thread pool via vector_store.add_async.
    """
    logger.info(f"Asynchronous worker started for payload: {payload_id}")
    
    # 1. Contact Google Embedding Service
    embedding_res = await embedding_service.get_embedding_async(text)
    if isinstance(embedding_res, JSONResponse):
        logger.error(f"Background worker embedding failure: {embedding_res.body.decode()}")
        return
        
    # 2. Write to ChromaDB in thread pool
    try:
        await vector_store.add_async(
            collection_name="maf_knowledge",
            ids=[payload_id],
            embeddings=[embedding_res],
            metadatas=[metadata or {}],
            documents=[text]
        )
        logger.info(f"Asynchronous vector write complete for payload: {payload_id}")
    except Exception as e:
        logger.error(f"Background vector database write failure: {e}")

@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_payload(payload: IngestPayload, background_tasks: BackgroundTasks):
    """
    Primary ingestion endpoint. Immediately returns a 202 Accepted status
    while routing the actual work to an asynchronous background worker.
    """
    background_tasks.add_task(
        background_vector_ingestion,
        payload_id=payload.id,
        text=payload.text,
        metadata=payload.metadata
    )
    return {
        "status": "ACCEPTED",
        "detail": "Ingestion payload spooled to background worker.",
        "payload_id": payload.id
    }

@router.post("/query")
async def query_payload(payload: QueryPayload):
    """
    Query endpoint. Dynamically embeds the query text and retrieves
    semantically similar documents from the isolated ChromaDB vector store.
    """
    # 1. Contact Google Embedding Service
    embedding_res = await embedding_service.get_embedding_async(payload.query)
    if isinstance(embedding_res, JSONResponse):
        return embedding_res  # Bubble up the uniform 502 fallback directly!
        
    # 2. Query ChromaDB
    try:
        results = await vector_store.query_async(
            collection_name="maf_knowledge",
            query_embeddings=[embedding_res],
            n_results=payload.n_results
        )
        return {
            "status": "SUCCESS",
            "query": payload.query,
            "results": results
        }
    except Exception as e:
        logger.error(f"Semantic query execution failure: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Database Query Error", "detail": str(e)}
        )
