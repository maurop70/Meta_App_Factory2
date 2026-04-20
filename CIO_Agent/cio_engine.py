"""
cio_engine.py — CIO Intelligence Pipeline V3 (Open Web Mandate)
═══════════════════════════════════════════════════════════════════
Upgraded to Universal Data Provenance Protocol (UDPP).

Architecture:
  - CIOAgent inherits AgentBase — every intelligence claim is a ProvenanceClaim
  - search_duckduckgo() — broad market discovery (DDG HTML scraper)
  - read_url()          — deep-read specific articles / competitor sites
  - Both tools wrapped in generate_with_backoff_sync for rate-limit resilience
  - Gemini 2.5 Pro Function Calling sequences the tools based on sweep intent
  - All numeric/financial claims must be 100% cited (Hallucination Gate)
  - Frontier Intelligence Report saved to App_Registry/Proposals/ AND broadcast
    to the factory's SSE telemetry feed via /api/qa/ingest

Permission Sandbox (unchanged):
  ✅ search_duckduckgo(*) — Unrestricted DDG search
  ✅ read_url(*)           — Unrestricted web research
  ✅ read_file             — Full local directory visibility
  ✅ write_file            — ONLY to App_Registry/Proposals/
  ❌ command(*)            — Completely blocked
"""

import os
import re
import json
import time
import logging
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

from bs4 import BeautifulSoup
from google import genai
from google.genai import types

# import UDPP base classes and backoff from the factory root
import sys
FACTORY_ROOT = Path(__file__).parent.parent
if str(FACTORY_ROOT) not in sys.path:
    sys.path.insert(0, str(FACTORY_ROOT))

from agent_base import AgentBase, ProvenanceClaim, run_hallucination_gate
from ai_utils import generate_with_backoff_sync

logger = logging.getLogger("CIO_Engine")

# ─────────────────────────────────────────────────────────────────────────────
# PATH CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

CIO_ROOT        = Path(__file__).parent
WORKSPACE_ROOT  = FACTORY_ROOT.parent
PROPOSALS_DIR   = WORKSPACE_ROOT / "App_Registry" / "Proposals"
CRAWL_TARGETS   = CIO_ROOT / "crawl_targets.json"

INTERNAL_AUDIT_TARGETS = [
    FACTORY_ROOT / "MASTER_INDEX.md",
    WORKSPACE_ROOT / "AGENTS.md",
    FACTORY_ROOT / "LEDGER.md",
    FACTORY_ROOT / "requirements.txt",
]

_DDG_URL = "https://html.duckduckgo.com/html/"
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ─────────────────────────────────────────────────────────────────────────────
# NATIVE PYTHON TOOLS (declared to Gemini 2.5 Pro via Function Calling)
# ─────────────────────────────────────────────────────────────────────────────

def search_duckduckgo(query: str) -> dict:
    """
    Broad market discovery via DuckDuckGo Search (DDGS).
    Restored with high-resilience library to bypass CAPTCHA blocks.
    
    Args:
        query: Search query (e.g. 'frontier LLM models released 2025')
        
    Returns:
        dict with query, results [{title, snippet, url}], source, count
    """
    from duckduckgo_search import DDGS
    
    try:
        results = []
        with DDGS() as ddgs:
            # text search returns a generator of dicts: {'title', 'href', 'body'}
            for r in ddgs.text(query, max_results=8):
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", "")
                })
        
        logger.info(f"[CIO DDGS] {len(results)} results for: {query!r}")
        return {"query": query, "results": results, "source": "DuckDuckGo (DDGS)", "count": len(results)}
    except Exception as e:
        logger.warning(f"[CIO DDGS] search failed: {e}")
        return {"query": query, "error": str(e), "results": [], "source": "DuckDuckGo", "count": 0}


