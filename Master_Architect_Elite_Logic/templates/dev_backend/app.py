# Base FastAPI backend — MAF Builder Chat overlays this with the real app.
# Routes live under /api (the Vite dev server proxies /api -> this backend).
# Persist data with the stdlib `sqlite3` module (DB file next to this file).
from fastapi import FastAPI

app = FastAPI()


@app.get("/api/health")
def health():
    return {"status": "ok"}
