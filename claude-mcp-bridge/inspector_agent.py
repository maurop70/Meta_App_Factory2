"""
Inspector Agent — MAF E2E Evaluator
-------------------------------------
Autonomously reads an app's code and documentation, then generates a
structured TestPlan with routes, pages, auth flows, test cases, and seed
requirements.  No hardcoded test cases — everything is derived from what it
finds in the code.

Phase flow:
  1  Read documentation  (docs_paths)
  2  Read backend routes (@app.get/post/put/delete decorators)
  3  Read frontend pages (.jsx / .tsx files)
  4  Build AuthFlows      (from auth_config)
  5  Generate TestCases   (via ay_client / Gemini; falls back to rule-based)
  6  Build SeedRequirements
  7  Return TestPlan       (and save to logs/qa_runs/smoke_test_plan.json)
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# ── Locate the bridge root so sibling imports resolve ────────────────────────
_BRIDGE_DIR = Path(__file__).parent.resolve()
_MAF_ROOT   = _BRIDGE_DIR.parent.resolve()
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dataclasses
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class RouteInfo:
    method:        str         # GET POST PUT DELETE
    path:          str         # /api/mwo/{id}
    description:   str         # derived from docstring or name
    requires_auth: bool
    params:        list[str]   # path params like {id}


@dataclass
class PageInfo:
    route:         str         # /archive
    component:     str         # ArchiveDashboard.jsx
    requires_auth: bool
    roles:         list[str]   # ["HM", "ADMIN"]
    api_calls:     list[str]   # endpoints this page calls


@dataclass
class AuthFlow:
    role:        str           # "HM" | "DM" | "TECH" | "ADMIN"
    login_url:   str
    credentials: dict


@dataclass
class TestCase:
    id:            str         # TC-001
    name:          str
    description:   str
    category:      str         # auth | crud | navigation | workflow | error_handling
    page:          str
    role:          str
    steps:         list[str]
    expected:      str
    priority:      int         # 1=critical 2=high 3=medium
    requires_seed: bool


@dataclass
class TableSeed:
    table_name:    str
    min_records:   int
    sample_record: dict        # field names + example values


@dataclass
class SeedRequirements:
    tables: list               # list[TableSeed]


@dataclass
class TestPlan:
    app_name:          str
    base_url:          str
    routes:            list    # list[RouteInfo]
    pages:             list    # list[PageInfo]
    auth_flows:        list    # list[AuthFlow]
    test_cases:        list    # list[TestCase]
    seed_requirements: Any     # SeedRequirements


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _read_file(path: str | Path) -> str:
    """Read a text file; return empty string on failure."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _resolve(base: str | Path, rel: str) -> Path:
    """Resolve rel relative to base, unless rel is already absolute."""
    p = Path(rel)
    if p.is_absolute():
        return p
    return (Path(base) / rel).resolve()