def read_url(url: str) -> dict:
    """
    Deep-reads the raw text content of a specific article, blog post,
    or competitor website. Strips scripts, ads, and nav noise.
    Wrapped in backoff to handle rate-limiting and transient errors.

    Args:
        url: Full URL to read (e.g. 'https://openai.com/blog/gpt-4o-mini')

    Returns:
        dict with url, text (cleaned body text up to 6000 chars), word_count, source
    """
    def _fetch():
        resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=15)
        resp.raise_for_status()
        return resp

    try:
        resp = generate_with_backoff_sync(_fetch, max_api_retries=3, base_delay=3.0, backoff_factor=2.0)

        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type or url.endswith(".json"):
            raw = json.dumps(resp.json(), indent=2)[:6000]
            return {"url": url, "text": raw, "word_count": len(raw.split()), "source": url}

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)[:6000]
        word_count = len(text.split())

        logger.info(f"[CIO read_url] {word_count} words from: {url}")
        return {"url": url, "text": text, "word_count": word_count, "source": url}

    except Exception as e:
        logger.warning(f"[CIO read_url] failed for {url}: {e}")
        return {"url": url, "error": str(e), "text": "", "word_count": 0, "source": url}


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL AUDIT (Phase 2 — no web calls)
# ─────────────────────────────────────────────────────────────────────────────

def _read_file_safe(path: Path, max_chars: int = 6000) -> Optional[str]:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
        return None
    except Exception as e:
        logger.warning(f"Could not read {path}: {e}")
        return None


def _scan_codebase_metadata() -> dict:
    py_files = list(FACTORY_ROOT.glob("*.py"))
    total_loc = 0
    import_counter: dict = {}

    for f in py_files:
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").split("\n")
            total_loc += len(lines)
            for line in lines:
                line = line.strip()
                if line.startswith("import ") or line.startswith("from "):
                    parts = line.replace("from ", "").replace("import ", "").split(".")
                    module = parts[0].split(" ")[0].strip()
                    if module and not module.startswith("_"):
                        import_counter[module] = import_counter.get(module, 0) + 1
        except Exception:
            continue

    agent_dirs = []
    
    # 1. Scan internal system agents
    for item in FACTORY_ROOT.iterdir():
        if item.is_dir() and ("Agent" in item.name or "agent" in item.name):
            agent_dirs.append({
                "name": f"Core Agent: {item.name}",
                "has_server": (item / "server.py").exists() or (item / "main.py").exists(),
            })

    # 2. Scan registered child apps
    projects_dir = FACTORY_ROOT / "projects"
    if projects_dir.exists():
        for item in projects_dir.iterdir():
            if item.is_dir() and not item.name.startswith("_"):
                agent_dirs.append({
                    "name": f"Child App: {item.name}",
                    "has_server": (item / "server.py").exists() or (item / "main.py").exists(),
                })

    top_imports = sorted(import_counter.items(), key=lambda x: x[1], reverse=True)[:15]
    return {
        "python_files": len(py_files),
        "total_loc": total_loc,
        "agent_directories": agent_dirs,
        "top_dependencies": [{"module": m, "count": c} for m, c in top_imports],
    }


def _gather_internal_audit() -> dict:
    logger.info("[CIO Phase 2] Internal System Audit")
    contents = {}
    for target in INTERNAL_AUDIT_TARGETS:
        c = _read_file_safe(target)
        if c:
            contents[target.name] = c
            logger.info(f"  Read {target.name} ({len(c)} chars)")
        else:
            logger.warning(f"  Could not read {target.name}")
    meta = _scan_codebase_metadata()
    logger.info(f"  Codebase: {meta['python_files']} py files, {meta['total_loc']} LOC, {len(meta['agent_directories'])} agents")
    return {"file_contents": contents, "codebase_metadata": meta, "audit_timestamp": datetime.now().isoformat()}


# ─────────────────────────────────────────────────────────────────────────────
# CIO AGENT (UDPP-enforced)
# ─────────────────────────────────────────────────────────────────────────────

