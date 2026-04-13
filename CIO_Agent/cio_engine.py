"""
cio_engine.py — CIO Intelligence Pipeline (V3 Architecture)
═══════════════════════════════════════════════════════════════
Three-phase intelligence engine:
  Phase 1: External Intelligence Gathering (web crawl)
  Phase 2: Internal System Audit (codebase scan)
  Phase 3: Upgrade Memo Synthesis (Gemini-powered)

Permission Sandbox:
  ✅ read_url(*)  — Unrestricted web research
  ✅ read_file    — Full local directory audit
  ✅ write_file   — ONLY to App_Registry/Proposals/
  ❌ command(*)   — Completely blocked (no subprocess/os.system)

Part of CIO_Agent — Port 5080 | Antigravity-AI
"""

import os
import json
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("CIO_Engine")

# ═══════════════════════════════════════════════════════════
#  PATH CONSTANTS
# ═══════════════════════════════════════════════════════════

CIO_ROOT = Path(__file__).parent
FACTORY_ROOT = CIO_ROOT.parent
WORKSPACE_ROOT = FACTORY_ROOT.parent
PROPOSALS_DIR = WORKSPACE_ROOT / "App_Registry" / "Proposals"
CRAWL_TARGETS_PATH = CIO_ROOT / "crawl_targets.json"

# Key internal files for audit
INTERNAL_AUDIT_TARGETS = [
    FACTORY_ROOT / "MASTER_INDEX.md",
    WORKSPACE_ROOT / "AGENTS.md",
    WORKSPACE_ROOT / "sync_manifest.json",
    FACTORY_ROOT / "LEDGER.md",
    FACTORY_ROOT / "requirements.txt",
    FACTORY_ROOT / "SOP_MAINTENANCE.md",
]


# ═══════════════════════════════════════════════════════════
#  PHASE 1: EXTERNAL INTELLIGENCE GATHERING
# ═══════════════════════════════════════════════════════════

