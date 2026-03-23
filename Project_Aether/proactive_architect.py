"""
Proactive Architect — Rule 0 Enforcement Engine
=================================================
Project Aether | Meta App Factory

Hooks into the AetherRuntime to automatically analyze every routed task
and produce architecture recommendations BEFORE execution begins.

This is the enforcement layer for the Proactive Architecture Mandate
(Rule 0) defined in master-architect.md.

Usage:
    # Standalone test
    python proactive_architect.py --test

    # Integrated via AetherRuntime (automatic)
    runtime = AetherRuntime()  # ProactiveArchitect loads automatically
    result = runtime.prompt("Build a dashboard for tracking inventory")
    print(result["architecture_recommendation"])
"""

# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

RUNTIME_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_DIR = os.path.abspath(os.path.join(RUNTIME_DIR, ".."))
DIRECTIVE_PATH = os.path.join(RUNTIME_DIR, "master-architect.md")

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(FACTORY_DIR, ".env"))
except ImportError:
    pass

logger = logging.getLogger("ProactiveArchitect")


# ═══════════════════════════════════════════════════════
#  PATTERN KNOWLEDGE BASE (offline fallback)
# ═══════════════════════════════════════════════════════

ARCHITECTURE_PATTERNS = {
    "api": {
        "pattern": "RESTful API with FastAPI + async handlers",
        "rationale": "FastAPI provides automatic OpenAPI docs, async support, and type validation via Pydantic",
        "technologies": ["FastAPI", "Pydantic", "uvicorn", "httpx"],
        "scaling_notes": "Horizontal scaling via load balancer; add Redis caching for hot paths at >1K RPS",
        "alternative": "GraphQL with Strawberry if clients need flexible queries; gRPC for internal microservice calls",
        "risk_flags": ["Ensure rate limiting on public endpoints", "Add request validation middleware"],
    },
    "dashboard": {
        "pattern": "Single-file SPA with SSE real-time updates",
        "rationale": "Minimizes deployment complexity; SSE provides real-time without WebSocket overhead",
        "technologies": ["HTML5", "Vanilla JS", "CSS custom properties", "Server-Sent Events"],
        "scaling_notes": "Add service worker for offline caching; CDN for static assets at scale",
        "alternative": "React/Vite SPA for complex state management; consider HTMX for server-driven UI",
        "risk_flags": ["Mobile responsiveness required from day one", "Test on slow connections"],
    },
    "data_pipeline": {
        "pattern": "Event-driven pipeline with stage isolation",
        "rationale": "Each stage can fail independently; supports retry and dead-letter queues",
        "technologies": ["APScheduler", "asyncio", "JSON file store -> SQLite -> PostgreSQL migration path"],
        "scaling_notes": "Replace file-based store with SQLite at >10K records; PostgreSQL at >100K",
        "alternative": "Celery + Redis for distributed task queues; Apache Airflow for complex DAGs",
        "risk_flags": ["File-based stores don't support concurrent writes", "Add idempotency keys"],
    },
    "ai_agent": {
        "pattern": "Multi-agent orchestration with Critic gate",
        "rationale": "Separation of concerns: classifier -> router -> executor -> reviewer prevents hallucination propagation",
        "technologies": ["Gemini API", "n8n webhooks", "Pydantic models", "structured JSON output"],
        "scaling_notes": "Model router enables hot-swapping between Gemini Flash/Pro based on task complexity",
        "alternative": "LangGraph for complex agent state machines; CrewAI for role-based multi-agent",
        "risk_flags": ["Always validate AI output before acting on it", "Implement token budget limits"],
    },
    "notification": {
        "pattern": "Push notification hub with ntfy + fallback channels",
        "rationale": "ntfy is self-hostable, open protocol; supports mobile push without app store dependency",
        "technologies": ["ntfy", "SSE for web clients", "email fallback via SMTP"],
        "scaling_notes": "Add priority queuing; batch low-priority notifications into digests",
        "alternative": "Firebase Cloud Messaging for native mobile push; Pushover for personal use",
        "risk_flags": ["Rate limit notifications to prevent alert fatigue", "Respect quiet hours"],
    },
    "testing": {
        "pattern": "AI-driven dynamic persona testing with universal app scanning",
        "rationale": "Static test suites become stale; AI-generated personas adapt to each app's specific domain and create edge-case coverage automatically",
        "technologies": ["Gemini AI persona generation", "OpenAPI endpoint discovery", "requests", "dynamic test_endpoints"],
        "scaling_notes": "Dynamic personas scale to any new app without code changes; parallelize with CI/CD; store generated personas for regression baselines",
        "alternative": "Static hardcoded test suites per app (faster but brittle, requires manual updates for each new app)",
        "risk_flags": ["Never use static-only test suites for a multi-app factory", "Always generate app-specific personas rather than generic ones", "Test against staging, not production"],
    },
    "security": {
        "pattern": "Fernet vault + PII masking pipeline",
        "rationale": "Symmetric encryption for at-rest secrets; PII detection prevents accidental exposure",
        "technologies": ["cryptography.fernet", "regex PII detector", "audit trail logging"],
        "scaling_notes": "Migrate to HashiCorp Vault for multi-service secret management",
        "alternative": "AWS KMS / Google Cloud KMS for cloud-native key management",
        "risk_flags": ["Rotate encryption keys quarterly", "Never log decrypted secrets"],
    },
    "general": {
        "pattern": "Modular monolith with clear bounded contexts",
        "rationale": "Start monolithic for velocity; extract microservices only when scaling demands it",
        "technologies": ["Python", "FastAPI", "JSON config", "file-based state with migration path"],
        "scaling_notes": "Extract hot paths into separate services when a single module becomes a bottleneck",
        "alternative": "Microservices from the start if team size > 3 or deployment independence is critical",
        "risk_flags": ["Maintain clear module boundaries even in monolith", "Document inter-module contracts"],
    },
}