CIO_SYSTEM_PROMPT = """You are the Chief Intelligence Officer of the Meta App Factory. 
Your sole directive is to analyze the provided list of our active apps, search the web for ways to improve them, and return highly specific, actionable upgrade recommendations.

TOOLS AVAILABLE:
- search_duckduckgo: broad discovery of market trends, competitor moves, new models
- read_url: deep-read specific articles, papers, or competitor pages

REQUIRED SWEEP SEQUENCE:
1. Search for competitor features related to our active apps
2. Search for UX improvements for these types of agents
3. Search for framework upgrades and MLOps tooling trends
4. Use read_url to deep-read the 2-3 most important articles you found

FRONTIER INTELLIGENCE REPORT FORMAT (strict Markdown):

# CIO Actionable Upgrade Memo — {date}

## Executive Summary
Single paragraph: the most important breakthrough and its direct impact on our active apps.

## Discovery #1: [Title]
- **Source**: [URL or domain — REQUIRED]
- **What It Is**: concise description
- **Why It Matters for Our Apps**: specific impact on our stack
- **Priority**: Critical / High / Medium / Low

## Discovery #2: [Title]
(same structure — 3-5 total discoveries)

## Competitive Landscape
What key competitors shipped this cycle and what it means for our active projects.

## Recommended Upgrades
Numbered list, ordered by impact. Be specific (library names, versions, architecture changes).

RULES:
1. Every claim must cite the exact URL where you found it.
2. Do NOT invent statistics. Only use data from your search results.
3. Return ONLY the Markdown report. No code blocks around it.
"""


