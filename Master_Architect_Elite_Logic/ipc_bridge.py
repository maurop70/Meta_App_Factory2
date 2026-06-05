import os
import sys
import json
import time
import asyncio
import logging
import aiofiles

# Configure logging to match server style
logger = logging.getLogger("MasterArchitect.IPCBridge")

# Core event stream clients registry
BRIDGE_CLIENTS = []

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

async def register_client():
    """
    Asynchronous generator registered in FastAPI StreamingResponse for /api/bridge/stream.
    Feeds real-time watchdog status, process output, and strategic pauses.
    """
    queue = asyncio.Queue()
    BRIDGE_CLIENTS.append(queue)
    logger.info("New client registered to IPC Bridge event stream.")
    
    try:
        # Emit confirmation connection event
        yield f"data: {json.dumps({'type': 'connection', 'status': 'connected'})}\n\n"
        
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=20.0)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                yield ": ping\n\n"
    except asyncio.CancelledError:
        logger.info("Client disconnected from IPC Bridge event stream.")
    finally:
        if queue in BRIDGE_CLIENTS:
            BRIDGE_CLIENTS.remove(queue)

async def broadcast_event(event: dict):
    """
    Broadcasts structured JSON payload to all connected EventSource clients.
    """
    logger.info(f"Broadcasting event: {event.get('type')} - {event.get('status', '')}")
    for queue in list(BRIDGE_CLIENTS):
        try:
            await queue.put(event)
        except Exception as e:
            logger.error(f"Failed to queue event to SSE client: {e}")

async def start_ipc_bridge():
    """
    Continuous async polling loop targeting ay2_dispatch_queue.
    Coordinates subprocess execution, strategic pauses, and life-cycle archival.
    """
    ay2_queue_dir = os.path.join(_SCRIPT_DIR, "ay2_dispatch_queue")
    os.makedirs(ay2_queue_dir, exist_ok=True)
    
    logger.info(f"Actuating IPC Bridge Watchdog. Spool directory: {ay2_queue_dir}")
    
    while True:
        try:
            # Audit directory for pending files
            if not os.path.exists(ay2_queue_dir):
                await asyncio.sleep(1)
                continue
                
            files = sorted([
                f for f in os.listdir(ay2_queue_dir)
                if f.startswith("pending_blueprint_") and f.endswith(".json")
            ])
            
            if not files:
                await asyncio.sleep(1)
                continue
                
            filename = files[0]
            file_path = os.path.join(ay2_queue_dir, filename)
            logger.info(f"IPC Watchdog discovered blueprint: {filename}")
            
            # Read spooled JSON to evaluate properties
            try:
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                blueprint_data = json.loads(content)
            except Exception as e:
                logger.error(f"Error reading/parsing pending blueprint {filename}: {e}")
                # Rename to broken to avoid infinite loop
                broken_name = filename.replace("pending_blueprint_", "broken_blueprint_")
                os.rename(file_path, os.path.join(ay2_queue_dir, broken_name))
                await broadcast_event({
                    "type": "circuit_breaker",
                    "status": "HALTED",
                    "blueprint_file": filename,
                    "error": f"Failed to parse blueprint JSON: {str(e)}"
                })
                continue
                
            # Rule 1: Evaluate Strategic Pause (Zero-Trust Pause)
            if blueprint_data.get("Strategic_Pause") is True:
                paused_name = filename.replace("pending_blueprint_", "paused_blueprint_")
                paused_path = os.path.join(ay2_queue_dir, paused_name)
                
                os.rename(file_path, paused_path)
                logger.warning(f"Strategic Pause detected. Renamed {filename} to {paused_name}")
                
                await broadcast_event({
                    "type": "strategic_pause",
                    "status": "PAUSED",
                    "blueprint_file": paused_name
                })
                # Yield to the next loop tick without executing, awaiting POST /approve or POST /reject
                await asyncio.sleep(1)
                continue
                
            # Rule 2: Execution via subprocess spawn
            await broadcast_event({
                "type": "execution_start",
                "status": "EXECUTING",
                "blueprint_file": filename
            })
            
            # Formulate subprocess arguments
            cmd = ["antigravity", "--execute-blueprint", file_path, "--headless-diagnostics"]
            process = None
            
            try:
                # Try spawning global antigravity CLI
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            except FileNotFoundError:
                # Fallback to programmatic mock CLI execution
                logger.info("Global antigravity command not found. Falling back to local mock_antigravity.py")
                mock_script = os.path.join(_SCRIPT_DIR, "mock_antigravity.py")
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    mock_script,
                    "--execute-blueprint",
                    file_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
            fatal_exception_detected = False
            exception_trace = []
            
            async def read_stdout(stream):
                while True:
                    line_bytes = await stream.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="ignore")
                    await broadcast_event({
                        "type": "agent_stream",
                        "emitter": "IPC_BRIDGE_STDOUT",
                        "content": line
                    })
                    
            async def read_stderr(stream):
                nonlocal fatal_exception_detected
                while True:
                    line_bytes = await stream.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="ignore")
                    await broadcast_event({
                        "type": "agent_stream",
                        "emitter": "IPC_BRIDGE_STDERR",
                        "content": line
                    })
                    
                    # Capture tracebacks and check for database/playwright exceptions
                    line_lower = line.lower()
                    if any(pat in line_lower for pat in ["fatal", "exception", "integrityerror", "unique constraint failed", "error"]):
                        fatal_exception_detected = True
                        exception_trace.append(line.strip())
                        
            # Execute streams concurrently
            await asyncio.gather(
                read_stdout(process.stdout),
                read_stderr(process.stderr)
            )
            
            return_code = await process.wait()
            logger.info(f"Subprocess terminated with exit code {return_code}")
            
            # Rule 3: Lifecycle Archival (Single-Execution Guarantee)
            archived_name = filename.replace("pending_blueprint_", "archived_blueprint_")
            archived_path = os.path.join(ay2_queue_dir, archived_name)
            os.rename(file_path, archived_path)
            logger.info(f"Spool queue cleaned. Blueprint archived to {archived_name}")
            
            if fatal_exception_detected or return_code != 0:
                logger.error("Fatal exception captured in watchdog process.")
                await broadcast_event({
                    "type": "circuit_breaker",
                    "status": "HALTED",
                    "blueprint_file": archived_name,
                    "error": "\n".join(exception_trace) if exception_trace else f"Subprocess exited with code {return_code}"
                })
            else:
                await broadcast_event({
                    "type": "execution_success",
                    "status": "COMPLETED",
                    "blueprint_file": archived_name
                })
                
        except Exception as e:
            logger.error(f"Global fracture in start_ipc_bridge event loop: {e}")
            
        await asyncio.sleep(1)
