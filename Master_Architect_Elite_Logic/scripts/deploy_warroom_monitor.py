import os
import sys
import asyncio

# Setup path to import core architecture modules
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
FACTORY_DIR = os.path.dirname(PARENT_DIR)
sys.path.insert(0, FACTORY_DIR)
sys.path.insert(0, PARENT_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(FACTORY_DIR, ".env"))
    load_dotenv()
except Exception:
    pass

from genesis_orchestrator import GenesisOrchestrator

async def main():
    print("==================================================")
    print("[GENESIS] Programmatic Synthesis: WarRoomMonitor Deployment")
    print("==================================================")
    
    prompt = (
        "Build a WarRoomMonitor agent. It must expose a GET /api/health endpoint "
        "with the exact path '/api/health' (not '/api/v1/health'). "
        "It must utilize 'psutil' to capture live CPU/RAM metrics, and read "
        "'agent_registry.json' to asynchronously ping all active child agent ports via 'httpx', "
        "returning a comprehensive system status JSON contract."
    )
    
    logic_ast = """logger.info("Executing endpoint: /api/health")

# 1. Capture live CPU/RAM metrics
cpu = psutil.cpu_percent(interval=None)
mem = psutil.virtual_memory().percent

# 2. Read agent_registry.json path relative to factory
registry_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Master_Architect_Elite_Logic", "agent_registry.json"))

child_status = {}
overall = "HEALTHY"

if os.path.exists(registry_path):
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
            
        # 3. Asynchronously ping all active child agent ports via httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            tasks = []
            agents_to_ping = []
            for agent in registry.get("agents", []):
                # Skip master_architect and self
                if agent["id"] in ["master_architect", "warroommonitor"] or agent["status"] != "ACTIVE":
                    continue
                agents_to_ping.append(agent)
                # Ping /api/health or root
                tasks.append(client.get(f"http://127.0.0.1:{agent['port']}/"))
                
            if tasks:
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                for agent, resp in zip(agents_to_ping, responses):
                    name = agent["name"]
                    if isinstance(resp, Exception):
                        child_status[name] = "OFFLINE"
                        overall = "DEGRADED"
                    else:
                        if resp.status_code < 500:
                            child_status[name] = "ONLINE"
                        else:
                            child_status[name] = "DEGRADED"
                            overall = "DEGRADED"
    except Exception as reg_err:
        logger.error(f"Error reading registry or pinging: {reg_err}")
        overall = "DEGRADED"
else:
    logger.warning(f"agent_registry.json not found at {registry_path}")
    
return {
    "timestamp": datetime.now().isoformat(),
    "cpu_percent": f"{cpu}%",
    "memory_percent": f"{mem}%",
    "child_agents_status": json.dumps(child_status),
    "overall_status": overall,
    "status": overall
}"""

    route_logic_blocks = [
        {
            "path": "/api/health",
            "method": "GET",
            "imports": [
                "import psutil",
                "import httpx",
                "import os",
                "import json",
                "import asyncio",
                "from datetime import datetime"
            ],
            "logic_ast": logic_ast
        }
    ]

    orchestrator = GenesisOrchestrator()
    success = False
    allocated_port = None
    
    async for event_str in orchestrator.run_stream(prompt, route_logic_blocks=route_logic_blocks):
        # Print without emojis for Windows compatibility
        clean_event = event_str.replace("🧬", "[DNA]").replace("⚙️", "[RUN]").replace("⚠️", "[WARN]").replace("✅", "[PASS]").replace("❌", "[FAIL]").replace("🏗️", "[BUILD]").replace("📁", "[DIR]").replace("💾", "[SAVE]").replace("🚀", "[START]")
        try:
            print(clean_event.strip().encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
        except Exception:
            print("[Event received]")
            
        if "compile_success" in event_str:
            success = True
            try:
                import json
                if event_str.startswith("data: "):
                    payload = json.loads(event_str.strip()[6:])
                    if payload.get("event") == "compile_success":
                        allocated_port = payload.get("port")
            except Exception:
                pass
                
    if success:
        print("\n[SUCCESS] WarRoomMonitor synthesized, compiled, and registered successfully!")
        if allocated_port:
            print(f"Active Child Port: {allocated_port}")
        sys.exit(0)
    else:
        print("\n[ERROR] Synthesis pipeline failed.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
