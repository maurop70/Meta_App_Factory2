"""
alpha_orchestrator.py — Phase 12.1 Autonomous API Bridge Daemon & AY2 Actuator
═══════════════════════════════════════════════════════════════════════════════
Meta_App_Factory | Antigravity V3.0 | Venture Studio

Implements the persistent watchdog, Rigid Context Compiler, Gemini API transmission,
and headless detached execution protocols. Integrates the AY2 Auto-Consumption Loop
for headless AST splicing, Playwright E2E verification, and automatic rollback seals.
"""

import os
import sys
import json
import asyncio
import logging
import time
import subprocess
from datetime import datetime
import aiofiles

# Configure unbuffered output for pipeline piping compatibility
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("alpha_orchestrator.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("AlphaOrchestrator")

# Load environment secrets
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'), override=True)
except ImportError:
    pass

import google.generativeai as genai

# Setup directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_DIR = os.path.join(BASE_DIR, "Master_Architect_Elite_Logic", "ay2_dispatch_queue")
LOGS_DIR = os.path.join(BASE_DIR, "Master_Architect_Elite_Logic", "logs")

os.makedirs(QUEUE_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# 1. RIGID CONTEXT COMPILER
# ─────────────────────────────────────────────────────────────────────────────

def rigid_compile_payload(raw_mandate: str, target_file_content: str = "", target_file_path: str = "") -> str:
    """
    Structured Python compiler that injects the three MAF Operational Doctrines
    directly into every Gemini prompt payload.
    """
    sub_atomic_restitching_doctrine = (
        "=== THE SUB-ATOMIC RESTITCHING DOCTRINE (IMMUTABLE) ===\n"
        "1. All proposed edits must be returned as strict SEARCH/REPLACE blocks.\n"
        "2. The target content block to be replaced MUST exist exactly as-is in the source code.\n"
        "3. Any single edit chunk is strictly restricted to a 250-line boundary.\n"
        "4. DO NOT dump or return the entire modified file contents."
    )
    
    verification_matrix = (
        "=== THE E2E PLAYWRIGHT VERIFICATION MATRIX (IMMUTABLE) ===\n"
        "1. All architectural changes, proxy updates, and endpoints must be validated.\n"
        "2. Verification MUST utilize a headless Playwright end-to-end spec file (.spec.ts).\n"
        "3. Asserting success using raw screenshots or DOM/UI presence logs is permanently forbidden.\n"
        "4. The spec must perform strict HTTP status and response schema validations."
    )
    
    io_serialization_envelope = (
        "=== THE I/O SERIALIZATION ENVELOPE MATRIX (IMMUTABLE) ===\n"
        "1. All generated API payloads must enforce a strict pagination boundary.\n"
        "2. Responses returning collections of records must strictly serialize as:\n"
        "   {\"items\": [...], \"total\": int, \"limit\": int, \"offset\": int}\n"
        "3. Payloads must strictly comply with the 'Infrastructure_Blueprint.json' schema."
    )
    
    prompt_payload = f"""ROLE: You are the Antigravity Swarm Architect (AY2). You are tasked with executing a sub-atomic mutation.

{sub_atomic_restitching_doctrine}

{verification_matrix}

{io_serialization_envelope}

---
TARGET FILE: {target_file_path or 'N/A'}
---
SOURCE CODE PREVIEW:
{target_file_content or 'No source file targeted.'}
---
COMMAND MANDATE / FAULT TRACEBACK:
{raw_mandate}

Please compile your response into a valid, strict JSON object conforming to this schema:
{{
    "name": "Self-Healing Patch Blueprint",
    "version": "1.0.0",
    "nodes": [
        {{
            "action": "AST_SPLICE",
            "target_file": "{target_file_path or 'api.py'}",
            "search_content": "exact code block to match",
            "replace_content": "repaired code block to swap in"
        }}
    ]
}}
"""
    return prompt_payload

# ─────────────────────────────────────────────────────────────────────────────
# 2. GEMINI API TRANSMISSION TIER
# ─────────────────────────────────────────────────────────────────────────────

async def transmit_mandate_to_gemini(compiled_prompt: str, payload_type: str = "CONVERSATIONAL") -> Optional[dict]:
    """
    Transmits the compiled prompt to the Gemini API, routing structural work
    to gemini-2.5-pro and reserving gemini-2.5-flash for conversational bypasses.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable is missing. Transmission blocked.")
        return None

    # ── PHASE 12.1 INFERENCE MODEL ROUTING SPLICE ──
    # If the payload is classified as a structural mandate or self-healing patch, route to the high-reasoning engine
    if payload_type in ("STRUCTURAL_MANDATE", "SELF_HEALING_PATCH") or any(x in compiled_prompt for x in ["Traceback", "ZeroDivisionError", "splice", "error"]):
        model_name = "gemini-2.5-pro"
        logger.info(f"Targeting high-reasoning model '{model_name}' for {payload_type} task complexity.")
    else:
        model_name = "gemini-2.5-flash"
        logger.info(f"Targeting conversational bypass model '{model_name}' for standard task complexity.")

    try:
        # Run synchronous SDK call in an executor thread to prevent event loop blocking
        loop = asyncio.get_running_loop()
        
        def _call_api():
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            
            # Request JSON output structure
            response = model.generate_content(
                compiled_prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return response.text

        response_text = await loop.run_in_executor(None, _call_api)
        logger.info("Received raw response from Gemini API.")
        
        # Parse and return structured JSON
        return json.loads(response_text)
    except Exception as e:
        logger.error(f"Gemini API transmission failed: {e}")
        return None

# ─────────────────────────────────────────────────────────────────────────────
# 3. WATCHDOG EVENT LOOP & AY2 AUTO-CONSUMER
# ─────────────────────────────────────────────────────────────────────────────

class AlphaOrchestratorWatchdog:
    def __init__(self, queue_dir: str, logs_dir: str, poll_interval: float = 1.5):
        self.queue_dir = queue_dir
        self.logs_dir = logs_dir
        self.poll_interval = poll_interval
        self.is_running = False
        self._processed_logs = {}  # Tracks log file sizes to only read new appends

    async def start(self):
        """Starts the persistent non-blocking watchdog loop."""
        self.is_running = True
        logger.info(f"AlphaOrchestrator Watchdog starting. Queue: {self.queue_dir} | Logs: {self.logs_dir}")
        asyncio.create_task(self._queue_watcher_loop())
        asyncio.create_task(self._log_watcher_loop())
        asyncio.create_task(self._ay2_consumer_loop())

    async def _queue_watcher_loop(self):
        """Monitors the ay2_dispatch_queue/ for pending prompt mandates."""
        while self.is_running:
            try:
                if os.path.exists(self.queue_dir):
                    files = [f for f in os.listdir(self.queue_dir) if f.startswith("prompt_") and f.endswith(".json")]
                    for file in files:
                        full_path = os.path.join(self.queue_dir, file)
                        logger.info(f"Detected incoming prompt mandate: {file}")
                        await self._process_prompt_file(full_path)
            except Exception as e:
                logger.error(f"Queue Watcher Loop fault: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _log_watcher_loop(self):
        """Tails application spooled logs looking for tracebacks and failures."""
        while self.is_running:
            try:
                if os.path.exists(self.logs_dir):
                    files = [f for f in os.listdir(self.logs_dir) if f.endswith(".log")]
                    for file in files:
                        full_path = os.path.join(self.logs_dir, file)
                        await self._tail_log_file(full_path)
            except Exception as e:
                logger.error(f"Log Watcher Loop fault: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _ay2_consumer_loop(self):
        """
        ── PHASE 12.1 AY2 AUTO-CONSUMPTION LOOP ──
        Persistently monitors the dispatch queue for pending self-healing blueprints
        and executes AST splices followed by Playwright E2E verifications.
        """
        while self.is_running:
            try:
                if os.path.exists(self.queue_dir):
                    files = [f for f in os.listdir(self.queue_dir) if f.startswith("pending_srepatch_") and f.endswith(".json")]
                    for file in files:
                        full_path = os.path.join(self.queue_dir, file)
                        logger.info(f"[AY2 Actuator] Ingesting pending patch blueprint: {file}")
                        await self._consume_patch_blueprint(full_path)
            except Exception as e:
                logger.error(f"AY2 Auto-Consumption Loop fault: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _tail_log_file(self, filepath: str):
        """Reads only newly appended content from log file and searches for Tracebacks."""
        try:
            stat = os.stat(filepath)
            prev_size = self._processed_logs.get(filepath, 0)
            
            # Initialize tracker on first encounter
            if prev_size == 0:
                self._processed_logs[filepath] = stat.st_size
                return

            if stat.st_size > prev_size:
                async with aiofiles.open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    await f.seek(prev_size)
                    new_content = await f.read()
                
                self._processed_logs[filepath] = stat.st_size
                
                # Check for crash tracebacks
                if "Traceback (most recent call last):" in new_content or "ZeroDivisionError" in new_content:
                    logger.warning(f"Watchdog tailer detected traceback inside: {os.path.basename(filepath)}")
                    await self._generate_self_healing_blueprint(new_content, filepath)
            elif stat.st_size < prev_size:
                # Log was truncated/cleared, reset tracker
                self._processed_logs[filepath] = stat.st_size
        except Exception as e:
            logger.error(f"Failed to tail log {filepath}: {e}")

    async def _process_prompt_file(self, filepath: str):
        """Processes a prompt json file, queries Gemini, and outputs the blueprint."""
        try:
            async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)

            mandate = data.get("mandate", "")
            target_file = data.get("target_file", "")
            payload_type = data.get("payload_type", "STRUCTURAL_MANDATE")
            
            # Resolve physical target file path securely
            target_abs = ""
            target_content = ""
            if target_file:
                target_abs = os.path.abspath(os.path.join(BASE_DIR, target_file.lstrip("/\\")))
                if target_abs.startswith(BASE_DIR) and os.path.exists(target_abs):
                    async with aiofiles.open(target_abs, "r", encoding="utf-8", errors="ignore") as tf:
                        target_content = await tf.read()

            logger.info(f"Compiling context payload for mandate targeting: {target_file}")
            compiled_payload = rigid_compile_payload(mandate, target_content, target_file)
            
            # Send to Gemini
            blueprint = await transmit_mandate_to_gemini(compiled_payload, payload_type=payload_type)
            if blueprint:
                # Output directly back to queue as pending patch
                output_filename = f"pending_srepatch_{int(time.time())}.json"
                output_path = os.path.join(self.queue_dir, output_filename)
                
                async with aiofiles.open(output_path, "w", encoding="utf-8") as out:
                    await out.write(json.dumps(blueprint, indent=2))
                
                logger.info(f"Successfully compiled and spooled self-healing blueprint: {output_filename}")
                
            # Eradicate consumed prompt file
            os.remove(filepath)
        except Exception as e:
            logger.error(f"Failed to process prompt file {filepath}: {e}")
            try:
                os.remove(filepath)
            except:
                pass

    async def _generate_self_healing_blueprint(self, traceback_content: str, log_filepath: str):
        """Creates a dynamic patch blueprint based on log error context."""
        try:
            # Simple heuristic to identify target file in traceback
            target_file = "api.py"
            for line in traceback_content.splitlines():
                if 'File "' in line and BASE_DIR in line:
                    parts = line.split('File "')
                    if len(parts) > 1:
                        extracted = parts[1].split('"')[0]
                        if os.path.exists(extracted):
                            target_file = os.path.relpath(extracted, BASE_DIR)
                            break

            target_abs = os.path.join(BASE_DIR, target_file)
            target_content = ""
            if os.path.exists(target_abs):
                async with aiofiles.open(target_abs, "r", encoding="utf-8", errors="ignore") as tf:
                    target_content = await tf.read()

            mandate = f"Auto-Heal tracebacks detected in {os.path.basename(log_filepath)}:\n{traceback_content}"
            compiled_payload = rigid_compile_payload(mandate, target_content, target_file)
            
            # Query Gemini
            blueprint = await transmit_mandate_to_gemini(compiled_payload, payload_type="SELF_HEALING_PATCH")
            if blueprint:
                output_filename = f"pending_srepatch_auto_{int(time.time())}.json"
                output_path = os.path.join(self.queue_dir, output_filename)
                async with aiofiles.open(output_path, "w", encoding="utf-8") as out:
                    await out.write(json.dumps(blueprint, indent=2))
                logger.info(f"Spooled SRE auto-healing patch: {output_filename}")
        except Exception as e:
            logger.error(f"Failed to generate self-healing blueprint: {e}")

    # ─────────────────────────────────────────────────────────────────────────────
    # 4. AY2 AUTO-CONSUMPTION IMPLEMENTATION
    # ─────────────────────────────────────────────────────────────────────────────

    async def _execute_ast_splice(self, target_file: str, search_content: str, replace_content: str) -> bool:
        """Natively applies the SEARCH/REPLACE splice to the filesystem."""
        target_abs = os.path.abspath(os.path.join(BASE_DIR, target_file.lstrip("/\\")))
        if not target_abs.startswith(BASE_DIR) or not os.path.exists(target_abs):
            logger.error(f"[AY2 Actuator] AST Splice blocked: path traversal violation or file missing: {target_file}")
            return False

        try:
            async with aiofiles.open(target_abs, "r", encoding="utf-8", errors="ignore") as f:
                original = await f.read()

            if search_content not in original:
                logger.error(f"[AY2 Actuator] AST Splice failed: search_content not found in '{target_file}'")
                return False

            new_content = original.replace(search_content, replace_content)
            async with aiofiles.open(target_abs, "w", encoding="utf-8") as f:
                await f.write(new_content)

            logger.info(f"[AY2 Actuator] Natively applied AST Splice chunk to '{target_file}'")
            return True
        except Exception as e:
            logger.error(f"[AY2 Actuator] AST Splice failed on '{target_file}': {e}")
            return False

    async def _run_playwright_verification(self) -> bool:
        """Dynamically launches headless Playwright E2E spec validations in factory_ui context."""
        factory_ui_dir = os.path.join(BASE_DIR, "factory_ui")
        logger.info("[AY2 Actuator] Invoking headless Playwright E2E verification spec...")
        try:
            proc = await asyncio.create_subprocess_exec(
                "npx.cmd", "playwright", "test", "tests/e2e/phase_11_6_critic_ontology.spec.ts",
                cwd=factory_ui_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                logger.info("[AY2 Actuator] Playwright verification PASSED successfully!")
                return True
            else:
                logger.error(f"[AY2 Actuator] Playwright verification FAILED with exit code {proc.returncode}.")
                logger.error(f"Stdout:\n{stdout.decode('utf-8', errors='replace')}")
                logger.error(f"Stderr:\n{stderr.decode('utf-8', errors='replace')}")
                return False
        except Exception as e:
            logger.error(f"[AY2 Actuator] Failed to execute Playwright validation: {e}")
            return False

    async def _consume_patch_blueprint(self, filepath: str):
        """Performs atomic-swap splice, E2E validation, and either commits/archives or rolls back."""
        try:
            async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
                raw_json = await f.read()
                patch_data = json.loads(raw_json)

            nodes = patch_data.get("nodes", [])
            backups = {}
            success = True

            # 1. Back up original contents and Apply Splices
            for node in nodes:
                if node.get("action") == "AST_SPLICE":
                    target_file = node.get("target_file", "")
                    search_content = node.get("search_content", "")
                    replace_content = node.get("replace_content", "")

                    target_abs = os.path.abspath(os.path.join(BASE_DIR, target_file.lstrip("/\\")))
                    if os.path.exists(target_abs):
                        async with aiofiles.open(target_abs, "r", encoding="utf-8", errors="ignore") as f:
                            backups[target_abs] = await f.read()

                    splice_ok = await self._execute_ast_splice(target_file, search_content, replace_content)
                    if not splice_ok:
                        success = False
                        break

            # 2. Run Headless Playwright Verification
            if success:
                validation_ok = await self._run_playwright_verification()
                if not validation_ok:
                    success = False

            # 3. Decision Gate: Archive or Rollback
            if success:
                logger.info(f"[AY2 Actuator] Patch blueprint fully verified. Sealing and archiving...")
                archived_filename = f"archived_{os.path.basename(filepath)}"
                archived_path = os.path.join(self.queue_dir, archived_filename)
                
                async with aiofiles.open(archived_path, "w", encoding="utf-8") as f:
                    await f.write(raw_json)
                
                os.remove(filepath)
                logger.info(f"[AY2 Actuator] Successfully archived patch blueprint: {archived_filename}")
            else:
                logger.warning("[AY2 Actuator] Validation failed! Initiating safety rollback...")
                for target_abs, original_text in backups.items():
                    try:
                        async with aiofiles.open(target_abs, "w", encoding="utf-8") as f:
                            await f.write(original_text)
                        logger.info(f"[AY2 Actuator] Successfully restored: {target_abs}")
                    except Exception as rb_err:
                        logger.error(f"[AY2 Actuator] Rollback failed for {target_abs}: {rb_err}")

                # Log failure to central_error.log
                central_error_log = os.path.join(BASE_DIR, "central_error.log")
                try:
                    async with aiofiles.open(central_error_log, "a", encoding="utf-8") as f:
                        await f.write(f"\n[{datetime.now().isoformat()}] [AY2 Actuator] Patch failed verification: {os.path.basename(filepath)}. Changes rolled back.\n")
                except:
                    pass

                # Move to broken for audit
                broken_filename = f"broken_{os.path.basename(filepath)}"
                broken_path = os.path.join(self.queue_dir, broken_filename)
                async with aiofiles.open(broken_path, "w", encoding="utf-8") as f:
                    await f.write(raw_json)
                os.remove(filepath)
                logger.warning(f"[AY2 Actuator] Failing blueprint quarantined: {broken_filename}")

        except Exception as e:
            logger.error(f"[AY2 Actuator] Error consuming patch {filepath}: {e}")
            try:
                os.remove(filepath)
            except:
                pass

# ─────────────────────────────────────────────────────────────────────────────
# 5. HEADLESS PROCESS LAUNCHER
# ─────────────────────────────────────────────────────────────────────────────

def launch_detached_daemon():
    """
    Launches alpha_orchestrator.py headlessly as a completely detached background process group.
    Perfected utilizing Windows process creation flags (CREATE_NEW_PROCESS_GROUP, DETACHED_PROCESS).
    """
    python_exe = sys.executable
    script_path = os.path.abspath(__file__)
    
    # Process Creation Flags for complete session detachment on Windows
    # CREATE_NEW_PROCESS_GROUP = 0x00000200
    # DETACHED_PROCESS = 0x00000008
    creation_flags = 0x00000200 | 0x00000008

    logger.info("Dispatched headlessly detached background execution sequence...")
    try:
        subprocess.Popen(
            [python_exe, "-u", script_path, "--daemon"],
            creationflags=creation_flags,
            close_fds=True,
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        logger.info("[SUCCESS] AlphaOrchestrator daemon successfully detached from parent CLI session!")
    except Exception as e:
        logger.error(f"Failed to deploy headless daemon process group: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# 6. CLI RUNNER / DAEMON TRIGGER
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        # Run persistent watchdog service
        watchdog = AlphaOrchestratorWatchdog(QUEUE_DIR, LOGS_DIR)
        
        async def main():
            await watchdog.start()
            # Infinite non-blocking loop to maintain server active process state
            while True:
                await asyncio.sleep(3600)
                
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("Daemon interrupted. Shutting down cleanly.")
    else:
        # Standard execution triggers process spawns
        launch_detached_daemon()
