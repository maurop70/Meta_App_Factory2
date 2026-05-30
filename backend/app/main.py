from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.inventory_router import router as inventory_router
from app.routers.ingest import router as ingest_router
from app.routers.vector_router import router as vector_router
from app.db import init_db

app = FastAPI(title="MAF Enterprise Inventory Tracking Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database schema and seeds
init_db()

# Include the routers
app.include_router(inventory_router)
app.include_router(ingest_router)
app.include_router(vector_router)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "FastAPI SQLite3 Engine"}
