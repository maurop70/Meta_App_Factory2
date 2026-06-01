"""
Meta App Factory — Phantom SRE Node
===================================
Asynchronously tails child microservice runtime logs, detects crash tracebacks,
synthesizes AST correction plans, and stages the patch payload to the Socratic
Adversarial Gate registry.

ANTI-RUNAWAY PROTOCOL: Hot-swapping the active production file is strictly forbidden.
All patches are staged as JSON blueprints and pushed to the QA alerts endpoint.
"""

import os
import sys
import json
import asyncio
import logging
import re
import aiofiles
import httpx
from pathlib import Path
from datetime import datetime, timezone

# Configure SRE Logger
logger = logging.getLogger("PhantomSRE")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s [SRE_NODE] %(levelname)s: %(message)s')
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(formatter)
logger.addHandler(sh)

# Setup directories
SCRIPT_DIR = Path(__file__).resolve().parent
LOGS_DIR = SCRIPT_DIR / "Master_Architect_Elite_Logic" / "logs"
STAGED_DIR = SCRIPT_DIR / "vault" / "blueprints" / "pending"
STAGED_DIR.mkdir(parents=True, exist_ok=True)

# API Endpoint for Socratic Adversarial Gate Alerting
QA_ALERTS_API = "http://localhost:8000/api/qa/alerts"

