"""
genesis_orchestrator.py — Phase 11.0: Genesis Architect Orchestrator
═══════════════════════════════════════════════════════════════════
Authoritative, deterministic agent ontology synthesis engine.
"""

import os
import json
import logging
import re
import asyncio
import aiofiles
from typing import List, Optional, AsyncGenerator

from duckduckgo_search import DDGS
import google.generativeai as genai
from pydantic import ValidationError

from schemas import AgentOntology, EndpointSpec, DataContract, SecurityPosture, RouteLogicSpec

logger = logging.getLogger("GenesisOrchestrator")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

ON_COMPILE_SUCCESS_CALLBACKS = []

def get_free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class OntologyValidationError(Exception):
    """Structured validation error indicating architectural schema fractures."""
    def __init__(self, message: str, round_number: int, validation_errors: list, raw_json: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.round_number = round_number
        self.validation_errors = validation_errors
        self.raw_json = raw_json


class GenesisOrchestrator:
    """
    Orchestrates the two-stage pre-flight pipeline for new agent synthesis:
    1. Research_Node: Live DuckDuckGo queries + Gemini Flash JSON generation.
    2. Verification_Node: Pydantic + logical invariants assertion with a 3-round retry loop.
    """
    MAX_ROUNDS = 3

    def __init__(self):
        # Ensure Gemini client is configured
        api_key = os.getenv("GEMINI_API_KEY", "")
        if api_key:
            api_key = api_key.strip("'\"")
        if api_key:
            genai.configure(api_key=api_key)
        else:
            logger.warning("GEMINI_API_KEY not configured. Gemini calls will fail.")

    def _execute_research(self, prompt: str) -> tuple[str, List[str]]:
        """
        Executes 2 targeted DuckDuckGo searches and aggregates results.
        Returns aggregated text and citation URLs.
        """
        logger.info(f"Initiating autonomous web research for prompt: '{prompt}'")
        queries = [
            f"{prompt} agent architecture API specifications details",
            f"{prompt} python library dependencies implementation patterns"
        ]
        
        aggregated_research = []
        citations = []
        
        try:
            with DDGS() as ddgs:
                for q in queries:
                    logger.info(f"Firing query to DuckDuckGo: '{q}'")
                    try:
                        results = list(ddgs.text(q, max_results=4))
                        for r in results:
                            title = r.get("title", "No Title")
                            href = r.get("href", "")
                            body = r.get("body", "")
                            if href:
                                citations.append(href)
                            aggregated_research.append(
                                f"Source: {title} ({href})\nContent: {body}\n"
                            )
                    except Exception as q_err:
                        logger.error(f"DuckDuckGo query '{q}' failed: {q_err}")
        except Exception as ddg_err:
            logger.error(f"DuckDuckGo search context failed entirely: {ddg_err}")

        # Unique citations
        citations = list(sorted(set(citations)))
        
        research_context = "\n".join(aggregated_research) if aggregated_research else "No search results retrieved."
        return research_context, citations

    async def _research_node(self, prompt: str, round_num: int, citations: List[str], prior_errors: Optional[list] = None, prior_json: Optional[dict] = None) -> dict:
        """
        Synthesizes research context and prompt into a candidate AgentOntology JSON via Gemini Flash.
        """
        logger.info(f"Running Research_Node (Round {round_num})")
        
        research_data, gathered_citations = await asyncio.to_thread(self._execute_research, prompt)
        
        # Merge citations
        all_citations = list(sorted(set(citations + gathered_citations)))
        
        # Build strict system instruction describing target Pydantic schema precisely
        system_instruction = (
            "You are the Genesis Research Architect. Your persona is highly technical and precise.\n"
            "Your sole objective is to output a raw JSON structure conforming EXACTLY to the following Pydantic schema details:\n\n"
            "SCHEMA DEFINITION:\n"
            "1. agent_name (string): PascalCase name of the agent. Starts with an uppercase letter, containing only letters, numbers, or underscores (e.g., 'StockAlertAgent'). No spaces or hyphens allowed.\n"
            "2. role_summary (string): Brief summary of the agent's role and primary directive. MUST NOT exceed 280 characters and MUST NOT be empty.\n"
            "3. primary_capabilities (list of strings): Describe what this agent can do. Min 3 capabilities, max 8 capabilities.\n"
            "4. api_endpoints (list of objects): At least one endpoint spec. Each endpoint object has:\n"
            "   - path (string): URL path. MUST start with '/api/' (e.g. '/api/v1/alerts').\n"
            "   - method (string): HTTP method. Must be one of GET | POST | PUT | DELETE | PATCH. IMPORTANT: You must include at least one POST endpoint.\n"
            "   - summary (string): One-line description of the endpoint's purpose.\n"
            "   - contract_ref (string): Unique name referencing a contract name in data_contracts.\n"
            "5. data_contracts (list of objects): At least one data contract. Each contract object has:\n"
            "   - contract_name (string): Name of the contract (MUST match the contract_ref of the endpoint).\n"
            "   - input_fields (list of strings): List of required input field names for the API payload.\n"
            "   - output_fields (list of strings): List of guaranteed output field names in the response.\n"
            "   - error_codes (list of integers): E.g., [400, 422, 500].\n"
            "6. dependencies (list of strings): pip package dependencies required (e.g. 'fastapi>=0.110.0', 'pydantic>=2.0').\n"
            "7. security_posture (object):\n"
            "   - auth_method (string): Must be api_key | bearer_token | none | oauth2.\n"
            "   - rate_limit_rpm (integer): Max requests per minute. >= 1 (default 60).\n"
            "   - audit_log_enabled (boolean): Log all requests (default true).\n"
            "   - cors_origins (list of strings): Permitted origins (default ['http://localhost:5173']).\n"
            "8. research_citations (list of strings): URLs of research sources. Use the exact citation list provided in the user message.\n"
            "9. ontology_version (string): Must be '1.0.0'.\n"
            "10. verified (boolean): Set to false by default.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "- Every api_endpoint's 'contract_ref' MUST match a corresponding 'contract_name' in data_contracts.\n"
            "- You must respond with raw JSON only. Do not wrap the JSON in markdown fences, backticks, or any conversational preamble.\n"
            "- Enforce highly detailed, robust, enterprise-grade endpoints and inputs."
        )

        user_content = (
            f"USER DIRECTIVE: {prompt}\n\n"
            f"RESEARCH CONTEXT:\n{research_data}\n\n"
            f"CITATION URLS TO INCLUDE IN 'research_citations': {all_citations}\n"
        )
        
        if prior_errors and prior_json:
            user_content += (
                f"\n\n[WARNING] Your previous generation failed Pydantic validation with these errors:\n"
                f"{json.dumps(prior_errors, indent=2)}\n\n"
                f"Please review the previous invalid JSON payload and correct all schema fractures:\n"
                f"{json.dumps(prior_json, indent=2)}\n"
            )

        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=system_instruction
        )
        
        response = await asyncio.to_thread(
            model.generate_content,
            user_content,
            generation_config={
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        )
        
        raw_text = response.text.strip()
        
        # Parse output into JSON
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as decode_err:
            logger.error(f"Gemini Flash failed to return valid JSON: {decode_err}\nRaw text: {raw_text}")
            # Try to regex extract JSON if it was accidentally wrapped anyway
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
            raise OntologyValidationError(
                message=f"Gemini response was not valid JSON: {decode_err}",
                round_number=round_num,
                validation_errors=[{"type": "json_decode_error", "msg": str(decode_err)}]
            )

    def _verification_node(self, raw_dict: dict, round_num: int) -> AgentOntology:
        """
        Validates the raw dict against Pydantic schemas and logical invariants.
        Sets verified=True ONLY after all assertions succeed.
        """
        logger.info(f"Running Verification_Node (Round {round_num})")
        
        try:
            # Let Pydantic do the heavy lifting of parsing and schema compliance
            ontology = AgentOntology(**raw_dict)
            
            # If Pydantic passed, we can confidently mark it verified as the Verification Node
            ontology.verified = True
            logger.info("Verification_Node check passed successfully!")
            return ontology
            
        except ValidationError as val_err:
            errors = []
            for err in val_err.errors():
                loc = " -> ".join(str(x) for x in err["loc"])
                errors.append({
                    "loc": loc,
                    "type": err["type"],
                    "msg": err["msg"]
                })
            
            logger.warning(f"Verification failed on round {round_num} with errors: {errors}")
            raise OntologyValidationError(
                message="Ontology failed Pydantic and logical verification checks.",
                round_number=round_num,
                validation_errors=errors,
                raw_json=raw_dict
            )

    async def run_stream(self, prompt: str, route_logic_blocks: Optional[list] = None, startup_logic_ast: Optional[str] = None) -> AsyncGenerator[str, None]:
        """
        Async generator yielding SSE formatted strings tracking the pipeline progress.
        """
        yield f"data: {json.dumps({'event': 'research_start', 'prompt': prompt})}\n\n"
        
        citations = []
        prior_errors = None
        prior_json = None
        
        for round_num in range(1, self.MAX_ROUNDS + 1):
            yield f"data: {json.dumps({'event': 'verify_start', 'round': round_num})}\n\n"
            
            try:
                # 1. Synthesize candidate ontology JSON
                raw_dict = await self._research_node(
                    prompt=prompt,
                    round_num=round_num,
                    citations=citations,
                    prior_errors=prior_errors,
                    prior_json=prior_json
                )
                
                # Keep citations updated
                citations = list(sorted(set(citations + raw_dict.get("research_citations", []))))
                
                if route_logic_blocks:
                    raw_dict["route_logic_blocks"] = route_logic_blocks
                if startup_logic_ast:
                    raw_dict["startup_logic_ast"] = startup_logic_ast

                # 2. Run Verification
                ontology = self._verification_node(raw_dict, round_num)
                
                # Success path
                yield f"data: {json.dumps({'event': 'research_complete', 'citations': citations})}\n\n"
                yield f"data: {json.dumps({'event': 'verify_pass', 'round': round_num})}\n\n"
                yield f"data: {json.dumps({'event': 'ontology_ready', 'ontology': ontology.model_dump()})}\n\n"
                
                # ── DETERMINISTIC JINJA2 COMPILATION ──
                agent_name = ontology.agent_name
                logger.info(f"Initiating deterministic Jinja2 compilation matrix for '{agent_name}'...")
                
                # 1. Dynamic Port Selection
                allocated_port = get_free_port()
                
                # 2. Enrich endpoints with path_params
                api_endpoints_enriched = []
                for ep in ontology.api_endpoints:
                    ep_dict = ep.model_dump()
                    params = re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', ep.path)
                    ep_dict["path_params"] = params
                    api_endpoints_enriched.append(ep_dict)
                
                # 3. Render fastapi_app.jinja
                import jinja2
                template_dir = os.path.join(SCRIPT_DIR, "templates")
                env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
                template = env.get_template("fastapi_app.jinja")
                
                extra_imports = []
                for rlb in (ontology.route_logic_blocks or []):
                    for imp in rlb.imports:
                        if imp not in extra_imports:
                            extra_imports.append(imp)

                rendered_app = template.render(
                    agent_name=ontology.agent_name,
                    role_summary=ontology.role_summary,
                    primary_capabilities=ontology.primary_capabilities,
                    api_endpoints=api_endpoints_enriched,
                    data_contracts=[dc.model_dump() for dc in ontology.data_contracts],
                    security_posture=ontology.security_posture.model_dump(),
                    route_logic_blocks=[rlb.model_dump() for rlb in ontology.route_logic_blocks] if ontology.route_logic_blocks else [],
                    startup_logic_ast=ontology.startup_logic_ast,
                    extra_imports=extra_imports
                )
                
                # 4. Write workspace outputs asynchronously
                children_dir = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "children"))
                agent_dir = os.path.join(children_dir, agent_name)
                await asyncio.to_thread(os.makedirs, agent_dir, exist_ok=True)
                
                app_py_path = os.path.join(agent_dir, "app.py")
                async with aiofiles.open(app_py_path, "w", encoding="utf-8") as f:
                    await f.write(rendered_app)
                    
                # Write requirements.txt
                reqs_path = os.path.join(agent_dir, "requirements.txt")
                async with aiofiles.open(reqs_path, "w", encoding="utf-8") as f:
                    for dep in ontology.dependencies:
                        await f.write(f"{dep}\n")
                    if not ontology.dependencies:
                        await f.write("fastapi>=0.110.0\nuvicorn>=0.27.0\npydantic>=2.0\n")
                        
                # Write README.md
                readme_path = os.path.join(agent_dir, "README.md")
                async with aiofiles.open(readme_path, "w", encoding="utf-8") as f:
                    await f.write(f"# {ontology.agent_name} Agent\n\n")
                    await f.write(f"## Role Summary\n{ontology.role_summary}\n\n")
                    await f.write(f"## Primary Capabilities\n")
                    for cap in ontology.primary_capabilities:
                        await f.write(f"- {cap}\n")
                    await f.write(f"\n## API Endpoints\n")
                    for ep in ontology.api_endpoints:
                        await f.write(f"- **{ep.method} {ep.path}** — {ep.summary} (ref: {ep.contract_ref})\n")
                        
                # Write contract_verified.json
                contract_path = os.path.join(agent_dir, "contract_verified.json")
                async with aiofiles.open(contract_path, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(ontology.model_dump(), indent=2))
                
                logger.info(f"Jinja2 files successfully synthesized in: {agent_dir}")
                
                # 5. Spawn child agent server utilizing asyncio.create_subprocess_exec()
                import sys
                cmd = [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(allocated_port)]
                try:
                    # Enforce logs directory initialization and persistent .gitkeep
                    logs_dir = os.path.join(SCRIPT_DIR, "logs")
                    os.makedirs(logs_dir, exist_ok=True)
                    with open(os.path.join(logs_dir, ".gitkeep"), "a"):
                        pass
                        
                    agent_id = ontology.agent_name.lower().replace("_", "")
                    log_file_path = os.path.join(logs_dir, f"{agent_id}_runtime.log")
                    
                    log_file = open(log_file_path, "ab", buffering=0)
                    
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        cwd=agent_dir,
                        stdout=log_file,
                        stderr=log_file,
                        creationflags=0x00000200 | 0x01000000 if os.name == 'nt' else 0, # CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB
                        close_fds=False,
                        env={**os.environ, "PYTHONUNBUFFERED": "1"}
                    )
                    await asyncio.sleep(2)
                    if process.returncode is not None:
                        logger.error(f"Spawned child agent uvicorn process (PID {process.pid}) EXITED IMMEDIATELY with code {process.returncode}!")
                    else:
                        logger.info(f"Spawned child agent uvicorn process (PID {process.pid}) is running on port {allocated_port}.")
                    log_file.close()
                except Exception as spawn_err:
                    logger.error(f"Failed to spawn uvicorn process for {ontology.agent_name}: {spawn_err}")
                    
                # 6. Append dynamically compiled agent status and port metadata to agent_registry.json ledger
                from registry_manager import register_agent
                await register_agent(ontology.agent_name, allocated_port, "ACTIVE")
                
                # 7. Fire dynamic proxy registration callback
                for callback in ON_COMPILE_SUCCESS_CALLBACKS:
                    try:
                        callback(ontology.agent_name, allocated_port, api_endpoints_enriched)
                    except Exception as cb_err:
                        logger.error(f"Failed to execute dynamic routing proxy callback: {cb_err}")
                        
                # 8. Yield final compile success token to dynamic UI listeners
                yield f"data: {json.dumps({'event': 'compile_success', 'port': allocated_port, 'agent_name': agent_name})}\n\n"
                return
                
            except OntologyValidationError as ova_err:
                prior_errors = ova_err.validation_errors
                prior_json = ova_err.raw_json or {}
                
                yield f"data: {json.dumps({
                    'event': 'verify_fail',
                    'round': round_num,
                    'errors': prior_errors
                })}\n\n"
                
                if round_num == self.MAX_ROUNDS:
                    # Final round failed: serialize final error and halt
                    yield f"data: {json.dumps({
                        'event': 'error',
                        'message': 'Genesis Orchestrator failed verification after 3 rounds.',
                        'errors': prior_errors
                    })}\n\n"
                    return
                else:
                    # Wait slightly before retrying for nice flow and api spacing
                    await asyncio.sleep(1)
            except Exception as exc:
                # Catch any unhandled/connection errors
                logger.error(f"Unexpected error in run_stream round {round_num}: {exc}")
                yield f"data: {json.dumps({
                    'event': 'error',
                    'message': f"Unexpected system error: {str(exc)}",
                    'errors': [{"type": "system_error", "msg": str(exc)}]
                })}\n\n"
                return

    def run(self, prompt: str, route_logic_blocks: Optional[list] = None, startup_logic_ast: Optional[str] = None) -> AgentOntology:
        """
        Synchronous blocking wrapper for standard execution or programmatic test suites.
        """
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If in a running event loop, execute via an task runner
            return asyncio.run_coroutine_threadsafe(self._run_async_wrapper(prompt, route_logic_blocks, startup_logic_ast), loop).result()
        else:
            return asyncio.run(self._run_async_wrapper(prompt, route_logic_blocks, startup_logic_ast))

    async def _run_async_wrapper(self, prompt: str, route_logic_blocks: Optional[list] = None, startup_logic_ast: Optional[str] = None) -> AgentOntology:
        citations = []
        prior_errors = None
        prior_json = None
        
        for round_num in range(1, self.MAX_ROUNDS + 1):
            try:
                raw_dict = await self._research_node(
                    prompt=prompt,
                    round_num=round_num,
                    citations=citations,
                    prior_errors=prior_errors,
                    prior_json=prior_json
                )
                if route_logic_blocks:
                    raw_dict["route_logic_blocks"] = route_logic_blocks
                if startup_logic_ast:
                    raw_dict["startup_logic_ast"] = startup_logic_ast
                citations = list(sorted(set(citations + raw_dict.get("research_citations", []))))
                return self._verification_node(raw_dict, round_num)
            except OntologyValidationError as ova_err:
                prior_errors = ova_err.validation_errors
                prior_json = ova_err.raw_json
                if round_num == self.MAX_ROUNDS:
                    raise ova_err
                await asyncio.sleep(0.5)