# Keyword → pattern mapping for offline classification
PATTERN_KEYWORDS = {
    "api": ["api", "endpoint", "rest", "webhook", "route", "server", "backend", "fastapi"],
    "dashboard": ["dashboard", "ui", "interface", "frontend", "page", "display", "visualization", "chart"],
    "data_pipeline": ["pipeline", "ingest", "etl", "transform", "process", "batch", "stream", "data flow"],
    "ai_agent": ["agent", "ai", "llm", "gemini", "model", "prompt", "classify", "generate", "orchestrat"],
    "notification": ["notification", "alert", "push", "ntfy", "remind", "sms", "email", "message"],
    "testing": ["test", "qa", "regression", "verify", "validate", "phantom", "assert", "check"],
    "security": ["security", "encrypt", "vault", "credential", "auth", "token", "pii", "compliance"],
}


class ProactiveArchitect:
    """
    Rule 0 enforcement engine.

    Analyzes every task routed through the Aether Runtime and produces
    architecture recommendations automatically, without waiting for user input.
    """

    def __init__(self):
        self.directive_loaded = False
        self._load_directive()
        logger.info("ProactiveArchitect initialized (Rule 0 active)")

    def _load_directive(self):
        """Load the master-architect.md directive."""
        if os.path.exists(DIRECTIVE_PATH):
            with open(DIRECTIVE_PATH, "r", encoding="utf-8") as f:
                self.directive_text = f.read()
            self.directive_loaded = True
            logger.info("Rule 0 directive loaded from master-architect.md")
        else:
            self.directive_text = ""
            logger.warning("master-architect.md not found — using built-in patterns only")

    def analyze(self, prompt: str, target_agent: str = "CEO") -> dict:
        """
        Analyze a task and produce architecture recommendations.

        This runs BEFORE the task is dispatched to any agent.
        Returns a recommendation dict that gets attached to the routing result.
        """
        # Try AI-powered analysis first
        ai_result = self._ai_analyze(prompt, target_agent)
        if ai_result:
            return ai_result

        # Fallback to keyword-based pattern matching
        return self._keyword_analyze(prompt, target_agent)

    def _ai_analyze(self, prompt: str, target_agent: str) -> Optional[dict]:
        """Use Gemini for intelligent architecture analysis."""
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return None

        analysis_prompt = f"""You are the Principal Meta-Architect for a software factory called Meta App Factory.
Your MANDATE (Rule 0): Always recommend the BEST, most scalable, state-of-the-art architecture.
Never recommend a static or hardcoded approach when a dynamic, AI-driven one exists.

Analyze this task:
Task: {prompt[:2000]}
Target Agent: {target_agent}

Respond with ONLY a JSON object (no markdown, no backticks, no explanation) with these keys:
pattern, rationale, technologies, scaling_notes, alternative, risk_flags, confidence

All values must be strings except technologies (string array), risk_flags (string array), and confidence (number 0-1).
Do NOT use special unicode characters in your response. Use only ASCII."""

        try:
            import requests as _req
            import re
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": analysis_prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
            }

            resp = _req.post(url, json=payload, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"Gemini API error: {resp.status_code}")
                return None

            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

            # Robust JSON extraction
            # Strip markdown fences if present
            if "```" in text:
                match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
                if match:
                    text = match.group(1).strip()

            # Try to find JSON object boundaries
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                text = text[start:end + 1]

            # Replace problematic unicode before parsing
            text = text.encode('ascii', 'replace').decode('ascii')

            result = json.loads(text)
            result["source"] = "gemini_analysis"
            result["timestamp"] = datetime.now().isoformat()
            result["target_agent"] = target_agent
            logger.info(f"AI architecture recommendation: {result.get('pattern', 'N/A')}")
            return result

        except Exception as e:
            logger.warning(f"AI architecture analysis failed ({e}) -- using keyword fallback")
            return None

    def _keyword_analyze(self, prompt: str, target_agent: str) -> dict:
        """Fallback: match task keywords to known architecture patterns."""
        prompt_lower = prompt.lower()
        scores = {}

        for pattern_key, keywords in PATTERN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in prompt_lower)
            if score > 0:
                scores[pattern_key] = score

        if not scores:
            best_key = "general"
        else:
            best_key = max(scores, key=scores.get)

        recommendation = dict(ARCHITECTURE_PATTERNS[best_key])
        recommendation["source"] = "keyword_pattern_match"
        recommendation["matched_pattern_key"] = best_key
        recommendation["confidence"] = min((scores.get(best_key, 0) / 3), 1.0)
        recommendation["timestamp"] = datetime.now().isoformat()
        recommendation["target_agent"] = target_agent

        logger.info(f"Keyword architecture recommendation: {recommendation['pattern']}")
        return recommendation

    def format_for_prompt(self, recommendation: dict) -> str:
        """Format the recommendation as text to inject into agent prompts."""
        lines = [
            "\n=== PROACTIVE ARCHITECTURE ADVISORY (Rule 0) ===",
            f"Pattern: {recommendation.get('pattern', 'N/A')}",
            f"Rationale: {recommendation.get('rationale', 'N/A')}",
            f"Technologies: {', '.join(str(t) for t in recommendation.get('technologies', []))}",
            f"Scaling: {recommendation.get('scaling_notes', 'N/A')}",
            f"Alternative: {recommendation.get('alternative', 'N/A')}",
        ]
        risk_flags = recommendation.get('risk_flags', [])
        if risk_flags:
            if isinstance(risk_flags, list):
                lines.append(f"Risks: {'; '.join(str(r) for r in risk_flags)}")
            else:
                lines.append(f"Risks: {risk_flags}")
        lines.append("================================================\n")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════
