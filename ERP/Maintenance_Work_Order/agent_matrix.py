"""
Component C — AI Support & Ops Agent Matrix.

Dedicated, API-key-gated endpoints for LLM-driven autonomous agents:

    /api/agent/sentry/logs          GET   tenant-filtered application logs
    /api/agent/sentry/apply-patch   POST  guarded code-patch (backup/compile/rollback)
    /api/agent/concierge/context    GET   tenant schema / config / active hooks
    /api/agent/concierge/chat       POST  context-rich troubleshooting responder
    /api/agent/provision/tenant     POST  provision tenant DB + seed + (optional) SSL

Security model
--------------
Every route in this router requires the ``X-Agent-Matrix-Key`` header to match the
``AGENT_MATRIX_API_KEY`` environment variable (constant-time compare; fail-closed
if unset). The high-blast-radius apply-patch route additionally requires a SEPARATE
``X-Sentry-Patch-Key`` matching ``AGENT_SENTRY_PATCH_KEY`` (per the plan's CAUTION),
restricts writes to .py files inside the app root, and audit-logs every mutation.
"""

import os
import re
import sys
import json
import time
import hmac
import shutil
import logging
import subprocess
import py_compile
from logging.handlers import RotatingFileHandler
from typing import Optional

# Official Anthropic SDK is the preferred client. If it isn't installed we fall
# back to a raw httpx call against the Messages API (same wire contract).
try:
    import anthropic
    _HAVE_ANTHROPIC_SDK = True
except ImportError:
    anthropic = None
    _HAVE_ANTHROPIC_SDK = False

from fastapi import APIRouter, HTTPException, Depends, Header, Request, Query
from pydantic import BaseModel, Field

from local_db import (
    get_db_connection_for_tenant,
    get_default_db_connection,
    get_current_tenant,
    _validate_tenant_id,
    DEFAULT_TENANT_ID,
    DB_PATH,
)
import plugin_manager

logger = logging.getLogger("MaintenanceBackend.AgentMatrix")

_here = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(_here, "logs")
APP_LOG_FILE = os.path.join(LOGS_DIR, "app.log")
AUDIT_LOG_FILE = os.path.join(LOGS_DIR, "agent_audit.log")
PATCH_BACKUP_DIR = os.path.join(_here, "backups", "sentry")

# --- Secrets (fail-closed: routes are disabled until these are configured) ---
AGENT_MATRIX_API_KEY = os.environ.get("AGENT_MATRIX_API_KEY", "").strip()
AGENT_SENTRY_PATCH_KEY = os.environ.get("AGENT_SENTRY_PATCH_KEY", "").strip()
# SSL/Nginx side effects are opt-in; on a box without certbot/nginx this stays off.
PROVISION_ENABLE_SSL = os.environ.get("AGENT_PROVISION_ENABLE_SSL", "").strip() in ("1", "true", "True")
PROVISION_WEBROOT = os.environ.get("AGENT_PROVISION_WEBROOT", "/opt/erp/frontend").strip()

# --- Concierge LLM (Anthropic Claude) ---
# NOTE: the requested 'claude-3-5-sonnet' is retired and would 404; we default to
# the current, most capable model and make it overridable. Set AGENT_CONCIERGE_MODEL
# to e.g. 'claude-sonnet-4-6' for the current Sonnet tier if cost is a concern.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
CONCIERGE_MODEL = os.environ.get("AGENT_CONCIERGE_MODEL", "").strip() or "claude-opus-4-8"

_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Tenant-tagged file logging (so /sentry/logs can filter by tenant)
# ---------------------------------------------------------------------------
class _TenantLogFilter(logging.Filter):
    """Stamp every record with the tenant bound to the current context."""
    def filter(self, record):
        try:
            record.tenant = get_current_tenant() or "-"
        except Exception:
            record.tenant = "-"
        return True


def attach_file_logging(target_logger: logging.Logger) -> None:
    """Idempotently add a rotating, tenant-tagged file handler to ``target_logger``.
    stdout logging is left untouched (Docker rotation). Called once from backend boot."""
    for h in target_logger.handlers:
        if getattr(h, "_agent_matrix_file", False):
            return
    os.makedirs(LOGS_DIR, exist_ok=True)
    handler = RotatingFileHandler(APP_LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    handler._agent_matrix_file = True
    handler.addFilter(_TenantLogFilter())
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [tenant=%(tenant)s] %(name)s %(levelname)s %(message)s"
    ))
    target_logger.addHandler(handler)


