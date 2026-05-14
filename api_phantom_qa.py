import os
import re
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
qa_router = APIRouter(prefix="/api/v1/qa/engine", tags=["Phantom QA Enforcement Matrix"])

FACTORY_ROOT = Path(os.getcwd()).resolve()

class AuditPayload(BaseModel):
    target_path: str

class PreflightPayload(BaseModel):
    content: str
    target_path: str

def _read_physical_matrix(target_path: str) -> str:
    """Utilizes the established Zero-Trust jail to securely read the AST payload."""
    safe_path = (FACTORY_ROOT / target_path).resolve()
    
    if not str(safe_path).startswith(str(FACTORY_ROOT)):
        logger.error(f"[SECURITY FATAL] QA Path traversal blocked: {target_path}")
        raise HTTPException(status_code=403, detail="Zero-Trust Violation: Path Traversal.")
        
    if not safe_path.exists() or not safe_path.is_file():
        raise HTTPException(status_code=404, detail="Target matrix not found on physical disk.")
    
    with open(safe_path, 'r', encoding='utf-8') as f:
        return f.read()

@qa_router.post("/audit")
async def execute_structural_audit(payload: AuditPayload):
    """
    Phantom QA Static Code Analysis Pipeline.
    Relentlessly enforces the Absolute Architectural Doctrine prior to Biological Operator review.
    """
    code_content = _read_physical_matrix(payload.target_path)
    violations = []

    # Doctrine 1: Catch-all fallback routes forbidden
    if re.search(r'\{.*?:path\}', code_content) or 'catch_all' in code_content:
        violations.append("FATAL: Catch-all routing detected. Backend must strictly return 404 JSON.")

    # Doctrine 2: StaticFiles mounting forbidden
    if 'StaticFiles' in code_content:
        violations.append("FATAL: StaticFiles mounting detected. Frontend assets must be decoupled.")

    # Doctrine 3: Mode B I/O ThreadPoolExecutor anti-pattern
    if 'ThreadPoolExecutor' in code_content:
        violations.append("FATAL: ThreadPoolExecutor detected in LLM matrix. Must utilize native asyncio.gather().")

    # Doctrine 4: Legacy fpdf2 spatial violation
    if 'ln=False' in code_content or 'ln=True' in code_content:
        violations.append("FATAL: Legacy fpdf2 boolean detected. Must implement explicit new_x/new_y spatial markers.")

    if violations:
        logger.warning(f"[PHANTOM QA] Audit REJECTED for {payload.target_path}. Fractures detected.")
        return {
            "status": "REJECTED", 
            "target": payload.target_path, 
            "violations": violations,
            "biological_authorization_required": True
        }

    logger.info(f"[PHANTOM QA] Audit PASSED for {payload.target_path}.")
    return {
        "status": "PASSED", 
        "target": payload.target_path, 
        "message": "Absolute Architectural Doctrine verified. Awaiting Biological Operator deployment authorization."
    }

async def perform_pre_flight_audit(payload: PreflightPayload):
    import ast
    violations = []
    code_content = payload.content

    try:
        tree = ast.parse(code_content)
    except SyntaxError as e:
        logger.warning(f"[PHANTOM QA] Pre-Flight REJECTED for {payload.target_path}. Invalid Python Syntax: {str(e)}")
        return {"status": "REJECTED", "violations": [f"FATAL: Invalid Python Syntax. Cannot parse AST: {str(e)}"]}

    # Rule 1 (Framework Ban)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [n.name for n in getattr(node, 'names', [])]
            module = getattr(node, 'module', '') or ''
            
            for name in names + [module]:
                if name.startswith('flask') or name.startswith('django'):
                    violations.append("FATAL: Synchronous frameworks are permanently forbidden. Strict FastAPI compliance required.")
                    break # Avoid duplicate warnings per node

    # Rule 2 (Async Enforcer)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Check if it has routing decorators
            has_route_decorator = False
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                    if decorator.func.attr in ["get", "post", "put", "delete", "patch"]:
                        has_route_decorator = True
                        break
            
            if has_route_decorator:
                violations.append("FATAL: FastAPI route detected without 'async def'. Blocking I/O is forbidden.")

    if violations:
        logger.warning(f"[PHANTOM QA] Pre-Flight REJECTED for {payload.target_path}.")
        return {"status": "REJECTED", "violations": violations}

    logger.info(f"[PHANTOM QA] Pre-Flight PASSED for {payload.target_path}.")
    return {"status": "APPROVED"}

@qa_router.post("/pre-flight")
async def execute_pre_flight_audit(payload: PreflightPayload):
    """
    Zero-Trust In-Memory Scanner.
    Evaluates LLM payloads against the Factory Doctrine BEFORE granting disk I/O authorization.
    """
    return await perform_pre_flight_audit(payload)


import ast
import asyncio
import httpx

class SastDastPayload(BaseModel):
    target_path: str
    target_url: str

