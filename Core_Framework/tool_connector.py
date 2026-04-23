"""
tool_connector.py — Standardized Agent Tool Access Layer
═══════════════════════════════════════════════════════
CIO Recommendation #5: Standardize Agent Tooling and Integration.
Provides a unified interface for agents to access external APIs,
databases, and internal systems with built-in retries and logging.
"""

import os
import json
import logging
import aiohttp
import asyncio
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger("ToolConnector")

class ToolConnector:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.registry = {}

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def register_tool(self, name: str, endpoint: str, auth_type: str = "Bearer"):
        """Registers a tool with the connector."""
        self.registry[name] = {
            "endpoint": endpoint,
            "auth_type": auth_type
        }
        logger.info(f"Connector: Tool '{name}' registered.")

    async def call_tool(self, tool_name: str, payload: Dict[str, Any], retries: int = 2) -> Dict[str, Any]:
        """
        Executes a tool call with consistent error handling and retry logic.
        """
        if tool_name not in self.registry:
            return {"error": f"Tool '{tool_name}' not found in registry."}

        tool = self.registry[tool_name]
        endpoint = tool["endpoint"]
        
        # Ensure session exists
        close_session = False
        if not self.session:
            self.session = aiohttp.ClientSession()
            close_session = True

        for attempt in range(retries + 1):
            try:
                async with self.session.post(endpoint, json=payload, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {"status": "success", "data": data}
                    else:
                        logger.warning(f"Tool {tool_name} failed (Attempt {attempt+1}): {resp.status}")
                        if attempt == retries:
                            return {"error": f"Tool failed with status {resp.status}", "status_code": resp.status}
            except Exception as e:
                logger.error(f"Connector Exception ({tool_name}): {e}")
                if attempt == retries:
                    return {"error": str(e)}
            
            # Exponential backoff
            await asyncio.sleep(2 ** attempt)

        if close_session:
            await self.session.close()
            self.session = None

        return {"error": "Maximum retries reached."}

# Standardized wrapper for the native auto_heal logging
def log_tool_event(tool_name: str, action: str, data: dict):
    from auto_heal import _log_heal_event
    _log_heal_event("ToolConnector", f"{tool_name}: {action}", data, "INFRA_EVENT")