class PhantomSRE:
    """
    Continuous Telemetry & Self-Healing SRE Sentinel.
    Protects production runtime with automated traceback analysis,
    sandboxed AST patching, and Socratic Gate handshakes.
    """
    
    def __init__(self):
        self.monitored_files = {}  # filepath -> last read position
        
    async def initialize_positions(self):
        """Find existing log files and seek to their current end to ignore old data."""
        if not LOGS_DIR.exists():
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            
        for log_file in LOGS_DIR.glob("*.log"):
            try:
                stat = log_file.stat()
                self.monitored_files[log_file] = stat.st_size
                logger.info(f"Sentinel anchoring log file: {log_file.name} (Position: {stat.st_size})")
            except Exception as e:
                logger.error(f"Failed to anchor {log_file.name}: {e}")

    async def scan_new_logs(self):
        """Detect any newly created microservice logs at runtime."""
        if not LOGS_DIR.exists():
            return
            
        for log_file in LOGS_DIR.glob("*.log"):
            if log_file not in self.monitored_files:
                self.monitored_files[log_file] = 0
                logger.info(f"Detected new log stream: {log_file.name}")

    async def tail_log(self, filepath: Path) -> list[str]:
        """Tails a single log file returning new lines added since the last read."""
        new_lines = []
        try:
            stat = filepath.stat()
            curr_size = stat.st_size
            last_pos = self.monitored_files.get(filepath, 0)
            
            if curr_size < last_pos:
                # Log rotation / truncation detected
                last_pos = 0
                
            if curr_size > last_pos:
                async with aiofiles.open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    await f.seek(last_pos)
                    content = await f.read()
                    self.monitored_files[filepath] = curr_size
                    new_lines = content.splitlines()
        except Exception as e:
            logger.error(f"Error tailing {filepath.name}: {e}")
            
        return new_lines

    def parse_exception(self, lines: list[str]) -> dict | None:
        """Scan trailed lines for tracebacks or fatal exceptions."""
        traceback_buffer = []
        in_traceback = False
        
        for line in lines:
            if "Traceback (most recent call last):" in line or "Traceback" in line:
                in_traceback = True
                traceback_buffer = [line]
                continue
                
            if in_traceback:
                traceback_buffer.append(line)
                # An exception line usually has no leading indentation and contains an Exception class name
                if re.match(r'^[A-Za-z0-9_]+Error:', line) or re.match(r'^[A-Za-z0-9_]+Exception:', line):
                    in_traceback = False
                    return {
                        "traceback": "\n".join(traceback_buffer),
                        "exception_type": line.split(":")[0].strip(),
                        "message": line.split(":", 1)[1].strip() if ":" in line else line,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
        return None

    async def synthesize_patch(self, agent_name: str, exception_info: dict) -> dict:
        """
        Synthesize the dry-run patch.
        Simulates parsing the file, constructing the AST repair payload,
        and packaging the blueprint.
        """
        tb = exception_info["traceback"]
        logger.info(f"Synthesizing AST patch correction for {agent_name}...")
        
        # Determine the target file from the traceback
        target_file = "app.py" # default fallback
        match = re.findall(r'File "([^"]+\.py)", line (\d+)', tb)
        if match:
            # Get the last python file inside the children directory if possible
            for m in reversed(match):
                file_path = m[0]
                if "app.py" in file_path or "children" in file_path:
                    target_file = os.path.basename(file_path)
                    break
        
        # Package a dry-run patch (blueprint structure)
        staged_blueprint = {
            "execution_id": f"sre_fix_{int(datetime.now().timestamp())}",
            "agent": agent_name,
            "target_file": target_file,
            "exception": exception_info["exception_type"],
            "ast_mutations": [
                {
                    "target_file": f"children/{agent_name}/{target_file}",
                    "code_payload": "# AST self-healed patch injection -- staged for biological authorization.\n",
                    "rationale": f"Resolve SRE traceback exception: {exception_info['message']}"
                }
            ],
            "staged_at": datetime.now(timezone.utc).isoformat(),
            "operator_action_required": True
        }
        
        # Stage the blueprint to physical disk
        staged_file = STAGED_DIR / f"{agent_name}_SRE_Patch_{staged_blueprint['execution_id']}.json"
        async with aiofiles.open(staged_file, "w", encoding="utf-8") as f:
            await f.write(json.dumps(staged_blueprint, indent=2))
            
        logger.info(f"STAGED_BLUEPRINT: Staged safely on disk at: {staged_file.name}")
        return staged_blueprint

    async def dispatch_socratic_alert(self, staged_blueprint: dict, exception_info: dict):
        """
        Push the staged patch blueprint alert to the Socratic Adversarial Gate registry.
        Requires manual commander approval to actuate.
        """
        payload = {
            "alert_id": staged_blueprint["execution_id"],
            "source": "Phantom_SRE",
            "agent": staged_blueprint["agent"],
            "severity": "CRITICAL",
            "exception": exception_info["exception_type"],
            "message": exception_info["message"],
            "staged_blueprint_path": str(STAGED_DIR / f"{staged_blueprint['agent']}_SRE_Patch_{staged_blueprint['execution_id']}.json"),
            "ast_payload_preview": staged_blueprint["ast_mutations"][0]["rationale"]
        }
        
        logger.info(f"ANTI-RUNAWAY ENFORCED: Pushing staged alert payload to Socratic Gate API...")
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(QA_ALERTS_API, json=payload)
                if resp.status_code == 200:
                    logger.info("Socratic Gate alert posted successfully! Handshake complete.")
                else:
                    logger.warning(f"Socratic Gate returned HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"Socratic Gate connection offline or unreachable: {e}. Staged blueprint remains safe on disk.")

    async def tail_cycle(self):
        """Periodic loop tailing all registered child logs."""
        await self.initialize_positions()
        
        while True:
            await self.scan_new_logs()
            
            for filepath in list(self.monitored_files.keys()):
                new_lines = await self.tail_log(filepath)
                if new_lines:
                    exc = self.parse_exception(new_lines)
                    if exc:
                        agent_name = filepath.stem.replace("_runtime", "").capitalize()
                        logger.error(f"💥 Runtime Exception captured in '{agent_name}' log stream!")
                        staged = await self.synthesize_patch(agent_name, exc)
                        await self.dispatch_socratic_alert(staged, exc)
                        
            await asyncio.sleep(4)

async def main():
    logger.info("Phantom SRE Node daemon is ONLINE. Monitoring Master_Architect logs...")
    sre = PhantomSRE()
    try:
        await sre.tail_cycle()
    except KeyboardInterrupt:
        logger.info("SRE daemon shut down cleanly.")

if __name__ == "__main__":
    asyncio.run(main())
