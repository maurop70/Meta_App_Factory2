"""
llm_router.py — Hybrid LLM Routing Engine (CIO Discovery #3)
═══════════════════════════════════════════════════════════════
Routes CFO audit narrative generation between:
  - LOCAL:  Ollama (nemotron-mini:4b) for routine, low-fragility reports
  - CLOUD:  Gemini 2.5 Flash for strategic, high-fragility escalations

Features:
  - Circuit Breaker: Auto-opens after 2 consecutive Ollama failures,
    bypasses with zero latency penalty. Background probe closes it
    when Ollama recovers.
  - Persistent Telemetry: Routing stats survive server restarts via
    local JSON file (llm_telemetry.json).
  - Graceful Degradation: If Ollama is unreachable, transparently
    degrades to Gemini cloud. Zero impact on deterministic math
    pipeline (cfo_logic.py).
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

logger = logging.getLogger("CFO_LLM_Router")


# ═══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "nemotron-mini:4b")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT", "30"))
LOCAL_THRESHOLD = float(os.getenv("LLM_LOCAL_THRESHOLD", "30"))

# Circuit breaker config
CIRCUIT_BREAKER_FAIL_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_FAILS", "2"))
CIRCUIT_BREAKER_PROBE_INTERVAL = int(os.getenv("CIRCUIT_BREAKER_PROBE_SECONDS", "60"))

# Telemetry persistence
TELEMETRY_FILE = Path(__file__).parent / "llm_telemetry.json"

# ═══════════════════════════════════════════════════════════════
#  SYSTEM PROMPTS
# ═══════════════════════════════════════════════════════════════

# Cloud prompt — full strategic reasoning (already exists in server.py as CFO_SYSTEM_PROMPT)
CLOUD_SYSTEM_PROMPT = """You are the Antigravity CFO Agent (Institutional Mathematics Division).
You are to generate a highly strategic, qualitative "War Room Audit Report" based on the provided deterministic mathematical inputs.

CRITICAL DIRECTIVE:
You have received a MATHEMATICALLY VERIFIED `CFOAnalysisResult` JSON. 
You MUST NOT recalculate any of these numbers. You are strictly forbidden from performing arithmetic.
Your sole job is to READ the JSON and generate qualitative insights identifying systemic, existential fragility.

RULES:
1. If the fragility_index > 50, escalate warnings to the CTO/Master Architect immediately.
2. If runway_months < 6, flag extreme risk and recommend immediate capital injection or aggressive OPEX reduction.
3. Write in concise, C-Suite level terminology (e.g., "debt sculpting", "fixed-point convergence", "drawdown risk").
4. Return ONLY the narrative audit report text. Do not return JSON or markdown code blocks around the text.
"""

# Local prompt — structured template optimized for compact models
LOCAL_SYSTEM_PROMPT = """You are a financial report writer for the Antigravity CFO Agent.
Generate a concise audit narrative from the provided JSON data.
Do NOT perform any math — all numbers are pre-verified.

Use this EXACT structure:

EXECUTIVE SUMMARY
[1-2 sentences on overall financial health]

FRAGILITY ASSESSMENT
[Comment on the fragility_index value and what it means for operations]

PORTFOLIO PERFORMANCE
[Summarize ROI, spend utilization, and campaign performance]

RUNWAY STATUS
[Comment on burn rate and runway months if available]

RECOMMENDATION
[1-2 actionable items based on the data]

