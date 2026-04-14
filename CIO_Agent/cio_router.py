"""
cio_router.py — CIO Hybrid LLM Routing Engine
═══════════════════════════════════════════════════════════════
Routes CIO generative tasks between:
  - LOCAL:  Ollama (nemotron-mini:4b) for routine dev tasks
            (basic formatting, syntax checking, generic scripting)
  - CLOUD:  Gemini 2.5 Flash for high-complexity strategic tasks
            (Architecture design, security audits, database schemas)

Classification is based on "Technical Complexity".

Features:
  - Circuit Breaker: Auto-opens after 2 consecutive Ollama failures.
  - Persistent Telemetry: Stats survive restarts via cio_telemetry.json.
  - Graceful Degradation: Transparent fallback to Gemini cloud.
"""

import os
import time
import json
import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional

import aiohttp

logger = logging.getLogger("CIO_LLM_Router")

# ═══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "nemotron-mini:4b")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT", "30"))

# Circuit breaker
CIRCUIT_BREAKER_FAIL_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_FAILS", "2"))
CIRCUIT_BREAKER_PROBE_INTERVAL = int(os.getenv("CIRCUIT_BREAKER_PROBE_SECONDS", "60"))

# Telemetry persistence
TELEMETRY_FILE = Path(__file__).parent / "cio_telemetry.json"

# ═══════════════════════════════════════════════════════════════
#  TECHNICAL COMPLEXITY CLASSIFICATION
# ═══════════════════════════════════════════════════════════════

# LOW complexity → route to LOCAL (Ollama)
LOCAL_TASK_TYPES = frozenset({
    "format_code",
    "syntax_check",
    "generic_script",
    "docstring_gen",
    "readme_update",
})

# HIGH complexity → route to CLOUD (Gemini)
CLOUD_TASK_TYPES = frozenset({
    "architecture_design",
    "security_audit",
    "database_schema",
    "upgrade_memo",       # Main CIO Agent feature
    "tech_stack_analysis",
    "api_design",
})

# ═══════════════════════════════════════════════════════════════
#  SYSTEM PROMPTS
# ═══════════════════════════════════════════════════════════════

CLOUD_SYSTEM_PROMPT = """You are the Antigravity CIO Agent — Chief Innovation Officer.
You are an uncompromising strategic software architect and technology advisor. 
Your mission: identify highest-impact upgrades, perform deep technical audits, 
and design state-of-the-art system architecture.

RULES:
1. Ground technical advice in facts and modern best practices (e.g., Python 3.11+, React 18).
2. Prioritize security, scalability, and asynchronous patterns.
3. Be definitive. Do not offer wishy-washy trade-offs without making a final recommendation.
4. Return ONLY the requested Markdown/JSON content. No preamble.
"""

LOCAL_SYSTEM_PROMPT = """You are an automated coding assistant.
Focus on accurate syntax, formatting, and standard boilerplate.

Rules:
- Write clean and correct code.
- Return ONLY the exact content requested.
"""

# ═══════════════════════════════════════════════════════════════
#  ROUTING TELEMETRY (Persistent)
# ═══════════════════════════════════════════════════════════════

