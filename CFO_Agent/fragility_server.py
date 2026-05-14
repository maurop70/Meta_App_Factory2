from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    """
    Root endpoint for the Fragility Server.
    """
    return {"message": "Welcome to the Fragility Server (FastAPI)"}

@app.get("/health")
async def health():
    """
    Health check endpoint for the Fragility Server.
    """
    return {"status": "healthy"}