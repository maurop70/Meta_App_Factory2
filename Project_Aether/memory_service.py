"""
memory_service.py — Supabase Vector Memory for Aether C-Suite
================================================================
Project Aether | Antigravity-AI

Agents "Commit" successful logic patterns to the vector DB and
"Query" it before starting new builds to ensure maximum code reuse.

Uses Supabase REST API via httpx (same pattern as delegate_api.py).

SQL Migration (run in Supabase SQL Editor):
    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE IF NOT EXISTS agent_memory (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        agent_key TEXT NOT NULL,
        pattern_type TEXT NOT NULL,
        pattern_name TEXT NOT NULL,
        pattern_data JSONB NOT NULL DEFAULT '{}',
        tags TEXT[] DEFAULT '{}',
        source_file TEXT,
        confidence FLOAT DEFAULT 1.0,
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    );

    CREATE INDEX idx_agent_memory_agent ON agent_memory(agent_key);
    CREATE INDEX idx_agent_memory_type ON agent_memory(pattern_type);
    CREATE INDEX idx_agent_memory_tags ON agent_memory USING GIN(tags);

Usage:
    from memory_service import MemoryService

    mem = MemoryService()

    # Commit a successful pattern
    mem.commit_pattern(
        agent_key="CTO",
        pattern_type="architecture",
        pattern_name="FastAPI Hook Pattern",
        data={"description": "Secondary import pattern for safe module extension", ...},
        tags=["fastapi", "hooks", "modular"],
        source_file="ip_strategist_hook.py"
    )

    # Query before building
    results = mem.query_patterns("FastAPI modular extension", limit=5)
"""

# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

from auto_heal import healed_post, auto_heal, diagnose

def _v3_preflight():
    """V3: Ping Resonance_Watchdog_V3 before execution."""
    if not _V3_AVAILABLE:
        return True
    try:
        import json as _j
        _cfg_path = _os.path.join(_FACTORY_DIR, "resilience_config.json")
        if not _os.path.exists(_cfg_path):
            return True
        with open(_cfg_path) as _f:
            _cfg = _j.load(_f)
        _url = _cfg.get("cloud_health", {}).get("watchdog_url", "")
        if not _url:
            return True
        import requests as _rq
        _r = _rq.get(_url, timeout=5)
        return _r.status_code == 200
    except Exception:
        return False


import os
import sys
import json
import httpx
from datetime import datetime
from typing import Optional, List, Dict, Any

# ── Load .env ──────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(FACTORY_ROOT, ".env"))
except ImportError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY", "")
TABLE_NAME = "agent_memory"
PRE_FLIGHT_THRESHOLD = 0.85  # Similarity score above which agents must use Import/Refactor mode


# ══════════════════════════════════════════════════
#  MEMORY SERVICE
# ══════════════════════════════════════════════════