@dataclass
class RoutingStats:
    total_requests: int = 0
    local_requests: int = 0
    cloud_requests: int = 0
    fallback_count: int = 0
    circuit_breaker_trips: int = 0
    last_request_at: Optional[str] = None
    avg_local_latency_ms: float = 0.0
    avg_cloud_latency_ms: float = 0.0
    _local_latencies: list = field(default_factory=list)
    _cloud_latencies: list = field(default_factory=list)
    _filepath: Optional[Path] = field(default=None, repr=False)

    def __post_init__(self):
        self._filepath = TELEMETRY_FILE

    def record(self, provider: str, latency_ms: float):
        self.total_requests += 1
        self.last_request_at = datetime.now().isoformat()
        if provider == "ollama":
            self.local_requests += 1
            self._local_latencies.append(latency_ms)
            if len(self._local_latencies) > 100:
                self._local_latencies = self._local_latencies[-100:]
            self.avg_local_latency_ms = round(sum(self._local_latencies) / len(self._local_latencies), 1)
        elif provider in ("gemini", "gemini_fallback"):
            self.cloud_requests += 1
            if provider == "gemini_fallback":
                self.fallback_count += 1
            self._cloud_latencies.append(latency_ms)
            if len(self._cloud_latencies) > 100:
                self._cloud_latencies = self._cloud_latencies[-100:]
            self.avg_cloud_latency_ms = round(sum(self._cloud_latencies) / len(self._cloud_latencies), 1)
        self._persist()

    def record_circuit_trip(self):
        self.circuit_breaker_trips += 1
        self._persist()

    def _persist(self):
        try:
            data = self.to_dict()
            data["_local_latencies"] = self._local_latencies[-20:]
            data["_cloud_latencies"] = self._cloud_latencies[-20:]
            self._filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to persist telemetry: {e}")

    @classmethod
    def load(cls) -> "RoutingStats":
        stats = cls()
        try:
            if TELEMETRY_FILE.exists():
                data = json.loads(TELEMETRY_FILE.read_text(encoding="utf-8"))
                stats.total_requests = data.get("total_requests", 0)
                stats.local_requests = data.get("local_requests", 0)
                stats.cloud_requests = data.get("cloud_requests", 0)
                stats.fallback_count = data.get("fallback_count", 0)
                stats.circuit_breaker_trips = data.get("circuit_breaker_trips", 0)
                stats.last_request_at = data.get("last_request_at")
                stats.avg_local_latency_ms = data.get("avg_local_latency_ms", 0.0)
                stats.avg_cloud_latency_ms = data.get("avg_cloud_latency_ms", 0.0)
                stats._local_latencies = data.get("_local_latencies", [])
                stats._cloud_latencies = data.get("_cloud_latencies", [])
                logger.info(f"CIO Telemetry restored: {stats.total_requests} requests")
        except Exception as e:
            logger.warning(f"Could not load telemetry ({e}), starting fresh")
        return stats

    def to_dict(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "local_requests": self.local_requests,
            "cloud_requests": self.cloud_requests,
            "fallback_count": self.fallback_count,
            "circuit_breaker_trips": self.circuit_breaker_trips,
            "last_request_at": self.last_request_at,
            "avg_local_latency_ms": self.avg_local_latency_ms,
            "avg_cloud_latency_ms": self.avg_cloud_latency_ms,
        }

# ═══════════════════════════════════════════════════════════════
#  OLLAMA CLIENT
# ═══════════════════════════════════════════════════════════════

class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.generate_url = f"{self.base_url}/api/generate"
        self.tags_url = f"{self.base_url}/api/tags"

    async def is_reachable(self) -> bool:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(self.tags_url) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def generate(self, prompt: str, system: str = LOCAL_SYSTEM_PROMPT) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": 0.2, "top_p": 0.9, "num_predict": 2048}
        }
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=OLLAMA_TIMEOUT_SECONDS)) as session:
            async with session.post(self.generate_url, json=payload) as resp:
                if resp.status != 200:
                    raise ConnectionError(f"Ollama error {resp.status}")
                data = await resp.json()
                return data.get("response", "").strip()

    async def health_status(self) -> dict:
        return {
            "ollama_reachable": await self.is_reachable(),
            "ollama_url": self.base_url,
            "ollama_model": self.model,
        }

# ═══════════════════════════════════════════════════════════════
#  CIRCUIT BREAKER
# ═══════════════════════════════════════════════════════════════

