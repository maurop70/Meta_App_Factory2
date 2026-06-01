import asyncio
from typing import Dict, Any
from phantom_core.daemons import EphemeralStagingDaemons
from phantom_core.telemetry import SSEDispatcher
from .skeptic import SkepticRunner as _SkepticRunner
from .ghost_user import GhostUserRunner as _GhostUserRunner

class SkepticRunner(_SkepticRunner):
    """Resilient wrapper providing default base_url to SkepticRunner."""
    def __init__(self, base_url: str = "http://127.0.0.1:5020", *args, **kwargs):
        super().__init__(base_url, *args, **kwargs)

class GhostUserRunner(_GhostUserRunner):
    """Resilient wrapper providing default base_url to GhostUserRunner."""
    def __init__(self, base_url: str = "http://127.0.0.1:5020", *args, **kwargs):
        super().__init__(base_url, *args, **kwargs)

class AdversarialTestAgent:
    def __init__(self):
        self.skeptic = SkepticRunner()
        self.ghost = GhostUserRunner()
        self.telemetry = SSEDispatcher(channel="/api/qa/stream")

    async def execute_full_adversarial_campaign(self, target_app_path: str) -> None:
        daemon = EphemeralStagingDaemons(target=target_app_path)
        try:
            await self.telemetry.push({"status": "booting", "target": target_app_path})
            await daemon.start()

            # Dynamically bind local staging URL to attack matrix runners
            self.skeptic.base_url = daemon.local_url.rstrip("/")
            self.ghost.base_url = daemon.local_url.rstrip("/")

            await self.telemetry.push({"status": "executing_api_fuzzing", "agent": "SkepticRunner"})
            api_ledger = await self.skeptic.run_full_attack()

            await self.telemetry.push({"status": "executing_ui_fuzzing", "agent": "GhostUserRunner"})
            ui_ledger = await self.ghost.run_full_suite()

            final_ledger = {
                "target": target_app_path,
                "api_diagnostics": api_ledger,
                "ui_diagnostics": ui_ledger,
                "conclusion": "PASS" if api_ledger.get("score", 0) >= 70 and ui_ledger.get("score", 0) >= 70 else "FAIL"
            }
            await self.telemetry.push({"status": "completed", "ledger": final_ledger})
        except Exception as e:
            await self.telemetry.push({"status": "fatal_fracture", "error": str(e)})
            raise
        finally:
            await daemon.teardown()
            await self.telemetry.push({"status": "daemon_terminated"})

adversarial_commander = AdversarialTestAgent()