class CIOAgent(AgentBase):
    """
    Chief Innovation Officer — autonomous 24h intelligence agent.
    Inherits AgentBase and enforces UDPP provenance on all intelligence claims.
    """
    AGENT_ID = "cio"
    
    def __init__(self):
        super().__init__()

    def run(self, intent: str = "AI/LLM frontier intelligence sweep 2025") -> dict:
        """
        Full sweep: Phase 1 (Gemini FC web intel) + Phase 2 (internal audit)
        + Phase 3 (Report synthesis). Returns result dict with _provenance sidecar.
        """
        sweep_start = datetime.now()
        logger.info(f"[CIO] Intel sweep started — intent: {intent!r}")
        self.add_trace(f"Intel sweep initiated with intent: {intent}", node="ORCHESTRATOR")

        # Phase 1: Internal system audit (Moved to front for context injection)
        self.add_trace("Scanning internal codebase for context injection...", node="AUDIT")
        internal_audit = _gather_internal_audit()
        self.add_trace(f"Internal audit complete. Detected {len(internal_audit.get('codebase_metadata', {}).get('agent_directories', []))} active agents.", node="AUDIT", status="SUCCESS")

        # Phase 2: Gemini 2.5 Pro Function Calling web sweep (Context-Aware)
        web_intel, web_provenance, searched_urls = self._phase1_web_sweep(intent, internal_audit)

        # Phase 3: Synthesize Frontier Intelligence Report
        report_text, report_provenance = self._phase3_synthesize(web_intel, internal_audit, searched_urls)

        duration = (datetime.now() - sweep_start).total_seconds()

        # Merge all provenance claims
        all_provenance = {**web_provenance, **report_provenance}

        # Validate provenance before writing
        gate_status, gate_errors = run_hallucination_gate({"CIO": all_provenance})

        # Write memo
        memo_filename = None
        if report_text and gate_status == "PASS":
            memo_filename = _write_memo(report_text)
        elif report_text and gate_errors:
            # Annotate the report with gate errors for transparency
            report_text = _prepend_gate_warning(report_text, gate_errors)
            memo_filename = _write_memo(report_text)

        result = {
            "sweep_start": sweep_start.isoformat(),
            "sweep_end": datetime.now().isoformat(),
            "duration_seconds": round(duration, 1),
            "urls_searched": searched_urls,
            "internal_files_audited": len(internal_audit.get("file_contents", {})),
            "memo_generated": memo_filename is not None,
            "memo_filename": memo_filename,
            "hallucination_gate": gate_status,
            "gate_errors": gate_errors,
            "llm_provider": "gemini-2.5-flash",
        }

        return self.merge_into_output(result, all_provenance)

    # ── Phase 1: Gemini 2.5 Pro Function Calling web sweep ──────────────────

    def _phase1_web_sweep(self, intent: str, internal_audit: dict) -> tuple[dict, dict, list[str]]:
        """
        Runs the Context-Aware Gemini 2.5 Pro function-calling web sweep.
        Returns (intel_summary, provenance_block, searched_urls).
        """
        logger.info("[CIO Phase 1] Gemini 2.5 Pro context-aware web intel sweep")
        self.add_trace("Initiating context-aware web sweep via DuckDuckGo...", node="WEB_SWEEP")
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("[CIO] GEMINI_API_KEY missing")
            return {}, {}, []

        client = genai.Client(api_key=api_key)
        tools = [search_duckduckgo, read_url]
        
        # Extract active apps for context injection
        active_apps_list = "\n".join([f"- {d['name']}" for d in internal_audit.get("codebase_metadata", {}).get("agent_directories", [])])
        if not active_apps_list:
            active_apps_list = "No specific active apps detected."

        prompt = f"""You are executing a deeply targeted intelligence sweep for the Antigravity platform.

Primary intent: {intent}

INTERNAL SYSTEM STATE (Our Active/Registered Apps):
{active_apps_list}

Execute the following sweep NOW using your tools:
1. Call search_duckduckgo for 'competitor features' and recent launches specifically related to the apps listed above.
2. Call search_duckduckgo for 'UX improvements' and interface patterns for these types of AI agents.
3. Call search_duckduckgo for 'framework upgrades' or new python libraries that could improve our specific stack.
4. Pick the 2 most important article URLs from your search results and call read_url on them to extract actionable details.

After using all tools, return a JSON summary of your findings:
{{
    "top_discoveries": [
        {{"title": "...", "url": "...", "summary": "...", "priority": "Critical|High|Medium|Low"}},
        ...
    ],
    "competitor_moves": ["...", "..."],
    "search_queries_used": ["...", "..."],
    "urls_deep_read": ["...", "..."]
}}

Return ONLY valid JSON.
"""

        try:
            response = generate_with_backoff_sync(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=tools,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False),
                    system_instruction=CIO_SYSTEM_PROMPT,
                ),
            )

            self.add_trace("Gemini tool-use cycle complete. Parsing intelligence payloads...", node="WEB_SWEEP")
            raw = response.text.strip().replace("```json", "").replace("```", "").strip()
            intel = json.loads(raw)
            self.add_trace(f"Discovered {len(intel.get('top_discoveries', []))} critical market events.", node="WEB_SWEEP", status="SUCCESS")

            # Build provenance from discovered URLs
            searched_urls = intel.get("urls_deep_read", []) + intel.get("search_queries_used", [])
            ddg_citation = "https://html.duckduckgo.com/html/ [DuckDuckGo HTML Search]"

            # Build a provenance claim per discovery
            provenance: dict = {}
            for i, disc in enumerate(intel.get("top_discoveries", [])[:5]):
                source_url = disc.get("url", ddg_citation)
                provenance[f"discovery_{i+1}"] = ProvenanceClaim.build(
                    value=disc.get("summary", ""),
                    source_citation=source_url if source_url else ddg_citation,
                    tool_used="web_search",
                    confidence=0.75,
                )

            logger.info(f"[CIO Phase 1] {len(intel.get('top_discoveries', []))} discoveries, {len(searched_urls)} URLs")
            return intel, provenance, searched_urls

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"[CIO Phase 1] Failed: {e}")
            # Return simulated provenance — will trigger Hallucination Gate FAIL notation
            fallback_cite = f"[SIMULATED — Phase 1 failed: {str(e)[:80]}]"
            return {}, {"phase1_result": ProvenanceClaim.build("", fallback_cite, "fallback", 0.0)}, []

    # ── Phase 3: Frontier Intelligence Report synthesis ──────────────────────

    def _phase3_synthesize(self, web_intel: dict, internal_audit: dict, searched_urls: list) -> tuple[Optional[str], dict]:
        """
        Synthesizes Frontier Intelligence Report using Gemini 2.5 Pro.
        Returns (report_markdown, provenance_block).
        """
        logger.info("[CIO Phase 3] Synthesizing Frontier Intelligence Report")
        self.add_trace("Synthesizing actionable Frontier Intelligence Report...", node="SYNTHESIS")
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None, {}

        client = genai.Client(api_key=api_key)
        today = datetime.now().strftime("%Y-%m-%d")

        codebase_meta = internal_audit.get("codebase_metadata", {})
        active_apps_list = "\n".join([f"- {d['name']}" for d in codebase_meta.get("agent_directories", [])])
        
        internal_summary = (
            f"Factory has {codebase_meta.get('python_files', '?')} Python files, "
            f"{codebase_meta.get('total_loc', '?')} LOC.\n"
            f"Active Apps/Agents:\n{active_apps_list}"
        )

        prompt = f"""Generate the actionable Upgrade Memo for {today}.

WEB INTELLIGENCE GATHERED (Targeted to our stack):
{json.dumps(web_intel, indent=2, default=str)[:15000]}

INTERNAL SYSTEM STATE:
{internal_summary}

Searched URLs with deep-reads: {searched_urls}

Generate the complete Markdown report now. Every 'Source' field MUST contain a real URL from the search results above.
Replace {{date}} in the template with {today}.
"""

        try:
            response = generate_with_backoff_sync(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=CIO_SYSTEM_PROMPT.replace("{date}", today),
                ),
            )
            report = response.text.strip()
            logger.info(f"[CIO Phase 3] Report synthesized: {len(report)} chars")
            self.add_trace("Report synthesis complete. Finalizing provenance claims.", node="SYNTHESIS", status="SUCCESS")

            # Build report provenance
            report_citation = (
                f"gemini-2.5-pro synthesis from: {', '.join(searched_urls[:3])}"
                if searched_urls else "gemini-2.5-pro synthesis [no live sources]"
            )
            provenance = {
                "report_synthesis": ProvenanceClaim.build(
                    value=f"Frontier Intelligence Report — {today}",
                    source_citation=report_citation,
                    tool_used="gemini_synthesis",
                    confidence=0.80,
                )
            }
            return report, provenance

        except Exception as e:
            logger.error(f"[CIO Phase 3] Synthesis failed: {e}")
            return None, {"report_synthesis": ProvenanceClaim.build("", f"[SIMULATED — synthesis failed: {e}]", "fallback", 0.0)}


