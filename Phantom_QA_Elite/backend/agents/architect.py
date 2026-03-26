"""
architect.py — The Architect (Test Planner Agent)
===================================================
Phantom QA Elite | Antigravity-AI

Scans target applications via OpenAPI spec, HTML structure, and
route patterns. Produces a structured Test Plan (JSON) that drives
the Ghost User and Skeptic agents.

Uses: Gemini 2.5 Flash (speed — this is a planning step)
"""

import os
import json
import time
import logging
import aiohttp
from typing import Optional

logger = logging.getLogger("Phantom.Architect")

# ── Gemini Client ────────────────────────────────────────
try:
    from google import genai
    _client = None

    def _get_client():
        global _client
        if _client is None:
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if api_key:
                _client = genai.Client(api_key=api_key)
        return _client
except ImportError:
    def _get_client():
        return None


# ══════════════════════════════════════════════════════════
#  DISCOVERY ENGINE
# ══════════════════════════════════════════════════════════

async def discover_endpoints(base_url: str, timeout: int = 10) -> dict:
    """
    Auto-discover app endpoints via OpenAPI spec and common probes.
    Returns structured endpoint inventory.
    """
    base_url = base_url.rstrip("/")
    discovery = {
        "base_url": base_url,
        "openapi_found": False,
        "endpoints": [],
        "health_endpoint": None,
        "has_frontend": False,
        "app_title": "",
        "technologies": [],
    }

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        # 1. Probe root
        try:
            async with session.get(base_url) as r:
                if r.status == 200:
                    content_type = r.headers.get("content-type", "")
                    body = await r.text()
                    if "text/html" in content_type:
                        discovery["has_frontend"] = True
                        # Extract title
                        import re
                        title_match = re.search(r"<title>(.*?)</title>", body, re.IGNORECASE)
                        if title_match:
                            discovery["app_title"] = title_match.group(1).strip()
        except Exception as e:
            logger.warning(f"Root probe failed: {e}")

        # 2. Probe health endpoints
        for path in ["/api/health", "/health", "/healthz", "/api/status"]:
            try:
                async with session.get(f"{base_url}{path}") as r:
                    if r.status == 200:
                        discovery["health_endpoint"] = path
                        try:
                            health_data = await r.json()
                            if "gemini" in str(health_data).lower():
                                discovery["technologies"].append("Gemini AI")
                            if "fastapi" in str(health_data).lower():
                                discovery["technologies"].append("FastAPI")
                        except Exception:
                            pass
                        break
            except Exception:
                continue

        # 3. OpenAPI spec discovery
        for spec_path in ["/openapi.json", "/api/openapi.json"]:
            try:
                async with session.get(f"{base_url}{spec_path}") as r:
                    if r.status == 200:
                        spec = await r.json()
                        discovery["openapi_found"] = True
                        discovery["app_title"] = discovery["app_title"] or spec.get("info", {}).get("title", "")

                        paths = spec.get("paths", {})
                        for path, methods in paths.items():
                            for method, details in methods.items():
                                if method.upper() in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                                    ep = {
                                        "method": method.upper(),
                                        "path": path,
                                        "summary": details.get("summary", ""),
                                        "description": details.get("description", ""),
                                        "has_request_body": "requestBody" in details,
                                        "parameters": [p.get("name", "") for p in details.get("parameters", [])],
                                    }
                                    discovery["endpoints"].append(ep)
                        break
            except Exception:
                continue

        # 4. Probe common API endpoints if no OpenAPI
        if not discovery["openapi_found"]:
            common_paths = [
                ("/api/dashboard", "GET"), ("/api/config", "GET"),
                ("/api/status", "GET"), ("/docs", "GET"),
            ]
            for path, method in common_paths:
                try:
                    async with session.get(f"{base_url}{path}") as r:
                        if r.status == 200:
                            discovery["endpoints"].append({
                                "method": method, "path": path,
                                "summary": f"Discovered via probe", "has_request_body": False,
                            })
                except Exception:
                    continue

    return discovery


# ══════════════════════════════════════════════════════════
#  AI TEST PLAN GENERATION
# ══════════════════════════════════════════════════════════