#  FLOW AUDITOR — System-Wide Gap Analysis (Rule 0.1)
# ═══════════════════════════════════════════════════════

# Cross-cutting features to detect in source files
FEATURE_SIGNATURES = {
    "calendar_write":     ["write_to_google_calendar", "calendar/v3/calendars", "google_event_id"],
    "calendar_read":      ["calendar_poller", "CalendarPoller", "calendar/poll"],
    "push_notification":  ["dispatcher.send_reminder", "ntfy.sh", "send_notification",
                           "_notify_state_change"],
    "vault_access":       ["vault.retrieve", "vault.store", "fernet_vault"],
    "google_auth":        ["GoogleAuth", "google_auth", "oauth", "/auth/google"],
    "ai_gemini":          ["generativelanguage.googleapis", "gemini", "GEMINI_API_KEY"],
    "pydantic_validate":  ["BaseModel", "field_validator", "ValidatedActivity",
                           "SnoozeInput", "TaskCreate", "ManualReminderInput",
                           "ReminderEdit", "CategoryOverride"],
    "document_parse":     ["DocumentParserService", "extract_activities", "upload_document"],
    "self_heal":          ["SelfHealEngine", "auto_heal", "healer"],
}

# Known Factory app directories to scan
FACTORY_APPS = {
    "Sentinel_Bridge": "Sentinel_Bridge",
    "Resonance":       "Resonance",
    "Alpha_V2_Genesis": "Alpha_V2_Genesis",
    "Factory_Core":    ".",             # root factory.py, api.py, etc.
    "Project_Aether":  "Project_Aether",
}