Rules:
- Use professional C-Suite language
- Never recalculate numbers
- Keep total output under 300 words
- Return ONLY the report text, no JSON or code blocks
"""


# ═══════════════════════════════════════════════════════════════
#  ROUTING TELEMETRY (Persistent)
# ═══════════════════════════════════════════════════════════════

@dataclass
class RoutingStats:
    """Persistent telemetry for LLM routing decisions.
    Automatically saves to llm_telemetry.json after each request."""
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
            # Keep only last 100 latencies to bound memory
            if len(self._local_latencies) > 100:
                self._local_latencies = self._local_latencies[-100:]
            self.avg_local_latency_ms = round(
                sum(self._local_latencies) / len(self._local_latencies), 1
            )
        elif provider in ("gemini", "gemini_fallback"):
            self.cloud_requests += 1
            if provider == "gemini_fallback":
                self.fallback_count += 1
            self._cloud_latencies.append(latency_ms)
            if len(self._cloud_latencies) > 100:
                self._cloud_latencies = self._cloud_latencies[-100:]
            self.avg_cloud_latency_ms = round(
                sum(self._cloud_latencies) / len(self._cloud_latencies), 1
            )
        self._persist()

    def record_circuit_trip(self):
        self.circuit_breaker_trips += 1
        self._persist()

    def _persist(self):
        """Write stats to disk so they survive restarts."""
        try:
            data = self.to_dict()
            data["_local_latencies"] = self._local_latencies[-20:]  # Keep last 20 for avg recalc
            data["_cloud_latencies"] = self._cloud_latencies[-20:]
            self._filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to persist telemetry: {e}")

    @classmethod
    def load(cls) -> "RoutingStats":
        """Load persisted stats from disk, or return fresh instance."""
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
                logger.info(
                    f"Telemetry restored: {stats.total_requests} total requests "
                    f"({stats.local_requests} local, {stats.cloud_requests} cloud, "
                    f"{stats.fallback_count} fallbacks, {stats.circuit_breaker_trips} circuit trips)"
                )
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
    """
    Async HTTP client wrapping the Ollama REST API.
    Targets compact models for structured financial narrative generation.
    """

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.generate_url = f"{self.base_url}/api/generate"
        self.tags_url = f"{self.base_url}/api/tags"

    async def is_reachable(self) -> bool:
        """Check if Ollama server is responding."""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as session:
                async with session.get(self.tags_url) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def is_model_loaded(self) -> bool:
        """Check if the target model is available in Ollama."""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as session:
                async with session.get(self.tags_url) as resp:
                    if resp.status != 200:
                        return False
                    data = await resp.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    # Match on base name (e.g., "nemotron-mini:4b" matches "nemotron-mini:4b")
                    return any(self.model in m for m in models)
        except Exception:
            return False

    async def generate(self, prompt: str, system: str = LOCAL_SYSTEM_PROMPT) -> str:
        """
        Generate text from the local Ollama model.
        Uses the /api/generate endpoint with stream=false for simplicity.
        Raises on timeout or connection error.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": 0.4,     # Low creativity — structured output
                "top_p": 0.9,
                "num_predict": 1024,    # Cap output length
            }
        }

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=OLLAMA_TIMEOUT_SECONDS)
        ) as session:
            async with session.post(self.generate_url, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise ConnectionError(
                        f"Ollama returned {resp.status}: {error_text[:200]}"
                    )
                data = await resp.json()
                return data.get("response", "").strip()

    async def health_status(self) -> dict:
        """Full health report for the /api/llm/status endpoint."""
        reachable = await self.is_reachable()
        model_loaded = await self.is_model_loaded() if reachable else False
        return {
            "ollama_reachable": reachable,
            "ollama_url": self.base_url,
            "ollama_model": self.model,
            "ollama_model_loaded": model_loaded,
        }


# ═══════════════════════════════════════════════════════════════
#  CIRCUIT BREAKER
# ═══════════════════════════════════════════════════════════════

class CircuitBreaker:
    """
    Circuit breaker for Ollama availability.
    
    States:
      CLOSED  — Ollama is healthy, requests route normally.
      OPEN    — Ollama has failed N times consecutively. All requests
                bypass Ollama instantly (zero latency penalty).
                A background probe pings Ollama every PROBE_INTERVAL.
                When probe succeeds → state flips to CLOSED.
    """

    def __init__(self, fail_threshold: int = CIRCUIT_BREAKER_FAIL_THRESHOLD,
                 probe_interval: int = CIRCUIT_BREAKER_PROBE_INTERVAL):
        self.state: str = "CLOSED"
        self.consecutive_failures: int = 0
        self.fail_threshold: int = fail_threshold
        self.probe_interval: int = probe_interval
        self.last_failure_at: Optional[str] = None
        self.last_recovery_at: Optional[str] = None
        self._probe_task: Optional[asyncio.Task] = None

    def record_success(self):
        """Ollama responded successfully — reset failure counter."""
        if self.consecutive_failures > 0:
            logger.info(
                f"Circuit Breaker: Ollama success after {self.consecutive_failures} failures — counter reset"
            )
        self.consecutive_failures = 0
        # If we were OPEN and got a success (from probe), close the circuit
        if self.state == "OPEN":
            self._close()

    def record_failure(self, stats: RoutingStats):
        """Ollama failed — increment counter, potentially open circuit."""
        self.consecutive_failures += 1
        self.last_failure_at = datetime.now().isoformat()
        logger.warning(
            f"Circuit Breaker: Ollama failure #{self.consecutive_failures} "
            f"(threshold={self.fail_threshold})"
        )
        if self.consecutive_failures >= self.fail_threshold and self.state == "CLOSED":
            self._open(stats)

    def is_open(self) -> bool:
        return self.state == "OPEN"

    def _open(self, stats: RoutingStats):
        """Trip the circuit — bypass Ollama, start probe."""
        self.state = "OPEN"
        stats.record_circuit_trip()
        logger.warning(
            f"⚡ CIRCUIT BREAKER OPEN — Ollama bypassed after "
            f"{self.consecutive_failures} consecutive failures. "
            f"Background probe every {self.probe_interval}s."
        )
        # Start background probe if not already running
        if self._probe_task is None or self._probe_task.done():
            self._probe_task = asyncio.ensure_future(self._probe_loop())

    def _close(self):
        """Ollama recovered — resume local routing."""
        self.state = "CLOSED"
        self.consecutive_failures = 0
        self.last_recovery_at = datetime.now().isoformat()
        logger.info(
            "✅ CIRCUIT BREAKER CLOSED — Ollama recovered, resuming local routing"
        )

    async def _probe_loop(self):
        """Background probe: ping Ollama until it recovers."""
        ollama_tags = f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags"
        while self.state == "OPEN":
            await asyncio.sleep(self.probe_interval)
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as session:
                    async with session.get(ollama_tags) as resp:
                        if resp.status == 200:
                            logger.info("Circuit Breaker probe: Ollama is back online!")
                            self._close()
                            return
                        else:
                            logger.debug(f"Circuit Breaker probe: Ollama returned {resp.status}")
            except Exception as e:
                logger.debug(f"Circuit Breaker probe: Ollama still down ({e})")

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "consecutive_failures": self.consecutive_failures,
            "fail_threshold": self.fail_threshold,
            "probe_interval_seconds": self.probe_interval,
            "last_failure_at": self.last_failure_at,
            "last_recovery_at": self.last_recovery_at,
        }