def _load_crawl_targets() -> dict:
    """Loads the configurable crawl target manifest."""
    try:
        with open(CRAWL_TARGETS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load crawl_targets.json: {e}")
        return {"competitors": {"sources": []}, "ai_frontier": {"sources": []}, "tech_integrations": {"sources": []}, "settings": {}}


def _fetch_url(url: str, timeout: int = 10, max_chars: int = 5000) -> Optional[str]:
    """Fetches a URL and returns cleaned text content."""
    try:
        headers = {
            "User-Agent": "Antigravity-CIO-Agent/1.0 (Market Intelligence Bot)"
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")

        # JSON API responses (e.g., HackerNews)
        if "application/json" in content_type or url.endswith(".json"):
            data = resp.json()
            return json.dumps(data, indent=2)[:max_chars]

        # HTML → extract text
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script/style noise
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        # Collapse excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text[:max_chars]

    except requests.Timeout:
        logger.warning(f"Timeout fetching {url}")
        return None
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def _extract_relevant_snippets(text: str, keywords: List[str], max_snippets: int = 10) -> List[str]:
    """Extracts lines containing relevant keywords from crawled text."""
    if not text:
        return []

    snippets = []
    lines = text.split("\n")
    keyword_pattern = re.compile("|".join(re.escape(kw) for kw in keywords), re.IGNORECASE)

    for line in lines:
        if keyword_pattern.search(line) and len(line.strip()) > 20:
            snippets.append(line.strip()[:300])
            if len(snippets) >= max_snippets:
                break

    return snippets


def gather_external_intel() -> Dict[str, List[dict]]:
    """
    Phase 1: Crawl external sources for competitor analysis,
    AI frontier news, and tech/integration opportunities.
    """
    logger.info("═══ PHASE 1: External Intelligence Gathering ═══")
    targets = _load_crawl_targets()
    settings = targets.get("settings", {})
    timeout = settings.get("request_timeout_seconds", 10)
    max_chars = settings.get("max_content_chars_per_source", 5000)

    intel = {}

    for domain in ["competitors", "ai_frontier", "tech_integrations"]:
        domain_data = targets.get(domain, {})
        sources = domain_data.get("sources", [])
        domain_results = []

        for source in sources:
            name = source.get("name", "Unknown")
            url = source.get("url", "")
            keywords = source.get("keywords", [])

            logger.info(f"  Crawling: {name} ({url})")
            raw_text = _fetch_url(url, timeout=timeout, max_chars=max_chars)

            if raw_text:
                snippets = _extract_relevant_snippets(raw_text, keywords)
                domain_results.append({
                    "source": name,
                    "url": url,
                    "snippets_found": len(snippets),
                    "snippets": snippets,
                    "status": "success"
                })
                logger.info(f"    ✅ {len(snippets)} relevant snippets extracted")
            else:
                domain_results.append({
                    "source": name,
                    "url": url,
                    "snippets_found": 0,
                    "snippets": [],
                    "status": "failed"
                })
                logger.warning(f"    ❌ No content retrieved")

        intel[domain] = domain_results
        total = sum(r["snippets_found"] for r in domain_results)
        logger.info(f"  [{domain}] Total snippets: {total}")

    return intel


# ═══════════════════════════════════════════════════════════
#  PHASE 2: INTERNAL SYSTEM AUDIT
# ═══════════════════════════════════════════════════════════

def _read_file_safe(path: Path, max_chars: int = 8000) -> Optional[str]:
    """Reads a file safely, returning None on failure."""
    try:
        if path.exists():
            content = path.read_text(encoding="utf-8", errors="replace")
            return content[:max_chars]
        return None
    except Exception as e:
        logger.warning(f"Failed to read {path}: {e}")
        return None


def _scan_codebase_metadata() -> dict:
    """
    Scans the Meta_App_Factory codebase for structural metadata:
    - Python file count and total LOC
    - Detected agent directories
    - Import frequency analysis (top dependencies)
    """
    py_files = list(FACTORY_ROOT.glob("*.py"))
    total_loc = 0
    import_counter: Dict[str, int] = {}

    for py_file in py_files:
        try:
            lines = py_file.read_text(encoding="utf-8", errors="replace").split("\n")
            total_loc += len(lines)

            for line in lines:
                line = line.strip()
                if line.startswith("import ") or line.startswith("from "):
                    # Extract the base module
                    parts = line.replace("from ", "").replace("import ", "").split(".")
                    module = parts[0].split(" ")[0].strip()
                    if module and not module.startswith("_"):
                        import_counter[module] = import_counter.get(module, 0) + 1
        except Exception:
            continue

    # Detect agent directories
    agent_dirs = []
    for item in FACTORY_ROOT.iterdir():
        if item.is_dir() and ("Agent" in item.name or "agent" in item.name):
            has_server = (item / "server.py").exists() or (item / "main.py").exists()
            agent_dirs.append({"name": item.name, "has_server": has_server})

    # Top 15 imports
    top_imports = sorted(import_counter.items(), key=lambda x: x[1], reverse=True)[:15]

    return {
        "python_files_in_root": len(py_files),
        "total_lines_of_code": total_loc,
        "agent_directories": agent_dirs,
        "top_dependencies": [{"module": m, "occurrences": c} for m, c in top_imports],
    }


def audit_internal_architecture() -> dict:
    """
    Phase 2: Read internal architecture files and scan codebase
    to build a structured understanding of current system state.
    """
    logger.info("═══ PHASE 2: Internal System Audit ═══")

    # Read key files
    file_contents = {}
    for target in INTERNAL_AUDIT_TARGETS:
        name = target.name
        content = _read_file_safe(target)
        if content:
            file_contents[name] = content
            logger.info(f"  ✅ Read {name} ({len(content)} chars)")
        else:
            logger.warning(f"  ❌ Could not read {name}")

    # Scan codebase metadata
    codebase_meta = _scan_codebase_metadata()
    logger.info(f"  Codebase: {codebase_meta['python_files_in_root']} Python files, "
                f"{codebase_meta['total_lines_of_code']} LOC, "
                f"{len(codebase_meta['agent_directories'])} agent directories")

    return {
        "file_contents": file_contents,
        "codebase_metadata": codebase_meta,
        "audit_timestamp": datetime.now().isoformat(),
    }


# ═══════════════════════════════════════════════════════════
#  PHASE 3: UPGRADE MEMO SYNTHESIS
# ═══════════════════════════════════════════════════════════

CIO_SYSTEM_PROMPT = """You are the Antigravity CIO Agent — Chief Innovation Officer.
You are an aggressive, read-only strategic advisor. Your mission: identify the highest-impact upgrades for the Antigravity Meta App Factory ecosystem.

You have received two datasets:
1. EXTERNAL INTELLIGENCE — Crawled web data on competitors, AI frontier breakthroughs, and new tech/integrations.
2. INTERNAL SYSTEM AUDIT — Architecture files, codebase metadata, active agent inventory, and dependency analysis.

Generate an "Upgrade Memo" in Markdown format with the following strict structure:

# CIO Upgrade Memo — [Date]

## Executive Summary
One paragraph: the single most important finding and its potential impact.

## 🏆 Discovery #1: [Title]
- **Source**: Where you found it
- **What It Is**: Concise description
- **Why It Matters**: Rationale for implementation
- **Affected Apps**: Which Antigravity apps would benefit
- **Implementation Priority**: Critical / High / Medium / Low
- **Risk Assessment**: What could go wrong

## 🏆 Discovery #2: [Title]
(Same structure — repeat for 3-5 total discoveries)

## 🔍 Architecture Observations
Key findings from the internal audit — gaps, opportunities, technical debt.

## 📊 Competitive Landscape
Summary of what competitors are doing that we should watch or counter.

## ⚡ Recommended Next Steps
Numbered list of actionable items, ordered by impact.

RULES:
1. Be specific. Name exact tools, libraries, APIs with versions.
2. Tie every discovery back to a concrete Antigravity app or module.
3. Prioritize ruthlessly — the user has limited bandwidth.
4. Do NOT recommend changes that would break the permission sandbox.
5. Return ONLY the Markdown memo. No wrapping code blocks.
"""


def synthesize_memo(external_intel: dict, internal_audit: dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Phase 3: Feed both datasets to Gemini to produce the Upgrade Memo.
    Returns (memo markdown string, llm_provider) or (None, None) on failure.
    """
    logger.info("═══ PHASE 3: Upgrade Memo Synthesis ═══")

    try:
        from cio_router import CIORouter
        import asyncio

        # Build the data payload for Gemini
        data_payload = {
            "external_intelligence": {},
            "internal_audit": {
                "codebase_metadata": internal_audit.get("codebase_metadata", {}),
                "file_summaries": {}
            }
        }

        # Flatten external intel into digestible chunks
        for domain, results in external_intel.items():
            domain_snippets = []
            for result in results:
                if result["snippets"]:
                    domain_snippets.append({
                        "source": result["source"],
                        "findings": result["snippets"][:5]  # Top 5 per source
                    })
            data_payload["external_intelligence"][domain] = domain_snippets

        # Include truncated file summaries (avoid blowing context)
        for fname, content in internal_audit.get("file_contents", {}).items():
            data_payload["internal_audit"]["file_summaries"][fname] = content[:3000]

        prompt = f"""Based on the following intelligence data, generate the Upgrade Memo.

DATA:
{json.dumps(data_payload, indent=2, default=str)[:30000]}

Generate the memo now."""

        router = CIORouter()
        
        # Run async generation in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        memo_text, provider = loop.run_until_complete(
            router.generate(prompt=prompt, task_type="upgrade_memo", system_override=CIO_SYSTEM_PROMPT)
        )
        loop.close()

        if provider == "error" or not memo_text or len(memo_text) < 100:
            logger.error(f"Gemini returned an empty or too-short memo. Provider: {provider}")
            return None, provider

        logger.info(f"  ✅ Memo synthesized ({len(memo_text)} chars) via {provider}")
        return memo_text, provider

    except Exception as e:
        logger.error(f"Memo synthesis failed: {e}")
        return None, "error"


# ═══════════════════════════════════════════════════════════
#  WRITE MEMO (Permission-Sandboxed)
# ═══════════════════════════════════════════════════════════

def write_memo(memo_text: str) -> Optional[str]:
    """
    Writes the memo to App_Registry/Proposals/ ONLY.
    Returns the filename on success, None on failure.
    
    PERMISSION SANDBOX: This is the ONLY write operation in the
    entire CIO Agent. It is path-locked to App_Registry/Proposals/.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"cio_upgrade_memo_{timestamp}.md"
    target_path = PROPOSALS_DIR / filename

    # Strict path validation
    resolved = target_path.resolve()
    proposals_resolved = PROPOSALS_DIR.resolve()

    if not str(resolved).startswith(str(proposals_resolved)):
        logger.error(f"PERMISSION DENIED: Write target {resolved} escapes sandbox")
        return None

    try:
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
        target_path.write_text(memo_text, encoding="utf-8")
        logger.info(f"  ✅ Memo written: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Failed to write memo: {e}")
        return None


# ═══════════════════════════════════════════════════════════
#  ORCHESTRATOR — Full Intelligence Sweep
# ═══════════════════════════════════════════════════════════

def run_full_sweep(focus_areas: Optional[List[str]] = None) -> dict:
    """
    Executes the complete 3-phase CIO intelligence sweep.
    
    Args:
        focus_areas: Optional list of domains to focus on
                     ("competitors", "ai_frontier", "tech_integrations").
                     If None, sweep all domains.

    Returns:
        dict with sweep results and memo filename.
    """
    sweep_start = datetime.now()
    logger.info(f"╔══════════════════════════════════════════╗")
    logger.info(f"║  CIO INTELLIGENCE SWEEP — {sweep_start.strftime('%Y-%m-%d %H:%M')}  ║")
    logger.info(f"╚══════════════════════════════════════════╝")

    # Phase 1: External Intelligence
    external_intel = gather_external_intel()

    # Filter by focus areas if specified
    if focus_areas:
        external_intel = {k: v for k, v in external_intel.items() if k in focus_areas}

    # Phase 2: Internal Audit
    internal_audit = audit_internal_architecture()

    # Phase 3: Synthesize Memo
    memo_text, provider = synthesize_memo(external_intel, internal_audit)

    result = {
        "sweep_start": sweep_start.isoformat(),
        "sweep_end": datetime.now().isoformat(),
        "duration_seconds": (datetime.now() - sweep_start).total_seconds(),
        "external_sources_crawled": sum(len(v) for v in external_intel.values()),
        "external_snippets_total": sum(
            sum(r["snippets_found"] for r in results)
            for results in external_intel.values()
        ),
        "internal_files_audited": len(internal_audit.get("file_contents", {})),
        "memo_generated": memo_text is not None,
        "memo_filename": None,
        "llm_provider": provider,
    }

    if memo_text:
        filename = write_memo(memo_text)
        result["memo_filename"] = filename

    logger.info(f"Sweep complete in {result['duration_seconds']:.1f}s "
                f"| Sources: {result['external_sources_crawled']} "
                f"| Snippets: {result['external_snippets_total']} "
                f"| Memo: {'✅' if result['memo_generated'] else '❌'}")

    return result


def list_memos() -> List[dict]:
    """Lists all generated memos in App_Registry/Proposals/."""
    memos = []
    if PROPOSALS_DIR.exists():
        for f in sorted(PROPOSALS_DIR.glob("cio_upgrade_memo_*.md"), reverse=True):
            stat = f.stat()
            memos.append({
                "filename": f.name,
                "size_bytes": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            })
    return memos


def read_memo(filename: str) -> Optional[str]:
    """Reads a specific memo by filename. Path-sandboxed."""
    target = PROPOSALS_DIR / filename
    resolved = target.resolve()

    if not str(resolved).startswith(str(PROPOSALS_DIR.resolve())):
        logger.error(f"PERMISSION DENIED: Read target escapes sandbox")
        return None

    if target.exists():
        return target.read_text(encoding="utf-8")
    return None