class FlowAuditor:
    """
    System-wide flow auditor for the Proactive Architecture Mandate.

    Scans all Factory apps to build a flow registry (endpoints + features),
    then uses Gemini to identify gaps and inconsistencies. This is the fix
    for Rule 0 only analyzing single prompts without system context.
    """

    def __init__(self, factory_dir: str = FACTORY_DIR):
        self.factory_dir = factory_dir
        self._registry: dict = {}
        self._last_scan: str = ""

    def scan_app(self, app_name: str, app_dir: str) -> dict:
        """Scan a single app directory for endpoints and feature usage."""
        import re
        app_path = os.path.join(self.factory_dir, app_dir)
        if not os.path.isdir(app_path):
            return {"name": app_name, "path": app_dir, "endpoints": [], "features": {}}

        endpoints = []
        features_found = {k: False for k in FEATURE_SIGNATURES}

        # Scan all .py files
        for root, _dirs, files in os.walk(app_path):
            # Skip __pycache__, .git, etc.
            if "__pycache__" in root or ".git" in root:
                continue
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception:
                    continue

                rel_path = os.path.relpath(fpath, self.factory_dir)

                # Detect endpoints
                ep_pattern = r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']\)'
                for m in re.finditer(ep_pattern, content, re.IGNORECASE):
                    method = m.group(1).upper()
                    route = m.group(2)

                    # Detect which features this endpoint uses
                    # Look within ~200 lines after the decorator
                    ep_start = m.end()
                    ep_block = content[ep_start:ep_start + 5000]

                    ep_features = []
                    for feat_name, sigs in FEATURE_SIGNATURES.items():
                        if any(sig in ep_block for sig in sigs):
                            ep_features.append(feat_name)

                    endpoints.append({
                        "method": method,
                        "route": route,
                        "file": rel_path,
                        "features": ep_features,
                    })

                # Detect app-wide features
                for feat_name, sigs in FEATURE_SIGNATURES.items():
                    if any(sig in content for sig in sigs):
                        features_found[feat_name] = True

        return {
            "name": app_name,
            "path": app_dir,
            "endpoints": endpoints,
            "features": {k: v for k, v in features_found.items() if v},
        }

    def build_flow_registry(self) -> dict:
        """Scan all known Factory apps and build the complete flow registry."""
        registry = {}
        for app_name, app_dir in FACTORY_APPS.items():
            registry[app_name] = self.scan_app(app_name, app_dir)

        self._registry = registry
        self._last_scan = datetime.now().isoformat()
        total_eps = sum(len(app["endpoints"]) for app in registry.values())
        logger.info(f"Flow audit: scanned {len(registry)} apps, found {total_eps} endpoints")
        return registry

    def find_gaps(self) -> list[dict]:
        """
        Analyze the flow registry to find gaps and inconsistencies.

        Rules checked:
        1. If ANY write endpoint has calendar_write, ALL write endpoints should
        2. If ANY endpoint has push_notification, mutation endpoints should too
        3. If an app has vault_access for some endpoints, sensitive endpoints should too
        4. POST/PUT endpoints without pydantic_validate are flagged
        """
        if not self._registry:
            self.build_flow_registry()

        gaps = []

        for app_name, app_data in self._registry.items():
            endpoints = app_data.get("endpoints", [])
            if not endpoints:
                continue

            # Collect features used across all endpoints
            write_eps = [ep for ep in endpoints if ep["method"] in ("POST", "PUT", "PATCH")]
            all_features = set()
            for ep in endpoints:
                all_features.update(ep.get("features", []))

            # Rule 1: Calendar write consistency
            eps_with_cal = [ep for ep in write_eps if "calendar_write" in ep.get("features", [])]
            eps_without_cal = [ep for ep in write_eps if "calendar_write" not in ep.get("features", [])
                               and any(kw in ep["route"] for kw in ["/task", "/remind", "/event", "/calendar"])]
            if eps_with_cal and eps_without_cal:
                for ep in eps_without_cal:
                    gaps.append({
                        "app": app_name,
                        "type": "missing_feature",
                        "severity": "high",
                        "endpoint": f"{ep['method']} {ep['route']}",
                        "missing": "calendar_write",
                        "reason": f"Other endpoints ({', '.join(e['route'] for e in eps_with_cal)}) "
                                  f"write to calendar, but this one does not",
                    })

            # Rule 2: Push notification on mutations
            eps_with_notif = [ep for ep in write_eps if "push_notification" in ep.get("features", [])]
            if eps_with_notif:
                for ep in write_eps:
                    if "push_notification" not in ep.get("features", []) and ep not in eps_with_notif:
                        if any(kw in ep["route"] for kw in ["/task", "/remind", "/upload", "/event"]):
                            gaps.append({
                                "app": app_name,
                                "type": "missing_feature",
                                "severity": "medium",
                                "endpoint": f"{ep['method']} {ep['route']}",
                                "missing": "push_notification",
                                "reason": "Mutation endpoint without push notification",
                            })

            # Rule 3: POST/PUT without validation
            for ep in write_eps:
                if "pydantic_validate" not in ep.get("features", []):
                    if any(kw in ep["route"] for kw in ["/task", "/upload", "/remind"]):
                        gaps.append({
                            "app": app_name,
                            "type": "missing_validation",
                            "severity": "medium",
                            "endpoint": f"{ep['method']} {ep['route']}",
                            "missing": "pydantic_validate",
                            "reason": "Write endpoint without Pydantic input validation",
                        })

        return gaps

    def ai_gap_analysis(self, task_context: str = "") -> Optional[list[dict]]:
        """Use Gemini to find deeper gaps the static rules might miss."""
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key or not self._registry:
            return None

        # Build a compact registry summary for the prompt
        summary_lines = []
        for app_name, app_data in self._registry.items():
            eps = app_data.get("endpoints", [])
            if not eps:
                continue
            summary_lines.append(f"\n## {app_name}")
            for ep in eps:
                feats = ", ".join(ep.get("features", [])) or "none"
                summary_lines.append(f"  {ep['method']} {ep['route']} [{feats}]")

        if not summary_lines:
            return None

        registry_text = "\n".join(summary_lines)

        prompt = f"""You are the Principal Meta-Architect auditing a software platform called Meta App Factory.

Here is the complete endpoint registry with feature annotations:
{registry_text}

Current task context: {task_context[:500] if task_context else 'General system audit'}

Identify GAPS and INCONSISTENCIES across these endpoints. Look for:
1. Features present in some write endpoints but missing in similar ones (e.g., calendar sync, notifications)
2. Missing input validation on mutation endpoints
3. Missing error handling patterns
4. Endpoints that should exist but don't (e.g., DELETE for every resource that has POST)
5. Security gaps (auth on some endpoints but not others)

Return ONLY a JSON array of gap objects, each with: "app", "type", "severity" (high/medium/low), "endpoint", "missing", "reason".
If no gaps found, return []. Use only ASCII characters. No markdown fences."""

        try:
            import requests as _req
            import re as _re
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4096},
            }

            resp = _req.post(url, json=payload, timeout=25)
            if resp.status_code != 200:
                return None

            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

            # Extract JSON
            if "```" in text:
                match = _re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, _re.DOTALL)
                if match:
                    text = match.group(1).strip()
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end > start:
                text = text[start:end + 1]
            text = text.encode('ascii', 'replace').decode('ascii')

            ai_gaps = json.loads(text)
            if isinstance(ai_gaps, list):
                for g in ai_gaps:
                    g["source"] = "gemini_audit"
                return ai_gaps
            return None

        except Exception as e:
            logger.warning(f"AI gap analysis failed: {e}")
            return None

    def full_audit(self, task_context: str = "") -> dict:
        """Run a complete system-wide flow audit."""
        self.build_flow_registry()

        # Phase 1: Static gap detection
        static_gaps = self.find_gaps()

        # Phase 2: AI-powered gap analysis
        ai_gaps = self.ai_gap_analysis(task_context) or []

        # Merge and deduplicate
        all_gaps = static_gaps
        seen_keys = {(g["app"], g.get("endpoint", ""), g.get("missing", "")) for g in static_gaps}
        for ag in ai_gaps:
            key = (ag.get("app", ""), ag.get("endpoint", ""), ag.get("missing", ""))
            if key not in seen_keys:
                all_gaps.append(ag)
                seen_keys.add(key)

        # Sort by severity
        severity_order = {"high": 0, "medium": 1, "low": 2}
        all_gaps.sort(key=lambda g: severity_order.get(g.get("severity", "low"), 3))

        return {
            "timestamp": datetime.now().isoformat(),
            "apps_scanned": len(self._registry),
            "total_endpoints": sum(len(a["endpoints"]) for a in self._registry.values()),
            "gaps_found": len(all_gaps),
            "gaps": all_gaps,
            "registry_summary": {
                name: {
                    "endpoints": len(data["endpoints"]),
                    "features": list(data.get("features", {}).keys()),
                }
                for name, data in self._registry.items()
            },
        }

    def format_audit_report(self, audit: dict) -> str:
        """Format audit results as a readable report for prompt injection."""
        lines = [
            "\n=== SYSTEM-WIDE FLOW AUDIT (Rule 0.1) ===",
            f"Apps scanned: {audit['apps_scanned']} | "
            f"Endpoints: {audit['total_endpoints']} | "
            f"Gaps found: {audit['gaps_found']}",
        ]

        if audit["gaps"]:
            lines.append("")
            for g in audit["gaps"][:10]:  # Cap at 10 for prompt size
                sev = g.get("severity", "?").upper()
                lines.append(f"  [{sev}] {g.get('app', '?')}: "
                             f"{g.get('endpoint', '?')} -- "
                             f"missing {g.get('missing', '?')} -- "
                             f"{g.get('reason', '')}")
        else:
            lines.append("  No gaps detected -- all flows consistent.")

        lines.append("==========================================\n")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════
