import os
import json
import logging
import aiofiles

logger = logging.getLogger("RegistryManager")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(SCRIPT_DIR, "agent_registry.json")

async def load_registry() -> dict:
    """Asynchronously load the registry JSON ledger from disk."""
    if not os.path.exists(REGISTRY_PATH):
        # Create an empty registry if missing
        initial_data = {
            "agents": [
                {"id": "master_architect", "name": "Master_Architect_Elite_Logic", "status": "ACTIVE", "port": 5050},
                {"id": "cfo_agent", "name": "CFO_Agent", "status": "ACTIVE", "port": 5070},
                {"id": "cio_agent", "name": "CIO_Agent", "status": "ACTIVE", "port": 5090},
                {"id": "adv_autonomous", "name": "Adv_Autonomous_Agent", "status": "INACTIVE", "port": 5012},
                {"id": "cmo_agent", "name": "CMO_Agent", "status": "ACTIVE", "port": 5020},
                {"id": "venture_architect", "name": "Venture_Architect", "status": "ACTIVE", "port": 5110},
                {"id": "clo_agent", "name": "CLO_Agent", "status": "ACTIVE", "port": 5080}
            ]
        }
        await save_registry(initial_data)
        return initial_data
        
    try:
        async with aiofiles.open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            content = await f.read()
            return json.loads(content)
    except Exception as e:
        logger.error(f"Failed to load agent registry: {e}")
        return {"agents": []}

async def save_registry(registry_data: dict) -> bool:
    """Asynchronously save the registry JSON ledger back to disk."""
    try:
        content = json.dumps(registry_data, indent=2)
        async with aiofiles.open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            await f.write(content)
        return True
    except Exception as e:
        logger.error(f"Failed to save agent registry: {e}")
        return False

async def register_agent(agent_name: str, port: int, status: str = "ACTIVE") -> dict:
    """
    Asynchronously registers a new agent or updates an existing one in the JSON ledger.
    """
    registry = await load_registry()
    agent_id = agent_name.lower().replace("_", "")
    
    # Check if agent already exists
    existing = None
    for agent in registry["agents"]:
        if agent["name"] == agent_name or agent["id"] == agent_id:
            existing = agent
            break
            
    if existing:
        existing["port"] = port
        existing["status"] = status
        logger.info(f"Updated agent registration: {agent_name} on port {port} ({status})")
    else:
        new_agent = {
            "id": agent_id,
            "name": agent_name,
            "status": status,
            "port": port
        }
        registry["agents"].append(new_agent)
        logger.info(f"Registered new agent: {agent_name} on port {port} ({status})")
        
    await save_registry(registry)
    return registry