def _execute_sast_scan(file_path: Path) -> list:
    """
    Static Code Analysis (SAST).
    Uses native ast module to identify FastAPI routes and check for security dependencies.
    """
    discovered_routes = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
        tree = ast.parse(code)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                route_path = None
                method = None
                secured = False
                
                # Check decorators for @app.get, @app.post, etc.
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                        if decorator.func.attr in ["get", "post", "put", "delete", "patch"]:
                            method = decorator.func.attr.upper()
                            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                                route_path = decorator.args[0].value
                
                if route_path and method:
                    # Check arguments for Depends() or schema payloads
                    for arg in node.args.args + node.args.kwonlyargs:
                        # Simple heuristic: if type annotation exists or default value uses Depends
                        if arg.annotation or (hasattr(arg, 'default') and isinstance(arg.default, ast.Call) and getattr(arg.default.func, 'id', '') == 'Depends'):
                            secured = True
                            
                    discovered_routes.append({
                        "path": route_path,
                        "method": method,
                        "secured": secured,
                        "function": node.name
                    })
    except Exception as e:
        logger.error(f"[SAST] Parsing failed for {file_path}: {e}")
        
    return discovered_routes

async def _execute_dast_fuzzing(target_url: str, routes: list) -> list:
    """
    Adversarial Fuzzing (DAST).
    Auto-generates hostile payloads for discovered routes.
    """
    anomalies = []
    async with httpx.AsyncClient(base_url=target_url, timeout=3.0) as client:
        for route in routes:
            path = route["path"]
            method = route["method"]
            
            # Skip wildcards/path params for basic fuzzing to avoid 404 spam
            if "{" in path:
                continue
                
            hostile_payloads = [
                {}, # Empty JSON
                {"invalid_key": "malicious_data"}, # Schema mismatch
                {"payload": "A" * 10000} # Oversized string
            ]
            
            headers = {"Authorization": "Bearer BAD_TOKEN"}
            
            try:
                for payload in hostile_payloads:
                    # Dynamically route the HTTP method. Omit JSON body for GET/DELETE.
                    if method in ["GET", "DELETE"]:
                        res = await client.request(method, path, headers=headers)
                    else:
                        res = await client.request(method, path, json=payload, headers=headers)
                        
                    if res.status_code >= 500:
                        anomalies.append({
                            "route": path,
                            "method": method,
                            "trigger_payload": payload if method not in ["GET", "DELETE"] else "N/A",
                            "status_code": res.status_code,
                            "error": res.text[:200]
                        })
                    
                    # Break loop early for GET/DELETE to prevent redundant non-payload requests
                    if method in ["GET", "DELETE"]:
                        break
                        
            except Exception as e:
                anomalies.append({
                    "route": path,
                    "method": method,
                    "error": str(e)
                })
                break # Abort further payload testing on this route if connection drops
    return anomalies

@qa_router.post("/sast-dast-matrix")
async def execute_sast_dast_matrix(payload: SastDastPayload):
    """
    Combined SAST/DAST Execution Pipeline with Memory Bridge.
    """
    target_dir = (FACTORY_ROOT / payload.target_path.lstrip("/\\")).resolve()
    
    if not str(target_dir).startswith(str(FACTORY_ROOT)):
        raise HTTPException(status_code=403, detail="Path Traversal Blocked.")
        
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="Target path not found.")

    all_routes = []
    sast_results = {}
    
    # 1. Execute SAST on all Python files in target directory
    if target_dir.is_file() and target_dir.suffix == ".py":
        routes = _execute_sast_scan(target_dir)
        if routes:
            all_routes.extend(routes)
            sast_results[str(target_dir.relative_to(FACTORY_ROOT))] = routes
    elif target_dir.is_dir():
        for py_file in target_dir.rglob("*.py"):
            routes = _execute_sast_scan(py_file)
            if routes:
                all_routes.extend(routes)
                sast_results[str(py_file.relative_to(FACTORY_ROOT))] = routes

    # 2. Execute DAST against discovered routes
    logger.info(f"[PHANTOM QA] Initiating DAST simulation against {len(all_routes)} discovered routes at {payload.target_url}")
    dast_anomalies = await _execute_dast_fuzzing(payload.target_url, all_routes)

    # 3. The Memory Bridge (Error Traceback to LocalStorage formatted JSON)
    memory_bridge_payload = None
    if dast_anomalies:
        logger.error(f"[PHANTOM QA] DAST Fuzzing triggered {len(dast_anomalies)} anomalies. Engaging Memory Bridge.")
        
        # Format the memory bridge payload for the React frontend
        memory_bridge_payload = {
            "target_path": payload.target_path,
            "timestamp": asyncio.get_event_loop().time(),
            "error_log": dast_anomalies,
            "sast_context": sast_results
        }
        
    return {
        "status": "COMPLETED",
        "sast_routes_discovered": len(all_routes),
        "dast_anomalies_detected": len(dast_anomalies),
        "memory_bridge": memory_bridge_payload
    }