#  STANDALONE TEST
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(description="Proactive Architect -- Rule 0 Engine")
    parser.add_argument("--test", action="store_true", help="Run self-test with sample prompts")
    parser.add_argument("--prompt", help="Analyze a specific prompt")
    parser.add_argument("--audit", action="store_true", help="Run system-wide flow audit")
    args = parser.parse_args()

    architect = ProactiveArchitect()

    if args.audit:
        print("\n" + "=" * 60)
        print("  SYSTEM-WIDE FLOW AUDIT -- Rule 0.1")
        print("=" * 60)
        auditor = FlowAuditor()
        audit = auditor.full_audit()
        print(f"\nApps scanned: {audit['apps_scanned']}")
        print(f"Endpoints found: {audit['total_endpoints']}")
        print(f"Gaps found: {audit['gaps_found']}\n")

        # Print registry summary
        for name, info in audit["registry_summary"].items():
            feats = ", ".join(info["features"]) if info["features"] else "none"
            print(f"  {name}: {info['endpoints']} endpoints [{feats}]")

        # Print gaps
        if audit["gaps"]:
            print(f"\n--- {len(audit['gaps'])} Gap(s) Detected ---")
            for g in audit["gaps"]:
                sev = g.get("severity", "?").upper()
                src = g.get("source", "static")
                print(f"  [{sev}] ({src}) {g.get('app', '?')}: "
                      f"{g.get('endpoint', '?')}")
                print(f"         Missing: {g.get('missing', '?')}")
                print(f"         Reason: {g.get('reason', '')}")
        else:
            print("\n  All flows consistent -- no gaps detected.")

        print("\n[OK] Audit complete.")

    elif args.test:
        test_prompts = [
            "Build a new dashboard for tracking inventory across warehouses",
            "Create an API endpoint for processing customer orders",
            "Set up a data pipeline to ingest calendar events every 15 minutes",
            "Deploy an AI agent that reviews code before merging",
            "Add push notifications for overdue reminders",
            "Write regression tests for the Sentinel Bridge",
        ]
        print("\n" + "=" * 60)
        print("  PROACTIVE ARCHITECT -- Rule 0 Self-Test")
        print("=" * 60)
        for p in test_prompts:
            result = architect.analyze(p)
            print(f"\n[PROMPT] {p}")
            print(f"   Pattern: {result['pattern']}")
            print(f"   Source: {result['source']}")
            print(f"   Technologies: {', '.join(result.get('technologies', []))}")
            print(f"   Alternative: {result.get('alternative', 'N/A')[:80]}")
        print("\n[OK] Self-test complete.")

    elif args.prompt:
        result = architect.analyze(args.prompt)
        print(json.dumps(result, indent=2, default=str))
        print("\n" + architect.format_for_prompt(result))
    else:
        parser.print_help()