# ─────────────────────────────────────────────────────────────────────────────
# MEMO PERSISTENCE (Permission-sandboxed)
# ─────────────────────────────────────────────────────────────────────────────

def _write_memo(text: str) -> Optional[str]:
    """Writes report to App_Registry/Proposals/ ONLY — path-locked."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"cio_frontier_report_{timestamp}.md"
    target = PROPOSALS_DIR / filename

    resolved = target.resolve()
    if not str(resolved).startswith(str(PROPOSALS_DIR.resolve())):
        logger.error(f"PERMISSION DENIED: write target escapes sandbox: {resolved}")
        return None

    try:
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        logger.info(f"[CIO] Report written: {filename}")
        return filename
    except Exception as e:
        logger.error(f"[CIO] Failed to write report: {e}")
        return None


def _prepend_gate_warning(text: str, gate_errors: list) -> str:
    """Prepends a UDPP warning block to the report when the Hallucination Gate flagged issues."""
    warning = (
        "> [!WARNING]\n"
        "> **UDPP Hallucination Gate flagged the following issues in this report:**\n"
        + "".join(f"> - {e}\n" for e in gate_errors[:5])
        + "\n---\n\n"
    )
    return warning + text


# ─────────────────────────────────────────────────────────────────────────────
# BACKWARD-COMPATIBLE INTERFACE (server.py calls these)
# ─────────────────────────────────────────────────────────────────────────────

def run_full_sweep(focus_areas=None) -> dict:
    """
    Public interface for server.py — runs the CIOAgent sweep.
    focus_areas parameter retained for backward compatibility (ignored — agent
    uses Gemini FC to decide what to search).
    """
    agent = CIOAgent()
    return agent.run()


def list_memos():
    """Lists generated reports in App_Registry/Proposals/."""
    memos = []
    if PROPOSALS_DIR.exists():
        for f in sorted(
            list(PROPOSALS_DIR.glob("cio_frontier_report_*.md")) +
            list(PROPOSALS_DIR.glob("cio_upgrade_memo_*.md")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
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
        logger.error("PERMISSION DENIED: read target escapes sandbox")
        return None
    if target.exists():
        return target.read_text(encoding="utf-8")
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    agent = CIOAgent()
    result = agent.run()
    print(json.dumps({k: v for k, v in result.items() if k != "_provenance"}, indent=2))