async def generate_test_plan(discovery: dict, app_description: str = "") -> dict:
    """
    Use Gemini to analyze the discovered endpoints and generate
    a comprehensive test plan for Ghost User and Skeptic agents.
    """
    client = _get_client()
    if not client:
        return _fallback_test_plan(discovery)

    ep_summary = "\n".join([
        f"  {ep['method']} {ep['path']} — {ep.get('summary', 'No description')}"
        f"{' [BODY]' if ep.get('has_request_body') else ''}"
        for ep in discovery["endpoints"]
    ]) or "  No endpoints discovered"

    prompt = f"""You are The Architect — the test planning agent for Phantom QA Elite.

Analyze this application and generate a comprehensive test plan.

APPLICATION CONTEXT:
- URL: {discovery['base_url']}
- Title: {discovery.get('app_title', 'Unknown')}
- Has Frontend: {discovery['has_frontend']}
- Health Endpoint: {discovery.get('health_endpoint', 'None')}
- Technologies: {', '.join(discovery.get('technologies', [])) or 'Unknown'}
- Description: {app_description or 'No description provided'}

DISCOVERED ENDPOINTS:
{ep_summary}

Generate a JSON test plan with this EXACT structure:
{{
    "app_profile": {{
        "type": "web_app|api_only|full_stack",
        "domain": "marketing|trading|education|general|etc",
        "risk_level": "HIGH|MEDIUM|LOW",
        "complexity": "HIGH|MEDIUM|LOW"
    }},
    "persona_recommendation": {{
        "name": "A name for the test persona",
        "role": "Their role/background",
        "behavior": "How they interact (fast clicker, methodical, impatient, etc)",
        "expertise": "tech-savvy|average|non-technical"
    }},
    "ui_tests": [
        {{
            "test_name": "Test name",
            "action": "What to do",
            "expected": "What should happen",
            "priority": "CRITICAL|HIGH|MEDIUM|LOW"
        }}
    ],
    "api_tests": [
        {{
            "method": "GET|POST",
            "path": "/api/example",
            "test_name": "Test name",
            "payload": null,
            "expected_status": 200,
            "priority": "CRITICAL|HIGH|MEDIUM|LOW"
        }}
    ],
    "edge_cases": [
        {{
            "test_name": "Edge case name",
            "method": "POST",
            "path": "/api/example",
            "payload": {{}},
            "expected_behavior": "Should return 400 with error message",
            "attack_type": "empty_body|malformed_json|oversized|injection|method_mismatch"
        }}
    ],
    "stress_tests": [
        {{
            "test_name": "Stress test name",
            "target": "/api/health",
            "concurrent_requests": 10,
            "expected": "All return 200 within 5s"
        }}
    ]
}}

Generate at least:
- 5 UI tests (if frontend exists)
- 1 API test per discovered endpoint
- 5 edge cases covering empty bodies, malformed JSON, method mismatch
- 2 stress tests

Return ONLY valid JSON. No markdown fences."""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "temperature": 0.3,
                "max_output_tokens": 4096,
                "response_mime_type": "application/json",
            }
        )
        text = response.text.strip()
        plan = json.loads(text)
        plan["_generated_by"] = "gemini-2.5-flash"
        plan["_discovery"] = discovery
        return plan
    except Exception as e:
        logger.error(f"AI test plan generation failed: {e}")
        return _fallback_test_plan(discovery)


def _fallback_test_plan(discovery: dict) -> dict:
    """Generate a basic test plan without AI."""
    plan = {
        "app_profile": {
            "type": "full_stack" if discovery["has_frontend"] else "api_only",
            "domain": "general",
            "risk_level": "MEDIUM",
            "complexity": "MEDIUM",
        },
        "persona_recommendation": {
            "name": "Alex Power-User",
            "role": "Experienced web application user",
            "behavior": "Methodical, tests every feature systematically",
            "expertise": "tech-savvy",
        },
        "ui_tests": [],
        "api_tests": [],
        "edge_cases": [],
        "stress_tests": [],
        "_generated_by": "fallback",
        "_discovery": discovery,
    }

    if discovery["has_frontend"]:
        plan["ui_tests"] = [
            {"test_name": "Page Load", "action": "Navigate to root URL",
             "expected": "Page loads with HTTP 200, non-blank content", "priority": "CRITICAL"},
            {"test_name": "Console Errors", "action": "Check browser console",
             "expected": "No critical JavaScript errors", "priority": "HIGH"},
            {"test_name": "Navigation", "action": "Click all nav items",
             "expected": "Each nav item loads content without error", "priority": "HIGH"},
            {"test_name": "Responsive Mobile", "action": "Resize to 375px width",
             "expected": "No horizontal overflow, content readable", "priority": "MEDIUM"},
            {"test_name": "Responsive Desktop", "action": "Resize to 1280px width",
             "expected": "Layout renders correctly", "priority": "MEDIUM"},
        ]

    for ep in discovery["endpoints"]:
        plan["api_tests"].append({
            "method": ep["method"],
            "path": ep["path"],
            "test_name": f"{ep['method']} {ep['path']}",
            "payload": None,
            "expected_status": 200 if ep["method"] == "GET" else 400,
            "priority": "HIGH",
        })

    # Standard edge cases for POST endpoints
    post_endpoints = [ep for ep in discovery["endpoints"] if ep["method"] == "POST"]
    for ep in post_endpoints[:5]:
        plan["edge_cases"].append({
            "test_name": f"Empty body → {ep['path']}",
            "method": "POST", "path": ep["path"],
            "payload": None,
            "expected_behavior": "Should return 400 with error message, NOT 500",
            "attack_type": "empty_body",
        })

    if discovery.get("health_endpoint"):
        plan["stress_tests"].append({
            "test_name": "Health endpoint under load",
            "target": discovery["health_endpoint"],
            "concurrent_requests": 10,
            "expected": "All return 200 within 5s",
        })

    return plan


# ══════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════

async def run_architect(target_url: str, app_description: str = "") -> dict:
    """
    Full Architect pipeline: discover → plan.
    Returns the complete test plan.
    """
    start = time.time()
    logger.info(f"🏗️ Architect: Scanning {target_url}...")

    # Phase 1: Discovery
    discovery = await discover_endpoints(target_url)
    logger.info(f"  Discovered {len(discovery['endpoints'])} endpoints, "
                f"frontend={'Yes' if discovery['has_frontend'] else 'No'}")

    # Phase 2: AI Test Plan
    plan = await generate_test_plan(discovery, app_description)

    elapsed = time.time() - start
    plan["_duration_seconds"] = round(elapsed, 1)
    logger.info(f"🏗️ Architect: Plan complete in {elapsed:.1f}s — "
                f"{len(plan.get('ui_tests', []))} UI, "
                f"{len(plan.get('api_tests', []))} API, "
                f"{len(plan.get('edge_cases', []))} edge cases")

    return plan