def _strip_fences(text: str) -> str:
    """Strip ```json ... ``` fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # remove first and last fence lines
        start = 1
        end   = len(lines)
        if lines[-1].strip() == "```":
            end = len(lines) - 1
        text = "\n".join(lines[start:end]).strip()
    return text


def _to_serialisable(obj: Any) -> Any:
    """Recursively convert dataclasses / nested objects to plain dicts/lists."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_serialisable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_serialisable(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_serialisable(v) for k, v in obj.items()}
    return obj


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# InspectorAgent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class InspectorAgent:
    """
    Inspects an app's code and documentation, then produces a TestPlan.
    """

    # ── Public entry-point ────────────────────────────────────────────────────

    def inspect(self, app_config: dict) -> TestPlan:
        """Run all 7 phases and return a complete TestPlan."""
        self._app_config = app_config
        local_path  = app_config.get("local_path", "")
        base_url    = app_config.get("base_url", "http://localhost")
        app_name    = app_config.get("name", "Unknown App")

        print(f"[Inspector] Inspecting: {app_name}")

        # Phase 1 — documentation
        doc_summary = self._phase1_docs(app_config, local_path)
        print(f"[Inspector] Phase 1 done — docs read")

        # Phase 2 — backend routes
        routes = self._phase2_backend(app_config, local_path)
        print(f"[Inspector] Phase 2 done — {len(routes)} routes found")

        # Phase 3 — frontend pages
        pages = self._phase3_frontend(app_config, local_path)
        print(f"[Inspector] Phase 3 done — {len(pages)} pages found")

        # Phase 4 — auth flows
        auth_flows = self._phase4_auth(app_config, base_url)
        print(f"[Inspector] Phase 4 done — {len(auth_flows)} auth flows")

        # Phase 5 — generate test cases
        test_cases = self._phase5_test_cases(routes, pages, auth_flows, doc_summary)
        print(f"[Inspector] Phase 5 done — {len(test_cases)} test cases")

        # Phase 6 — seed requirements
        seed_req = self._phase6_seed(test_cases, routes)
        print(f"[Inspector] Phase 6 done — {len(seed_req.tables)} seed tables")

        # Phase 7 — assemble and persist
        plan = TestPlan(
            app_name          = app_name,
            base_url          = base_url,
            routes            = routes,
            pages             = pages,
            auth_flows        = auth_flows,
            test_cases        = test_cases,
            seed_requirements = seed_req,
        )
        self._phase7_save(plan)
        return plan

    # ── Phase 1: Read documentation ──────────────────────────────────────────

    def _phase1_docs(self, app_config: dict, local_path: str) -> str:
        """Read all listed documentation files and return concatenated text."""
        docs_paths = app_config.get("docs_paths", [])
        parts: list[str] = []
        for rel in docs_paths:
            abs_path = _resolve(local_path, rel)
            content  = _read_file(abs_path)
            if content:
                parts.append(f"=== {rel} ===\n{content}")
        return "\n\n".join(parts) if parts else ""

    # ── Phase 2: Read backend routes ─────────────────────────────────────────

    def _phase2_backend(self, app_config: dict, local_path: str) -> list[RouteInfo]:
        """Parse FastAPI / Flask-style route decorators from the backend file."""
        backend_rel  = app_config.get("backend_file", "")
        backend_path = _resolve(local_path, backend_rel)
        content      = _read_file(backend_path)
        if not content:
            return []

        routes: list[RouteInfo] = []
        # Split into function blocks so we can check each block for Depends(
        # Pattern: @app.<method>("path") ... def func_name(...)
        block_pattern = re.compile(
            r'@app\.(get|post|put|delete|patch)\s*\(\s*"([^"]+)".*?\n'   # decorator
            r'(?:.*?\n)*?'                                                  # optional lines (docstring etc.)
            r'async def\s+(\w+)\s*\(([^)]*)\)',                            # function signature
            re.IGNORECASE | re.DOTALL,
        )

        # Simpler two-pass approach: first find all decorators + paths, then
        # for each find the next function and inspect a window for Depends(
        dec_pattern = re.compile(
            r'@\w+\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        )
        func_pattern = re.compile(r'(?:async\s+)?def\s+(\w+)\s*\(', re.IGNORECASE)

        lines = content.splitlines()
        n     = len(lines)

        for i, line in enumerate(lines):
            dm = dec_pattern.search(line)
            if not dm:
                continue
            method = dm.group(1).upper()
            path   = dm.group(2)

            # Extract path params like {id}
            params = re.findall(r'\{(\w+)\}', path)

            # Search the next ~8 lines for the function definition
            window_end  = min(i + 8, n)
            window      = "\n".join(lines[i:window_end])

            description = ""
            fm = func_pattern.search(window)
            if fm:
                func_name   = fm.group(1)
                description = func_name.replace("_", " ").strip()
                # Look for a docstring in the next few lines after def
                def_line_idx = None
                for j in range(i, window_end):
                    if func_pattern.search(lines[j]):
                        def_line_idx = j
                        break
                if def_line_idx is not None:
                    doc_window = "\n".join(lines[def_line_idx:min(def_line_idx + 4, n)])
                    doc_m = re.search(r'"""(.*?)"""', doc_window, re.DOTALL)
                    if doc_m:
                        description = doc_m.group(1).strip().splitlines()[0].strip()

            # Check for Depends( in the next 15 lines as proxy for auth
            auth_window = "\n".join(lines[i:min(i + 15, n)])
            requires_auth = "Depends(" in auth_window or "verify_token" in auth_window

            routes.append(RouteInfo(
                method        = method,
                path          = path,
                description   = description or path,
                requires_auth = requires_auth,
                params        = params,
            ))

        return routes

    # ── Phase 3: Read frontend pages ─────────────────────────────────────────

    def _phase3_frontend(self, app_config: dict, local_path: str) -> list[PageInfo]:
        """Scan .jsx/.tsx files in the frontend_dir and extract page info."""
        frontend_rel = app_config.get("frontend_dir", "")
        frontend_dir = _resolve(local_path, frontend_rel)
        if not frontend_dir.is_dir():
            return []

        jsx_files = list(frontend_dir.rglob("*.jsx")) + list(frontend_dir.rglob("*.tsx"))
        pages: list[PageInfo] = []

        for fpath in jsx_files:
            # Skip .deprecated files
            if ".deprecated" in fpath.name:
                continue
            content   = _read_file(fpath)
            component = fpath.name

            # Try to extract a route path from Route / useNavigate / Link
            route = self._guess_route(component, content)

            # API calls: fetch( or axios. or /api/ string literals
            api_calls = self._extract_api_calls(content)

            # Auth role checks
            roles = self._extract_roles(content)

            # Requires auth? — look for token, isAuthenticated, role checks
            requires_auth = bool(
                re.search(r'token|isAuthenticated|currentRole|useAuth|PrivateRoute', content)
            )

            pages.append(PageInfo(
                route         = route,
                component     = component,
                requires_auth = requires_auth,
                roles         = roles,
                api_calls     = api_calls,
            ))

        return pages

    def _guess_route(self, component: str, content: str) -> str:
        """Derive a likely URL route from the component name / content."""
        # Explicit Route path attributes
        m = re.search(r'<Route\s+[^>]*path\s*=\s*["\']([^"\']+)["\']', content)
        if m:
            return m.group(1)
        # useNavigate / navigate calls
        m = re.search(r'navigate\s*\(\s*["\']([^"\']+)["\']', content)
        if m:
            return m.group(1)
        # Link to= attributes
        m = re.search(r'to\s*=\s*["\']([/][^"\']+)["\']', content)
        if m:
            return m.group(1)

        # Fallback: derive from component filename
        name = re.sub(r'\.(jsx|tsx)$', '', component, flags=re.I)
        # CamelCase → kebab-case
        kebab = re.sub(r'(?<!^)(?=[A-Z])', '-', name).lower()
        # Drop generic suffixes
        for suffix in ('-dashboard', '-console', '-page', '-view'):
            if kebab.endswith(suffix) and kebab != suffix:
                kebab = kebab[: -len(suffix)]
        return f"/{kebab}"

    def _extract_api_calls(self, content: str) -> list[str]:
        """Pull /api/... URL strings from a JSX/TSX file."""
        hits = re.findall(r'["\`](/api/[^"\`\s]+)["\`]', content)
        # Also catch template literals like `/api/mwo/${id}`
        hits += re.findall(r'`(/api/[^`\$]+)', content)
        # Deduplicate while preserving order
        seen: set[str] = set()
        result: list[str] = []
        for h in hits:
            h = h.rstrip('/')
            if h not in seen:
                seen.add(h)
                result.append(h)
        return result

    def _extract_roles(self, content: str) -> list[str]:
        """Extract role strings referenced in the component."""
        roles: set[str] = set()
        # role === "HM" | role === 'TECH' etc.
        for m in re.finditer(r'''(?:role|currentRole|userRole)\s*===?\s*['"](\w+)['"]''', content):
            roles.add(m.group(1).upper())
        # includes("HM")
        for m in re.finditer(r'''includes\s*\(\s*['"](\w+)['"]\s*\)''', content):
            candidate = m.group(1).upper()
            if candidate in ("HM", "DM", "TECH", "ADMIN"):
                roles.add(candidate)
        return sorted(roles)

    # ── Phase 4: Build AuthFlows ──────────────────────────────────────────────

    def _phase4_auth(self, app_config: dict, base_url: str) -> list[AuthFlow]:
        """Map credential keys in auth_config to role AuthFlow objects."""
        auth_config = app_config.get("auth_config", {})
        login_url   = base_url.rstrip("/") + "/login"

        # Map credential keys → role names
        key_to_role = {
            "hm_pin":    "HM",
            "tech_pin":  "TECH",
            "dm_pin":    "DM",
            "admin_pin": "ADMIN",
        }

        flows: list[AuthFlow] = []
        seen_roles: set[str] = set()

        for key, role in key_to_role.items():
            if key in auth_config:
                creds: dict = {key: auth_config[key]}
                # Also include any companion field (e.g. dm_employee_id)
                companion_key = key.replace("_pin", "_employee_id")
                if companion_key in auth_config:
                    creds[companion_key] = auth_config[companion_key]
                flows.append(AuthFlow(
                    role        = role,
                    login_url   = login_url,
                    credentials = creds,
                ))
                seen_roles.add(role)

        return flows

    # ── Phase 5: Generate TestCases (LLM-assisted) ────────────────────────────

    def _phase5_test_cases(
        self,
        routes:     list[RouteInfo],
        pages:      list[PageInfo],
        auth_flows: list[AuthFlow],
        doc_summary: str,
    ) -> list[TestCase]:
        """Call ay_client / Gemini to generate test cases, or fall back."""

        routes_json    = json.dumps([asdict(r) for r in routes],     indent=2)
        pages_json     = json.dumps([asdict(p) for p in pages],      indent=2)
        auth_flows_json= json.dumps([asdict(a) for a in auth_flows], indent=2)

        prompt = f"""You are a senior QA engineer building an automated test plan.

Given this web application structure:

ROUTES (backend API endpoints):
{routes_json}

PAGES (frontend components):
{pages_json}

AUTH FLOWS (roles and credentials):
{auth_flows_json}

DOCUMENTATION SUMMARY:
{doc_summary[:3000] if doc_summary else "No documentation available."}

Generate a comprehensive test plan as a JSON array.
Requirements:
- Every major feature must have at least one test case.
- Include: auth tests, CRUD tests, navigation tests, workflow tests, error_handling tests.
- Prioritize: 1=must pass before deploy, 2=important, 3=nice to have.
- Use realistic role names from the auth flows (HM, TECH, DM, ADMIN).
- steps must be an array of short human-readable action strings.

Return ONLY a JSON array of objects, each with EXACTLY these fields:
  id           (string, e.g. "TC-001")
  name         (string)
  description  (string)
  category     (string: one of auth|crud|navigation|workflow|error_handling)
  page         (string: component filename or route)
  role         (string: HM|TECH|DM|ADMIN|any)
  steps        (array of strings)
  expected     (string)
  priority     (integer: 1, 2, or 3)
  requires_seed (boolean)

No preamble, no markdown code fences, no explanation. Pure JSON array only."""

        raw = self._call_llm(prompt)
        if raw:
            cases = self._parse_test_cases(raw)
            if cases:
                return cases

        # Fallback — rule-based generation
        print("[Inspector] LLM unavailable or returned bad JSON — using rule-based fallback")
        return self._fallback_test_cases(routes, pages, auth_flows)

    def _call_llm(self, prompt: str) -> str | None:
        """Try ay_client; return response text or None on failure."""
        try:
            # ay_client.send_mandate uses Gemini agentic loop — for pure generation
            # we just want a single-turn call.  Use the underlying client directly
            # so we avoid the tool-use loop overhead.
            import warnings
            from google import genai
            from google.genai import types
            from dotenv import load_dotenv

            load_dotenv(_MAF_ROOT / ".env")
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                return None

            client = genai.Client(api_key=api_key)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                response = client.models.generate_content(
                    model   = "gemini-2.5-flash",
                    contents= prompt,
                    config  = types.GenerateContentConfig(temperature=0.2),
                )
            return getattr(response, "text", None) or str(response)
        except Exception as exc:
            print(f"[Inspector] LLM call failed: {exc}")
            return None

    def _parse_test_cases(self, raw: str) -> list[TestCase]:
        """Parse raw LLM text into TestCase objects."""
        try:
            cleaned = _strip_fences(raw)
            data    = json.loads(cleaned)
            if not isinstance(data, list):
                return []
            cases: list[TestCase] = []
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    continue
                cases.append(TestCase(
                    id            = item.get("id")            or f"TC-{i+1:03d}",
                    name          = item.get("name")          or "Unnamed test",
                    description   = item.get("description")   or "",
                    category      = item.get("category")      or "navigation",
                    page          = item.get("page")          or "",
                    role          = item.get("role")          or "any",
                    steps         = item.get("steps")         or [],
                    expected      = item.get("expected")      or "",
                    priority      = int(item.get("priority")  or 2),
                    requires_seed = bool(item.get("requires_seed", False)),
                ))
            return cases
        except Exception as exc:
            print(f"[Inspector] JSON parse failed: {exc}")
            return []

    def _fallback_test_cases(
        self,
        routes:     list[RouteInfo],
        pages:      list[PageInfo],
        auth_flows: list[AuthFlow],
    ) -> list[TestCase]:
        """Generate a reasonable set of test cases from routes/pages without LLM."""
        cases: list[TestCase] = []
        counter = 1

        def _tc(**kwargs) -> TestCase:
            nonlocal counter
            tc = TestCase(
                id            = kwargs.get("id",            f"TC-{counter:03d}"),
                name          = kwargs.get("name",          ""),
                description   = kwargs.get("description",   ""),
                category      = kwargs.get("category",      "navigation"),
                page          = kwargs.get("page",          ""),
                role          = kwargs.get("role",          "any"),
                steps         = kwargs.get("steps",         []),
                expected      = kwargs.get("expected",      ""),
                priority      = kwargs.get("priority",      2),
                requires_seed = kwargs.get("requires_seed", False),
            )
            counter += 1
            return tc

        # Auth tests for each role
        for af in auth_flows:
            cases.append(_tc(
                name          = f"{af.role} — valid login",
                description   = f"Authenticate as {af.role} with correct PIN",
                category      = "auth",
                page          = "Login.jsx",
                role          = af.role,
                steps         = [
                    f"Navigate to {af.login_url}",
                    f"Enter {af.role} credentials",
                    "Submit the login form",
                ],
                expected      = f"{af.role} dashboard loads without errors",
                priority      = 1,
                requires_seed = False,
            ))
            cases.append(_tc(
                name          = f"{af.role} — invalid PIN rejected",
                description   = f"Ensure wrong PIN shows error for {af.role}",
                category      = "error_handling",
                page          = "Login.jsx",
                role          = af.role,
                steps         = [
                    f"Navigate to {af.login_url}",
                    f"Enter wrong PIN for {af.role}",
                    "Submit the login form",
                ],
                expected      = "Error message displayed; no navigation away from login",
                priority      = 1,
                requires_seed = False,
            ))

        # Navigation test for each page
        for page in pages:
            primary_role = page.roles[0] if page.roles else (
                auth_flows[0].role if auth_flows else "any"
            )
            cases.append(_tc(
                name          = f"Navigate to {page.component}",
                description   = f"Page {page.component} loads without console errors",
                category      = "navigation",
                page          = page.component,
                role          = primary_role,
                steps         = [
                    f"Authenticate as {primary_role}",
                    f"Navigate to {page.route}",
                    "Wait for page to fully load",
                ],
                expected      = "Page renders without JS errors or failed network requests",
                priority      = 2,
                requires_seed = False,
            ))

        # CRUD tests for POST/PUT routes
        crud_routes = [r for r in routes if r.method in ("POST", "PUT", "DELETE")]
        for route in crud_routes:
            cases.append(_tc(
                name          = f"API {route.method} {route.path}",
                description   = f"Test {route.description} endpoint",
                category      = "crud",
                page          = route.path,
                role          = auth_flows[0].role if auth_flows else "any",
                steps         = [
                    "Authenticate with valid credentials",
                    f"Send {route.method} request to {route.path}",
                    "Check response status and payload",
                ],
                expected      = "HTTP 200/201 with valid JSON; data persisted in DB",
                priority      = 2,
                requires_seed = route.method in ("PUT", "DELETE"),
            ))

        # Workflow test: end-to-end create → view
        create_routes = [r for r in routes if r.method == "POST"]
        if create_routes and auth_flows:
            cases.append(_tc(
                name          = "End-to-end create and view record",
                description   = "Create a new record and verify it appears in the list",
                category      = "workflow",
                page          = "Dashboard",
                role          = auth_flows[0].role,
                steps         = [
                    f"Authenticate as {auth_flows[0].role}",
                    "Open the create form",
                    "Fill in all required fields",
                    "Submit the form",
                    "Navigate to the records list",
                    "Verify the new record is present",
                ],
                expected      = "New record visible in the list with correct data",
                priority      = 1,
                requires_seed = False,
            ))

        return cases

    # ── Phase 6: Build SeedRequirements ──────────────────────────────────────

    def _phase6_seed(
        self,
        test_cases: list[TestCase],
        routes:     list[RouteInfo],
    ) -> SeedRequirements:
        """Infer DB tables that need seeding from test cases and route paths."""

        # Build a mapping from URL path fragment → table name
        _FRAGMENT_TABLE: dict[str, tuple[str, dict]] = {
            "mwo":          ("work_orders",    {"id": 1, "title": "Test MWO",   "status": "open"}),
            "work_order":   ("work_orders",    {"id": 1, "title": "Test MWO",   "status": "open"}),
            "user":         ("users",          {"id": 1, "username": "testuser","role": "HM"}),
            "employee":     ("employees",      {"id": 1, "name": "Test Tech",   "role": "TECH"}),
            "equipment":    ("equipment",      {"id": 1, "name": "Unit A",      "status": "active"}),
            "part":         ("parts",          {"id": 1, "sku": "SKU-001",      "qty": 10}),
            "sku":          ("skus",           {"id": 1, "code": "SKU-001",     "description": "Test part"}),
            "procurement":  ("procurement",    {"id": 1, "sku_id": 1,           "qty": 5}),
            "dispatch":     ("dispatch_queue", {"id": 1, "mwo_id": 1,           "tech_id": 2}),
            "archive":      ("archive",        {"id": 1, "mwo_id": 1,           "closed_at": "2024-01-01"}),
        }

        table_map: dict[str, TableSeed] = {}

        # From routes that have seed-requiring test cases
        seed_routes = {tc.page for tc in test_cases if tc.requires_seed}

        # Also look at all route paths
        all_paths = [r.path for r in routes] + list(seed_routes)

        for path_str in all_paths:
            for fragment, (table_name, sample) in _FRAGMENT_TABLE.items():
                if fragment in path_str.lower() and table_name not in table_map:
                    table_map[table_name] = TableSeed(
                        table_name    = table_name,
                        min_records   = 5,
                        sample_record = sample,
                    )

        # Always seed users/employees if there are auth flows
        for tbl, sample in [
            ("users",     {"id": 1, "username": "testuser", "role": "HM",   "pin_hash": "..."}),
            ("employees", {"id": 1, "name": "Test Tech",    "role": "TECH", "pin": "2345"}),
        ]:
            if tbl not in table_map:
                table_map[tbl] = TableSeed(
                    table_name    = tbl,
                    min_records   = 3,
                    sample_record = sample,
                )

        return SeedRequirements(tables=list(table_map.values()))

    # ── Phase 7: Save & return ───────────────────────────────────────────────

    def _phase7_save(self, plan: TestPlan) -> None:
        """Persist the test plan JSON to logs/qa_runs/smoke_test_plan.json."""
        out_dir  = _MAF_ROOT / "logs" / "qa_runs"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "smoke_test_plan.json"
        payload  = _to_serialisable(plan)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"[Inspector] Saved to {out_path}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# __main__ — smoke test against MWO ERP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    import json, os, sys

    # Force UTF-8 on Windows consoles so Unicode in print() doesn't crash
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    registry_path = _BRIDGE_DIR / "e2e_app_registry.json"
    registry      = json.loads(registry_path.read_text(encoding="utf-8"))
    app_config    = registry["apps"][0]   # MWO ERP

    print("=" * 60)
    print("Inspector Agent - MWO ERP Smoke Test")
    print("=" * 60)

    agent = InspectorAgent()
    plan  = agent.inspect(app_config)

    print()
    print(f"  Routes found        : {len(plan.routes)}")
    for r in plan.routes:
        print(f"    {r.method:<6} {r.path}")

    print()
    print(f"  Pages found         : {len(plan.pages)}")
    for p in plan.pages:
        print(f"    {p.component}")

    print()
    print(f"  Auth flows          : {len(plan.auth_flows)}")
    for a in plan.auth_flows:
        print(f"    {a.role} -> {a.login_url}")

    print()
    print(f"  Test cases generated: {len(plan.test_cases)}")
    from collections import Counter
    cats = Counter(tc.category for tc in plan.test_cases)
    for cat, cnt in sorted(cats.items()):
        print(f"    {cat}: {cnt}")

    print()
    print(f"  Seed tables         : {len(plan.seed_requirements.tables)}")
    for t in plan.seed_requirements.tables:
        print(f"    {t.table_name} (min {t.min_records} records)")

    out = _MAF_ROOT / "logs" / "qa_runs" / "smoke_test_plan.json"
    print()
    print(f"Saved to {out}")