class CircuitBreaker:
    def __init__(self, fail_threshold: int = CIRCUIT_BREAKER_FAIL_THRESHOLD, probe_interval: int = CIRCUIT_BREAKER_PROBE_INTERVAL):
        self.state: str = "CLOSED"
        self.consecutive_failures: int = 0
        self.fail_threshold: int = fail_threshold
        self.probe_interval: int = probe_interval
        self.last_failure_at: Optional[str] = None
        self.last_recovery_at: Optional[str] = None
        self._probe_task: Optional[asyncio.Task] = None

    def record_success(self):
        self.consecutive_failures = 0
        if self.state == "OPEN":
            self._close()

    def record_failure(self, stats: RoutingStats):
        self.consecutive_failures += 1
        self.last_failure_at = datetime.now().isoformat()
        if self.consecutive_failures >= self.fail_threshold and self.state == "CLOSED":
            self._open(stats)

    def is_open(self) -> bool:
        return self.state == "OPEN"

    def _open(self, stats: RoutingStats):
        self.state = "OPEN"
        stats.record_circuit_trip()
        if self._probe_task is None or self._probe_task.done():
            self._probe_task = asyncio.ensure_future(self._probe_loop())

    def _close(self):
        self.state = "CLOSED"
        self.consecutive_failures = 0
        self.last_recovery_at = datetime.now().isoformat()

    async def _probe_loop(self):
        ollama_tags = f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags"
        while self.state == "OPEN":
            await asyncio.sleep(self.probe_interval)
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                    async with session.get(ollama_tags) as resp:
                        if resp.status == 200:
                            self._close()
                            return
            except Exception:
                pass

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "consecutive_failures": self.consecutive_failures,
            "fail_threshold": self.fail_threshold,
        }

# ═══════════════════════════════════════════════════════════════
#  CIO ROUTER
# ═══════════════════════════════════════════════════════════════

class CIORouter:
    def __init__(self):
        self.ollama = OllamaClient()
        self.stats = RoutingStats.load()
        self.circuit_breaker = CircuitBreaker()

    def classify_request(self, task_type: str, prompt_length: int = 0) -> Tuple[str, str]:
        if task_type in CLOUD_TASK_TYPES:
            return ("cloud", f"High-complexity architecture task: {task_type}")
        if task_type in LOCAL_TASK_TYPES:
            return ("local", f"Routine development task: {task_type}")
        if prompt_length > 4000:
            return ("cloud", f"Complex context ({prompt_length} chars)")
        return ("cloud", f"Default fallback for unknown task: {task_type}")

    async def generate(self, prompt: str, task_type: str = "upgrade_memo", system_override: Optional[str] = None) -> Tuple[str, str]:
        """Returns (generated_text, provider)"""
        classification, _ = self.classify_request(task_type, len(prompt))
        start_time = time.time()

        if classification == "local" and self.circuit_breaker.is_open():
            classification = "cloud_fallback"

        if classification == "local":
            try:
                sys_prompt = system_override or LOCAL_SYSTEM_PROMPT
                text = await self.ollama.generate(prompt=prompt, system=sys_prompt)
                elapsed_ms = round((time.time() - start_time) * 1000, 1)
                self.stats.record("ollama", elapsed_ms)
                self.circuit_breaker.record_success()
                return text, "ollama"
            except Exception as e:
                logger.warning(f"Ollama fallback triggered: {e}")
                self.circuit_breaker.record_failure(self.stats)
                classification = "cloud_fallback"

        provider = "gemini_fallback" if classification == "cloud_fallback" else "gemini"
        try:
            gemini_key = os.getenv("GEMINI_API_KEY")
            if not gemini_key:
                elapsed = round((time.time() - start_time) * 1000, 1)
                self.stats.record(provider, elapsed)
                return "API_KEY_ERROR", "error"

            from google import genai
            client = genai.Client(api_key=gemini_key)
            system = system_override or CLOUD_SYSTEM_PROMPT
            
            # This is specifically a sync call right now, we will wrap in asyncio if needed, 
            # but google.genai has async client. Let's use it properly async for performance.
            # Actually, google.genai client defaults to sync. The async client is client.aio.
            response = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system
                )
            )
            text = response.text.strip()
            elapsed_ms = round((time.time() - start_time) * 1000, 1)
            self.stats.record(provider, elapsed_ms)
            return text, provider

        except Exception as e:
            elapsed = round((time.time() - start_time) * 1000, 1)
            self.stats.record(provider, elapsed)
            logger.error(f"Generate fail: {e}")
            return f"Error: {str(e)}", "error"

    async def get_status(self) -> dict:
        health = await self.ollama.health_status()
        return {
            **health,
            "cloud_provider": "gemini-2.5-pro",
            "circuit_breaker": self.circuit_breaker.to_dict(),
            "telemetry_persistent": True,
            "local_task_types": sorted(LOCAL_TASK_TYPES),
            "cloud_task_types": sorted(CLOUD_TASK_TYPES),
            **self.stats.to_dict(),
        }
