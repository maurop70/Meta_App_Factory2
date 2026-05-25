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
        "that utilizes 'psutil' to capture live CPU/RAM metrics, and reads "
        "'agent_registry.json' to asynchronously ping all active child agent ports via 'httpx', "
        "returning a comprehensive system status JSON contract."
    )
    
    orchestrator = GenesisOrchestrator()
    success = False
    allocated_port = None
    
    async for event_str in orchestrator.run_stream(prompt):
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