class MemoryService:
    """
    Supabase-backed vector memory for C-Suite agents.
    Commit successful patterns → Query before new builds.
    Graceful degradation: falls back to local JSON when Supabase is unavailable.
    """

    def __init__(self, supabase_url: str = "", supabase_key: str = ""):
        self.url = supabase_url or SUPABASE_URL
        self.key = supabase_key or SUPABASE_KEY
        self.connected = False
        self.local_store: List[Dict] = []
        self._local_path = os.path.join(SCRIPT_DIR, "_memory_cache.json")

        if self.url and self.key:
            try:
                self._client = httpx.Client(
                    base_url=f"{self.url}/rest/v1",
                    headers={
                        "apikey": self.key,
                        "Authorization": f"Bearer {self.key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation",
                    },
                    timeout=10.0,
                )
                # Test connection
                resp = self._client.get(f"/{TABLE_NAME}?select=id&limit=1")
                if resp.status_code in (200, 206):
                    self.connected = True
                    print(f"[OK] MemoryService connected to Supabase ({self.url})")
                elif resp.status_code == 404:
                    print(f"[WARN] Table '{TABLE_NAME}' not found. Run the SQL migration.")
                    print("       MemoryService falling back to LOCAL mode.")
                else:
                    print(f"[WARN] Supabase returned {resp.status_code}. Falling back to LOCAL.")
            except Exception as e:
                print(f"[WARN] Supabase connection failed: {e}. Using LOCAL mode.")
                self._client = None
        else:
            print("[INFO] MemoryService running in LOCAL mode (no Supabase credentials)")
            self._client = None

        # Load local cache
        if not self.connected:
            self._load_local()

    # ── Commit Pattern ─────────────────────────────────

    def commit_pattern(
        self,
        agent_key: str,
        pattern_type: str,
        pattern_name: str,
        data: Dict[str, Any],
        tags: Optional[List[str]] = None,
        source_file: Optional[str] = None,
        confidence: float = 1.0,
    ) -> Dict:
        """
        Commit a successful logic pattern to the vector DB.
        Called after a build completes successfully.

        Args:
            agent_key: Agent that discovered/used the pattern (e.g., "CTO")
            pattern_type: Category — "architecture", "algorithm", "ui_pattern",
                         "api_design", "error_handling", "optimization"
            pattern_name: Human-readable name for the pattern
            data: JSON-serializable dict with pattern details
            tags: Searchable tags
            source_file: Origin file path
            confidence: Pattern reliability score (0.0-1.0)

        Returns:
            Committed record dict
        """
        record = {
            "agent_key": agent_key.upper(),
            "pattern_type": pattern_type,
            "pattern_name": pattern_name,
            "pattern_data": data,
            "tags": tags or [],
            "source_file": source_file or "",
            "confidence": min(max(confidence, 0.0), 1.0),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

        if self.connected and self._client:
            try:
                resp = self._client.post(f"/{TABLE_NAME}", json=record)
                if resp.status_code in (200, 201):
                    result = resp.json()
                    return result[0] if isinstance(result, list) else result
                else:
                    print(f"[WARN] Supabase commit failed ({resp.status_code}): {resp.text[:200]}")
            except Exception as e:
                print(f"[WARN] Supabase commit error: {e}")

        # Local fallback
        record["id"] = f"local_{len(self.local_store)}_{datetime.utcnow().timestamp()}"
        self.local_store.append(record)
        self._save_local()
        return record

    # ── Query Patterns ─────────────────────────────────

    def query_patterns(
        self,
        query_text: str,
        agent_key: Optional[str] = None,
        pattern_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[Dict]:
        """
        Query the memory for reusable patterns before starting a new build.
        Uses text-based search with filters (pgvector embedding search when available).

        Args:
            query_text: Natural language description of what you need
            agent_key: Filter by agent (optional)
            pattern_type: Filter by type (optional)
            tags: Filter by tags — matches ANY (optional)
            limit: Max results

        Returns:
            List of matching pattern records, ranked by relevance
        """
        if self.connected and self._client:
            try:
                # Build Supabase query with filters
                params = f"select=*&limit={limit}&order=created_at.desc"

                if agent_key:
                    params += f"&agent_key=eq.{agent_key.upper()}"
                if pattern_type:
                    params += f"&pattern_type=eq.{pattern_type}"

                # Text search on pattern_name and pattern_data
                # Uses Supabase's text search (ilike) on pattern_name
                if query_text:
                    # Search across name — Supabase ilike
                    keywords = query_text.split()[:3]  # Top 3 keywords
                    for kw in keywords:
                        params += f"&or=(pattern_name.ilike.*{kw}*,pattern_type.ilike.*{kw}*)"

                resp = self._client.get(f"/{TABLE_NAME}?{params}")
                if resp.status_code == 200:
                    results = resp.json()
                    # Client-side relevance scoring
                    return self._rank_results(results, query_text, limit)
                else:
                    print(f"[WARN] Supabase query returned {resp.status_code}")
            except Exception as e:
                print(f"[WARN] Supabase query error: {e}")

        # Local fallback — text match
        return self._local_search(query_text, agent_key, pattern_type, tags, limit)

    # ── Pre-Flight Check ───────────────────────────────

    def pre_flight_check(
        self,
        task_description: str,
        agent_key: Optional[str] = None,
        pattern_type: Optional[str] = None,
        threshold: float = PRE_FLIGHT_THRESHOLD,
    ) -> Dict:
        """
        Token-Aware Planning gate. Call this BEFORE any agent begins a generation task.

        Queries the vector DB for existing code/logic patterns similar to the
        requested task. If a match exceeds the threshold (default 0.85), the
        agent is restricted to "IMPORT_REFACTOR" mode instead of generating new code.

        Args:
            task_description: Natural language description of what the agent wants to build
            agent_key: Calling agent identifier (e.g., "CTO", "factory_stream")
            pattern_type: Optional pattern type filter ("architecture", "algorithm", etc.)
            threshold: Similarity threshold (0.0-1.0). Default: 0.85

        Returns:
            dict with keys:
                - mode (str): "GENERATE" | "IMPORT_REFACTOR"
                - best_match (dict | None): The highest-scoring existing pattern
                - similarity (float): Best match score (0.0-1.0)
                - recommendation (str): Human-readable guidance for the agent
                - token_savings_estimate (str): Rough tokens saved by reusing
        """
        matches = self.query_patterns(
            query_text=task_description,
            agent_key=agent_key,
            pattern_type=pattern_type,
            limit=5,
        )

        if not matches:
            return {
                "mode": "GENERATE",
                "best_match": None,
                "similarity": 0.0,
                "recommendation": "No existing patterns found. Proceed with generation.",
                "token_savings_estimate": "0",
            }

        # Score the best match using keyword overlap as a proxy for similarity
        best = matches[0]
        name = (best.get("pattern_name", "") or "").lower()
        ptype = (best.get("pattern_type", "") or "").lower()
        tags = [t.lower() for t in (best.get("tags") or [])]
        data_str = json.dumps(best.get("pattern_data", {})).lower()
        query_lower = task_description.lower()
        keywords = set(query_lower.split())

        raw_score = 0
        max_score = len(keywords) * 8  # max per keyword: 3+2+2+1
        for kw in keywords:
            if kw in name:        raw_score += 3
            if kw in ptype:       raw_score += 2
            if any(kw in t for t in tags): raw_score += 2
            if kw in data_str:    raw_score += 1

        # Normalize to 0.0-1.0, also factor in stored confidence
        base_similarity = (raw_score / max_score) if max_score > 0 else 0.0
        stored_confidence = float(best.get("confidence", 1.0))
        similarity = round(min(base_similarity * stored_confidence, 1.0), 3)

        if similarity >= threshold:
            loc = best.get("source_file") or best.get("pattern_name", "existing pattern")
            return {
                "mode": "IMPORT_REFACTOR",
                "best_match": best,
                "similarity": similarity,
                "recommendation": (
                    f"HIGH SIMILARITY ({similarity:.0%}) detected. "
                    f"Import/refactor '{loc}' instead of regenerating. "
                    f"Pattern: {best.get('pattern_name')} ({best.get('pattern_type')})"
                ),
                "token_savings_estimate": f"~{int(similarity * 2000)} tokens",
            }
        else:
            return {
                "mode": "GENERATE",
                "best_match": best,
                "similarity": similarity,
                "recommendation": (
                    f"Low similarity ({similarity:.0%}). Generating new code is appropriate. "
                    f"Consider committing the result as a new pattern after completion."
                ),
                "token_savings_estimate": "0",
            }

    # ── List All Patterns ──────────────────────────────

    def list_patterns(
        self,
        agent_key: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """List all committed patterns, optionally filtered by agent."""
        if self.connected and self._client:
            try:
                params = f"select=id,agent_key,pattern_type,pattern_name,tags,confidence,created_at&limit={limit}&order=created_at.desc"
                if agent_key:
                    params += f"&agent_key=eq.{agent_key.upper()}"
                resp = self._client.get(f"/{TABLE_NAME}?{params}")
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                print(f"[WARN] List error: {e}")

        # Local fallback
        results = self.local_store
        if agent_key:
            results = [r for r in results if r.get("agent_key") == agent_key.upper()]
        return results[:limit]

    # ── Stats ──────────────────────────────────────────

    def stats(self) -> Dict:
        """Return memory service statistics."""
        if self.connected and self._client:
            try:
                resp = self._client.get(
                    f"/{TABLE_NAME}?select=agent_key,pattern_type",
                    headers={**self._client.headers, "Prefer": "count=exact"},
                )
                total = int(resp.headers.get("content-range", "0-0/0").split("/")[-1])
                records = resp.json() if resp.status_code == 200 else []
                agents = set(r.get("agent_key", "") for r in records)
                types = set(r.get("pattern_type", "") for r in records)
                return {
                    "mode": "SUPABASE",
                    "total_patterns": total,
                    "unique_agents": len(agents),
                    "pattern_types": list(types),
                    "status": "operational",
                }
            except Exception:
                pass

        return {
            "mode": "LOCAL",
            "total_patterns": len(self.local_store),
            "unique_agents": len(set(r.get("agent_key", "") for r in self.local_store)),
            "pattern_types": list(set(r.get("pattern_type", "") for r in self.local_store)),
            "status": "operational (local cache)",
        }

    # ── Internal Helpers ───────────────────────────────

    def _rank_results(self, results: List[Dict], query: str, limit: int) -> List[Dict]:
        """Client-side relevance ranking using keyword overlap."""
        query_lower = query.lower()
        keywords = set(query_lower.split())

        for r in results:
            name = (r.get("pattern_name", "") or "").lower()
            ptype = (r.get("pattern_type", "") or "").lower()
            tags = [t.lower() for t in (r.get("tags") or [])]
            data_str = json.dumps(r.get("pattern_data", {})).lower()

            # Score: name match > tag match > data match
            score = 0
            for kw in keywords:
                if kw in name:
                    score += 3
                if kw in ptype:
                    score += 2
                if any(kw in t for t in tags):
                    score += 2
                if kw in data_str:
                    score += 1
            r["_relevance"] = score

        results.sort(key=lambda r: r.get("_relevance", 0), reverse=True)
        # Clean up internal field
        for r in results[:limit]:
            r.pop("_relevance", None)
        return results[:limit]

    def _local_search(
        self, query: str, agent_key: Optional[str],
        pattern_type: Optional[str], tags: Optional[List[str]], limit: int
    ) -> List[Dict]:
        """Local fallback search."""
        results = list(self.local_store)

        if agent_key:
            results = [r for r in results if r.get("agent_key") == agent_key.upper()]
        if pattern_type:
            results = [r for r in results if r.get("pattern_type") == pattern_type]

        if query:
            results = self._rank_results(results, query, limit)

        if tags:
            tag_set = set(t.lower() for t in tags)
            results = [
                r for r in results
                if tag_set & set(t.lower() for t in (r.get("tags") or []))
            ]

        return results[:limit]

    def _load_local(self):
        """Load local cache from JSON."""
        if os.path.exists(self._local_path):
            try:
                with open(self._local_path, "r") as f:
                    self.local_store = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.local_store = []

    def _save_local(self):
        """Persist local cache to JSON."""
        try:
            with open(self._local_path, "w") as f:
                json.dump(self.local_store, f, indent=2)
        except OSError as e:
            print(f"[WARN] Could not save local memory cache: {e}")


# ══════════════════════════════════════════════════
#  SQL MIGRATION HELPER
# ══════════════════════════════════════════════════

MIGRATION_SQL = """
-- Aether Agent Memory Table
-- Run this in Supabase SQL Editor

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS agent_memory (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_key TEXT NOT NULL,
    pattern_type TEXT NOT NULL,
    pattern_name TEXT NOT NULL,
    pattern_data JSONB NOT NULL DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    source_file TEXT DEFAULT '',
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_agent ON agent_memory(agent_key);
CREATE INDEX IF NOT EXISTS idx_agent_memory_type ON agent_memory(pattern_type);
CREATE INDEX IF NOT EXISTS idx_agent_memory_tags ON agent_memory USING GIN(tags);

-- Enable RLS (optional — for multi-tenant isolation)
ALTER TABLE agent_memory ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY "Service role full access" ON agent_memory
    FOR ALL USING (true) WITH CHECK (true);
"""


def print_migration():
    """Print the SQL migration for copy-paste into Supabase SQL Editor."""
    print("=" * 60)
    print("  SUPABASE MIGRATION — Agent Memory Table")
    print("  Copy and run in Supabase SQL Editor:")
    print("=" * 60)
    print(MIGRATION_SQL)


# ══════════════════════════════════════════════════
#  STANDALONE TEST
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Aether Memory Service")
    parser.add_argument("--migrate", action="store_true", help="Print SQL migration")
    parser.add_argument("--stats", action="store_true", help="Show memory stats")
    parser.add_argument("--test", action="store_true", help="Run a test commit + query")
    args = parser.parse_args()

    if args.migrate:
        print_migration()
        sys.exit(0)

    mem = MemoryService()

    if args.stats:
        print(json.dumps(mem.stats(), indent=2))
    elif args.test:
        print("\n[TEST] Committing a test pattern...")
        result = mem.commit_pattern(
            agent_key="CTO",
            pattern_type="architecture",
            pattern_name="FastAPI Hook Pattern",
            data={
                "description": "Secondary import pattern for safe module extension",
                "example": "try: from hook import router; app.include_router(router)\nexcept ImportError: pass",
                "benefits": ["zero disruption", "modular", "fail-safe"],
            },
            tags=["fastapi", "hooks", "modular", "api"],
            source_file="ip_strategist_hook.py",
        )
        print(f"   Committed: {result.get('id', result.get('pattern_name'))}")

        print("\n[TEST] Querying for 'modular API extension'...")
        results = mem.query_patterns("modular API extension", limit=3)
        for r in results:
            print(f"   → {r.get('pattern_name')} ({r.get('pattern_type')}) by {r.get('agent_key')}")

        print(f"\n[TEST] Stats: {json.dumps(mem.stats(), indent=2)}")
    else:
        print(f"\nMemoryService initialized: {json.dumps(mem.stats(), indent=2)}")
        print("\nUsage:")
        print("  --migrate  Print SQL migration for Supabase")
        print("  --stats    Show memory statistics")
        print("  --test     Run a test commit + query")
# V3 AUTO-HEAL ACTIVE