def _audit(action: str, detail: dict) -> None:
    """Append-only audit trail for agent mutations (best-effort; never raises)."""
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{stamp} {action} {detail}\n")
    except Exception as e:
        logger.error("[AUDIT] Failed to write audit record for %s: %s", action, e)


# ---------------------------------------------------------------------------
# Security dependencies
# ---------------------------------------------------------------------------
def verify_agent_matrix_key(x_agent_matrix_key: Optional[str] = Header(None, alias="X-Agent-Matrix-Key")):
    if not AGENT_MATRIX_API_KEY:
        raise HTTPException(status_code=503, detail="Agent Matrix disabled: AGENT_MATRIX_API_KEY not configured.")
    if not x_agent_matrix_key or not hmac.compare_digest(x_agent_matrix_key, AGENT_MATRIX_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing Agent Matrix API key.")
    return True


def verify_sentry_patch_key(x_sentry_patch_key: Optional[str] = Header(None, alias="X-Sentry-Patch-Key")):
    """Separate, stronger gate for the high-blast-radius patch endpoint."""
    if not AGENT_SENTRY_PATCH_KEY:
        raise HTTPException(status_code=503, detail="Patch application disabled: AGENT_SENTRY_PATCH_KEY not configured.")
    if not x_sentry_patch_key or not hmac.compare_digest(x_sentry_patch_key, AGENT_SENTRY_PATCH_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing Sentry patch key.")
    return True


def verify_concierge_auth(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_agent_matrix_key: Optional[str] = Header(None, alias="X-Agent-Matrix-Key"),
):
    """Dual-auth gate for the in-app concierge endpoints.

    Accepts EITHER a valid in-app Bearer JWT (so logged-in tenant users can reach
    the concierge from the ERP UI) OR the Agent Matrix API key (so autonomous
    agents keep working). The JWT is tried first; if it is absent or invalid we
    fall back to the API-key check.
    """
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        # Local import: maintenance_backend imports this module's agent_router,
        # so importing it at load time would create a circular dependency.
        from maintenance_backend import verify_jwt_token
        from fastapi.security import HTTPAuthorizationCredentials
        # A Bearer token was presented: verify it and let any HTTPException
        # (Token Expired / Token Revoked / verification failure) propagate to
        # the client. We do NOT fall back to the API key for a bad JWT.
        return verify_jwt_token(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        )

    return verify_agent_matrix_key(x_agent_matrix_key)


agent_router = APIRouter(
    prefix="/api/agent",
    tags=["agent-matrix"],
)


def _resolve_tenant(request: Request, tenant_id: Optional[str]) -> str:
    """Resolve the effective tenant: explicit param > request.state (subdomain) >
    bound context > default. Validated; raises 400 on a malformed explicit id."""
    candidate = tenant_id or getattr(request.state, "tenant_id", None) or get_current_tenant() or DEFAULT_TENANT_ID
    if candidate == DEFAULT_TENANT_ID:
        return DEFAULT_TENANT_ID
    try:
        return _validate_tenant_id(candidate)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid tenant_id: {candidate!r}")


# ===========================================================================
# 1. SENTRY AGENT
# ===========================================================================
@agent_router.get("/sentry/logs", dependencies=[Depends(verify_agent_matrix_key)])
def sentry_logs(
    request: Request,
    tenant_id: Optional[str] = Query(None, description="Tenant to filter logs by; defaults to request context."),
    lines: int = Query(500, ge=1, le=5000),
):
    """Return the last N application-log lines, filtered to the tenant. The
    'default' tenant (admin console) receives the unfiltered tail."""
    tenant = _resolve_tenant(request, tenant_id)
    if not os.path.isfile(APP_LOG_FILE):
        return {"status": "success", "tenant_id": tenant, "lines": [], "note": "Log file not yet created."}

    try:
        with open(APP_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except Exception as e:
        logger.error("[SENTRY] Failed to read log file: %s", e)
        raise HTTPException(status_code=500, detail="Failed to read application logs.")

    if tenant == DEFAULT_TENANT_ID:
        selected = all_lines
    else:
        tag = f"[tenant={tenant}]"
        selected = [ln for ln in all_lines if tag in ln]

    tail = [ln.rstrip("\n") for ln in selected[-lines:]]
    return {"status": "success", "tenant_id": tenant, "count": len(tail), "lines": tail}


class PatchRequest(BaseModel):
    file_path: str = Field(..., description="Path to the target .py file, relative to the app root.")
    content: str = Field(..., description="Full new file content (deterministic full-file replacement).")
    reason: Optional[str] = Field(None, description="Why this patch is being applied (audited).")


def _safe_app_py_path(file_path: str) -> str:
    """Resolve file_path within the app root and enforce a .py extension."""
    root = os.path.realpath(_here)
    raw = file_path if os.path.isabs(file_path) else os.path.join(root, file_path)
    resolved = os.path.realpath(raw)
    if os.path.commonpath([root, resolved]) != root:
        raise HTTPException(status_code=400, detail="Path traversal denied: target escapes application root.")
    if not resolved.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only .py files may be patched (compile verification requires Python).")
    return resolved


@agent_router.post("/sentry/apply-patch", dependencies=[Depends(verify_agent_matrix_key), Depends(verify_sentry_patch_key)])
def sentry_apply_patch(payload: PatchRequest, request: Request):
    """Backup -> write -> compile-verify -> rollback-on-failure. Restricted to .py
    files inside the app root. Every attempt and outcome is audit-logged."""
    target = _safe_app_py_path(payload.file_path)
    if not os.path.isfile(target):
        raise HTTPException(status_code=404, detail="Target file does not exist; refusing to create new files via patch.")

    with open(target, "rb") as f:
        original_bytes = f.read()

    os.makedirs(PATCH_BACKUP_DIR, exist_ok=True)
    backup_path = os.path.join(PATCH_BACKUP_DIR, f"{os.path.basename(target)}.{int(time.time())}.bak")
    with open(backup_path, "wb") as f:
        f.write(original_bytes)

    _audit("PATCH_ATTEMPT", {"file": target, "backup": backup_path, "reason": payload.reason})

    try:
        with open(target, "w", encoding="utf-8", newline="") as f:
            f.write(payload.content)
        # Syntax gate: compile the modified file. doraise -> PyCompileError on failure.
        py_compile.compile(target, doraise=True)
    except py_compile.PyCompileError as ce:
        with open(target, "wb") as f:
            f.write(original_bytes)
        _audit("PATCH_ROLLBACK", {"file": target, "error": str(ce)})
        logger.error("[SENTRY] Patch to %s failed compile; rolled back. %s", target, ce)
        return {"status": "rolled_back", "file_path": target, "error": f"Syntax verification failed: {ce}", "backup": backup_path}
    except Exception as e:
        with open(target, "wb") as f:
            f.write(original_bytes)
        _audit("PATCH_ROLLBACK", {"file": target, "error": str(e)})
        logger.error("[SENTRY] Patch to %s failed; rolled back. %s", target, e)
        raise HTTPException(status_code=500, detail=f"Patch failed and was rolled back: {e}")

    _audit("PATCH_APPLIED", {"file": target, "backup": backup_path, "bytes": len(payload.content)})
    logger.info("[SENTRY] Patch applied and verified for %s (backup at %s)", target, backup_path)
    return {"status": "applied", "file_path": target, "backup": backup_path,
            "note": "Compiled successfully. A process reload is required for the change to take effect."}


# ===========================================================================
# 2. CUSTOMER CONCIERGE AGENT
# ===========================================================================
def _tenant_schema(conn) -> dict:
    """Map of table -> [columns] for the tenant database."""
    tables = {}
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall():
        cols = [row[1] for row in conn.execute(f"PRAGMA table_info('{name}')").fetchall()]
        tables[name] = cols
    return tables


@agent_router.get("/concierge/context", dependencies=[Depends(verify_concierge_auth)])
def concierge_context(request: Request, tenant_id: Optional[str] = Query(None)):
    """Dump schema definitions, active plugin hooks, and core parameters so an LLM
    agent can understand the tenant's specific setup."""
    tenant = _resolve_tenant(request, tenant_id)
    conn = get_db_connection_for_tenant(tenant)
    try:
        schema = _tenant_schema(conn)
    finally:
        conn.close()

    active_hooks = plugin_manager.list_tenant_hooks(tenant) if tenant != DEFAULT_TENANT_ID else []
    return {
        "status": "success",
        "tenant_id": tenant,
        "config": {
            "is_default": tenant == DEFAULT_TENANT_ID,
            "supported_hooks": list(plugin_manager.CORE_HOOKS),
            "ssl_provisioning_enabled": PROVISION_ENABLE_SSL,
        },
        "schema": schema,
        "table_count": len(schema),
        "active_hooks": active_hooks,
    }


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    tenant_id: Optional[str] = None


def _call_claude(system_prompt: str, user_message: str) -> str:
    """Query Claude with the official SDK, falling back to a raw httpx call if the
    SDK isn't installed. Returns the concatenated assistant text. Raises on failure;
    the caller maps that to a 502."""
    if _HAVE_ANTHROPIC_SDK:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=CONCIERGE_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return "".join(
            b.text for b in resp.content if getattr(b, "type", None) == "text"
        ).strip()

    # Fallback: raw Messages API call (httpx is already an app dependency).
    import httpx
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": CONCIERGE_MODEL,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        },
        timeout=30.0,
    )
    r.raise_for_status()
    data = r.json()
    return "".join(
        b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
    ).strip()


@agent_router.post("/concierge/chat", dependencies=[Depends(verify_concierge_auth)])
def concierge_chat(payload: ChatRequest, request: Request):
    """Answer a tenant support query with Claude, grounded in the tenant's real
    schema and active plugin hooks. Fail-closed: returns 503 if ANTHROPIC_API_KEY
    is not configured (no silent degraded path)."""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="Concierge LLM disabled: ANTHROPIC_API_KEY not configured.")

    tenant = _resolve_tenant(request, payload.tenant_id)
    conn = get_db_connection_for_tenant(tenant)
    try:
        schema = _tenant_schema(conn)
    finally:
        conn.close()
    active_hooks = plugin_manager.list_tenant_hooks(tenant) if tenant != DEFAULT_TENANT_ID else []

    system_prompt = (
        "You are the Customer Concierge support agent for a multi-tenant Maintenance "
        f"Work Order (MWO) ERP system. You are assisting tenant '{tenant}'.\n\n"
        "Ground every answer in THIS tenant's actual configuration below. Do not "
        "invent tables, columns, or features that are not listed. If the question "
        "falls outside this system's scope, say so plainly.\n\n"
        f"Active database tables and their columns (JSON):\n{json.dumps(schema)}\n\n"
        f"Active tenant plugin hooks: {active_hooks or 'none'}\n"
        f"Supported lifecycle hooks: {list(plugin_manager.CORE_HOOKS)}\n\n"
        "Reply with concise, actionable troubleshooting steps.\n\n"
        "Do not output raw source code, python scripts, file layouts, database "
        "initialization scripts, or SQL query statements under any circumstances. "
        "If the user asks for code, configuration files, or database schemas in a "
        "structural format (such as SQL DDL), politely decline and instruct them "
        "conceptually on how to perform the action using the ERP UI."
    )

    try:
        answer = _call_claude(system_prompt, payload.query)
    except Exception as e:
        logger.error("[CONCIERGE] Claude call failed for tenant '%s': %s", tenant, e)
        raise HTTPException(status_code=502, detail=f"Upstream LLM error: {e}")

    return {
        "status": "success",
        "tenant_id": tenant,
        "query": payload.query,
        "model": CONCIERGE_MODEL,
        "response": answer,
        "grounding": {"table_count": len(schema), "active_hooks": active_hooks},
    }


# ===========================================================================
# 3. PROVISIONING AGENT (Admin)
# ===========================================================================
class ProvisionRequest(BaseModel):
    tenant_id: str = Field(..., description="DNS-label tenant slug.")
    domain: str = Field(..., description="Fully-qualified subdomain, e.g. clienta.domain.com.")
    admin_email: str = Field(..., description="Contact email for the SSL certificate.")


def _seed_tenant_baseline(conn) -> dict:
    """Idempotently seed standard departments, SKU categories, and the default
    ERP-1000 administrator into a freshly-provisioned tenant database."""
    import bcrypt
    cur = conn.cursor()

    departments = [
        ("DEPT-001", "Dispatch Command"),
        ("DEPT-002", "Field Maintenance"),
        ("DEPT-003", "IT Infrastructure"),
        ("DEPT-004", "Procurement"),
    ]
    cur.executemany("INSERT OR IGNORE INTO erp_departments (id, name) VALUES (?, ?)", departments)

    categories = [
        ("CAT-MECH", "Mechanical"),
        ("CAT-ELEC", "Electrical"),
        ("CAT-CONS", "Consumables"),
        ("CAT-SAFE", "Safety"),
    ]
    cur.executemany("INSERT OR IGNORE INTO erp_categories (id, name) VALUES (?, ?)", categories)

    cur.execute("SELECT 1 FROM erp_employees WHERE id = 'ERP-1000'")
    seeded_admin = False
    if not cur.fetchone():
        admin_hash = bcrypt.hashpw("1234".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cur.execute(
            "INSERT INTO erp_employees (id, name, role, pin_hash, is_active, department_id) "
            "VALUES ('ERP-1000', 'System Administrator', 'ADMINISTRATOR', ?, 1, 'DEPT-003')",
            (admin_hash,),
        )
        seeded_admin = True

    conn.commit()
    return {"departments": len(departments), "categories": len(categories), "admin_seeded": seeded_admin}


def _run_cmd(cmd: list) -> dict:
    """Run a subprocess with an explicit arg list (never shell=True). Returns a
    structured result; never raises on non-zero exit."""
    if not shutil.which(cmd[0]):
        return {"ran": False, "skipped": f"binary '{cmd[0]}' not found on PATH"}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return {"ran": True, "returncode": proc.returncode,
                "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}
    except Exception as e:
        return {"ran": True, "error": str(e)}


@agent_router.post("/provision/tenant", status_code=201, dependencies=[Depends(verify_agent_matrix_key)])
def provision_tenant(payload: ProvisionRequest):
    """Instantiate the tenant database (schema cloned from production via the
    local_db resolver), seed the master catalog + ERP-1000 admin, then optionally
    issue an SSL cert and reload Nginx (gated by AGENT_PROVISION_ENABLE_SSL)."""
    try:
        tenant = _validate_tenant_id(payload.tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid tenant_id: {payload.tenant_id!r}")
    if tenant == DEFAULT_TENANT_ID:
        raise HTTPException(status_code=400, detail="Refusing to provision the reserved 'default' tenant.")
    if not _DOMAIN_RE.match(payload.domain):
        raise HTTPException(status_code=400, detail=f"Invalid domain: {payload.domain!r}")
    if not _EMAIL_RE.match(payload.admin_email):
        raise HTTPException(status_code=400, detail=f"Invalid admin_email: {payload.admin_email!r}")

    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=503, detail="Production template database unavailable; cannot clone tenant schema.")

    # 1+2. Instantiate + clone schema (first connection bootstraps the file), then seed.
    conn = get_db_connection_for_tenant(tenant)
    try:
        seed_summary = _seed_tenant_baseline(conn)
    except Exception as e:
        conn.close()
        logger.error("[PROVISION] Seeding failed for tenant '%s': %s", tenant, e)
        raise HTTPException(status_code=500, detail=f"Tenant DB created but seeding failed: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    _audit("PROVISION_TENANT", {"tenant": tenant, "domain": payload.domain, "seed": seed_summary})
    logger.info("[PROVISION] Tenant '%s' provisioned and seeded: %s", tenant, seed_summary)

    # 3. SSL + Nginx (opt-in side effects).
    ssl_result = {"ran": False, "skipped": "AGENT_PROVISION_ENABLE_SSL is off"}
    nginx_result = {"ran": False, "skipped": "AGENT_PROVISION_ENABLE_SSL is off"}
    if PROVISION_ENABLE_SSL:
        ssl_result = _run_cmd([
            "certbot", "certonly", "--webroot", "-w", PROVISION_WEBROOT,
            "-d", payload.domain, "--non-interactive", "--agree-tos", "-m", payload.admin_email,
        ])
        # Validate config before reloading so a bad cert path can't take Nginx down.
        test = _run_cmd(["nginx", "-t"])
        if test.get("ran") and test.get("returncode", 1) == 0:
            nginx_result = _run_cmd(["nginx", "-s", "reload"])
        else:
            nginx_result = {"ran": False, "skipped": "nginx -t failed or nginx not present", "test": test}
        _audit("PROVISION_SSL", {"tenant": tenant, "domain": payload.domain, "ssl": ssl_result, "nginx": nginx_result})

    return {
        "status": "success",
        "tenant_id": tenant,
        "domain": payload.domain,
        "database": f"tenant_{tenant}.db",
        "seed": seed_summary,
        "ssl": ssl_result,
        "nginx_reload": nginx_result,
    }
