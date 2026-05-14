import os
import shutil
import uuid
import subprocess
import asyncio

from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse

# Assume 'app' is already initialized in server.py.
# For demonstration purposes, we'll initialize it here if it's a standalone snippet.
# In a real application, 'app' would be the existing FastAPI instance.
app = FastAPI() # Uncomment if this is a new file, otherwise assume 'app' exists.

# --- Configuration for Ledger Ingestion ---
INGEST_DIR = "/tmp/cfo_ingest/"
WORKER_SCRIPT = "worker_ingest.py" # The background worker script (not created here).

# --- Application Startup Event ---
# This ensures the ingestion directory exists when the FastAPI application starts.
@app.on_event("startup")
async def startup_event_cfo_agent():
    """Ensures the necessary directories for CFO Agent operations exist on startup."""
    os.makedirs(INGEST_DIR, exist_ok=True)
    print(f"CFO_Agent: Ensured ingestion directory exists at {INGEST_DIR}")

# --- New Asynchronous FastAPI POST Route ---
@app.post("/api/v1/economics/ingest_ledger", status_code=status.HTTP_202_ACCEPTED)
async def ingest_ledger(
    ledger_file: UploadFile = File(..., description="CSV ledger file to ingest for processing.")
) -> JSONResponse:
    """
    Accepts a CSV ledger file, saves it locally, and spawns a detached background
    worker for asynchronous processing.

    Returns:
        JSONResponse: A status message and a unique job ID.
    """
    job_id = uuid.uuid4()
    
    # Generate a unique filename using the job_id and the original file's extension.
    # This prevents path traversal issues and ensures unique storage.
    original_filename_ext = os.path.splitext(ledger_file.filename)[1]
    unique_filename = f"{job_id}{original_filename_ext}"
    target_filepath = os.path.join(INGEST_DIR, unique_filename)

    try:
        # --- High-Performance I/O Serialization Doctrine Compliance ---
        # Blocking file I/O operations (reading from UploadFile.file and writing
        # to disk) are offloaded to a separate thread using asyncio.to_thread().
        # This prevents the main FastAPI event loop from being blocked, ensuring
        # the server remains responsive to other requests.
        def _sync_write_file_to_disk():
            """Synchronously writes the uploaded file to the target path."""
            # Ensure the file pointer of the source (UploadFile's underlying file)
            # is at the beginning before copying.
            ledger_file.file.seek(0)
            with open(target_filepath, "wb") as buffer:
                # shutil.copyfileobj is an efficient way to copy file-like objects.
                shutil.copyfileobj(ledger_file.file, buffer)
            # Explicitly close the UploadFile's underlying temporary file to release resources.
            ledger_file.file.close()

        await asyncio.to_thread(_sync_write_file_to_disk)

        # --- Spawn Detached Background Worker ---
        # The worker_ingest.py script will be responsible for processing the saved file.
        # This process is completely decoupled from the FastAPI application's execution thread.
        command = ["python", WORKER_SCRIPT, target_filepath]

        # Configure subprocess.Popen for true detachment based on the operating system.
        # stdout and stderr are redirected to DEVNULL to prevent the parent process
        # from waiting for the child's pipes to close, ensuring complete detachment.
        if os.name == 'posix':  # Unix-like systems (Linux, macOS)
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid  # Detaches the child from the controlling terminal
            )
        elif os.name == 'nt':  # Windows systems
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS  # Detaches the child process
            )
        else:
            # Fallback for other operating systems; detachment might not be as robust.
            print(f"Warning: Running on unsupported OS '{os.name}'. Detachment might not be complete.")
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        # --- Immediate Response ---
        # Return a 202 Accepted status code with a job ID, indicating that
        # processing has been initiated but is not yet complete.
        return JSONResponse(
            content={"status": "processing", "job_id": str(job_id)},
            status_code=status.HTTP_202_ACCEPTED
        )

    except Exception as e:
        # Log the error for debugging purposes.
        print(f"CFO_Agent Error: Failed to ingest ledger for job_id {job_id}. Details: {e}")
        
        # Clean up the partially written file if an error occurred during the write process.
        if os.path.exists(target_filepath):
            os.remove(target_filepath)
            print(f"CFO_Agent: Cleaned up partial file {target_filepath}")

        # Raise an HTTPException for client feedback.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest ledger file: {e}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5041)