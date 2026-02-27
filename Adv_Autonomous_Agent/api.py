from fastapi import FastAPI
from pydantic import BaseModel
import subprocess
import sys
import os

app = FastAPI(title="Antigravity Meta App Factory API")

class TaskRequest(BaseModel):
    task: str

@app.post("/execute")
def execute_task(request: TaskRequest):
    # This bridge triggers the MetaSupervisor via the CLI
    # We use subprocess to run the supervisor script with the user's prompt
    try:
        # Determine the path to supervisor.py relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        supervisor_path = os.path.join(current_dir, "supervisor.py")
        
        # In a real production scenario, you might want to run this as a background task
        # or use a task queue if the supervisor loop takes a long time.
        # For now, we trigger it and return a confirmation message.
        
        # Note: supervisor.py enters an interactive loop. 
        # For n8n integration, you might later want a non-interactive mode.
        command = [sys.executable, supervisor_path, request.task]
        
        # We start the process in the background to avoid blocking the API response
        subprocess.Popen(command)
        
        return {
            "status": "success", 
            "message": f"Task '{request.task}' sent to Antigravity factory.",
            "details": "Supervisor process started in background."
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