# ═══════════════════════════════════════════════════════════════
#  LLM ROUTER
# ═══════════════════════════════════════════════════════════════

class LLMRouter:
    """
    Hybrid routing engine for CFO narrative generation.
    
    Decision Logic:
      - fragility_index <= threshold AND runway_months > 12 AND
        no volatile_variables → route to LOCAL (Ollama)
      - Otherwise → route to CLOUD (Gemini)
      - If Circuit Breaker is OPEN → instant bypass to CLOUD
      - If LOCAL fails → automatic FALLBACK to CLOUD + circuit breaker tracking
    """

    def __init__(self):
        self.ollama = OllamaClient()
        self.stats = RoutingStats.load()  # Persistent — restored from disk
        self.circuit_breaker = CircuitBreaker()
        self.threshold = LOCAL_THRESHOLD
        logger.info(
            f"LLM Router initialized | "
            f"Local: {self.ollama.model}@{self.ollama.base_url} | "
            f"Cloud: gemini-2.5-flash | "
            f"Threshold: fragility ≤ {self.threshold} | "
            f"Circuit Breaker: {self.circuit_breaker.fail_threshold} failures → OPEN | "
            f"Restored stats: {self.stats.total_requests} total requests"
        )

    def classify_request(self, math_result) -> Tuple[str, str]:
        """
        Classify a CFOAnalysisResult into a routing decision.
        
        Returns:
            (classification, reason) — e.g., ("local", "Low fragility (18.4), stable runway")
        """
        fragility = math_result.fragility_index
        runway = math_result.runway_months
        volatiles = math_result.volatile_variables

        # High fragility → always cloud
        if fragility > self.threshold:
            return (
                "cloud",
                f"Fragility {fragility} exceeds threshold {self.threshold}"
            )

        # Short runway → cloud (strategic escalation needed)
        if runway < 12 and runway != 999.0:
            return (
                "cloud",
                f"Runway {runway} months is below 12-month safety margin"
            )

        # Volatile variables present → cloud (complex risk narrative needed)
        if len(volatiles) > 2:
            return (
                "cloud",
                f"{len(volatiles)} volatile variables detected — complex risk narrative required"
            )

        # All clear → local
        return (
            "local",
            f"Routine report: fragility {fragility}, runway {runway}mo, "
            f"{len(volatiles)} volatiles"
        )

    async def generate_narrative(
        self, math_json: str, math_result
    ) -> Tuple[str, str]:
        """
        Generate the qualitative audit narrative via the optimal provider.
        
        Args:
            math_json: Serialized CFOAnalysisResult JSON string
            math_result: The CFOAnalysisResult Pydantic model instance
            
        Returns:
            (narrative_text, provider) — provider is "ollama", "gemini", or "gemini_fallback"
        """
        classification, reason = self.classify_request(math_result)
        logger.info(f"LLM Router: {classification.upper()} — {reason}")

        start_time = time.time()

        # ── Circuit Breaker Gate ───────────────────────────────────
        # If circuit is OPEN and classification is "local", bypass instantly
        if classification == "local" and self.circuit_breaker.is_open():
            logger.warning(
                "Circuit Breaker OPEN — bypassing Ollama, routing to Gemini (zero latency penalty)"
            )
            classification = "cloud_fallback"

        # ── Route: LOCAL (Ollama) ──────────────────────────────────
        if classification == "local":
            try:
                narrative = await self.ollama.generate(
                    prompt=math_json,
                    system=LOCAL_SYSTEM_PROMPT
                )
                elapsed_ms = round((time.time() - start_time) * 1000, 1)
                self.stats.record("ollama", elapsed_ms)
                self.circuit_breaker.record_success()
                logger.info(
                    f"Ollama generated narrative in {elapsed_ms}ms "
                    f"({len(narrative)} chars)"
                )
                return narrative, "ollama"

            except Exception as e:
                logger.warning(
                    f"Ollama failed ({type(e).__name__}: {e}), "
                    f"falling back to Gemini cloud"
                )
                self.circuit_breaker.record_failure(self.stats)
                # Fall through to cloud with fallback tag
                classification = "cloud_fallback"

        # ── Route: CLOUD (Gemini) ─────────────────────────────────
        provider = "gemini_fallback" if classification == "cloud_fallback" else "gemini"

        try:
            gemini_key = os.getenv("GEMINI_API_KEY")
            if not gemini_key:
                fallback_msg = (
                    "GEMINI_API_KEY not found. Native Audit fallback generated:\n"
                    f"CFO Math Engine passed. Fragility Index: "
                    f"{math_result.fragility_index}"
                )
                elapsed_ms = round((time.time() - start_time) * 1000, 1)
                self.stats.record(provider, elapsed_ms)
                return fallback_msg, "no_key_fallback"

            from google import genai
            client = genai.Client(api_key=gemini_key)

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=math_json,
                config=genai.types.GenerateContentConfig(
                    system_instruction=CLOUD_SYSTEM_PROMPT
                )
            )
            narrative = response.text.strip()

            elapsed_ms = round((time.time() - start_time) * 1000, 1)
            self.stats.record(provider, elapsed_ms)
            logger.info(
                f"Gemini generated narrative in {elapsed_ms}ms "
                f"({len(narrative)} chars) [provider={provider}]"
            )
            return narrative, provider

        except Exception as e:
            elapsed_ms = round((time.time() - start_time) * 1000, 1)
            self.stats.record(provider, elapsed_ms)
            error_msg = f"LLM Generation Failed (Math verified). Reason: {str(e)}"
            logger.error(error_msg)
            return error_msg, "error"

    async def get_status(self) -> dict:
        """Full status report for the /api/llm/status endpoint."""
        ollama_health = await self.ollama.health_status()
        return {
            **ollama_health,
            "cloud_provider": "gemini-2.5-flash",
            "routing_threshold": self.threshold,
            "circuit_breaker": self.circuit_breaker.to_dict(),
            "telemetry_persistent": True,
            "telemetry_file": str(TELEMETRY_FILE),
            **self.stats.to_dict(),
        }
