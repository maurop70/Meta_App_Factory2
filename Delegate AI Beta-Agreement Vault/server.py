"""
server.py — Delegate AI Beta-Agreement Vault — FastAPI Backend
================================================================
Port: 5007 | Fernet AES-128 Encrypted | Leitner Alert System
Antigravity-AI | Project: DAI-2026-A1F3E7
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
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from cryptography.fernet import Fernet

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("VaultAPI")

# ── Config ────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "vault_data")
os.makedirs(DATA_DIR, exist_ok=True)

VAULT_DB = os.path.join(DATA_DIR, "vault.json")
ALERTS_DB = os.path.join(DATA_DIR, "alerts.json")
AUDIT_LOG = os.path.join(DATA_DIR, "audit_trail.jsonl")
KEY_FILE = os.path.join(DATA_DIR, ".vault_key")

# ── Fernet AES-128 Encryption ────────────────────────────────

def _get_or_create_key() -> bytes:
    """Load or generate a Fernet key (AES-128-CBC under the hood)."""
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(key)
    logger.info("Generated new Fernet encryption key")
    return key

FERNET_KEY = _get_or_create_key()
cipher = Fernet(FERNET_KEY)


def encrypt(plaintext: str) -> str:
    """Encrypt a string using Fernet AES-128."""
    return cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    """Decrypt a Fernet token back to plaintext."""
    return cipher.decrypt(token.encode("utf-8")).decode("utf-8")


# ── Vault Storage ─────────────────────────────────────────────

def _load_vault() -> dict:
    if os.path.exists(VAULT_DB):
        with open(VAULT_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"agreements": {}, "metadata": {"created": _now(), "version": "1.0.0"}}


def _save_vault(data: dict):
    with open(VAULT_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── Alert Storage (Leitner System) ────────────────────────────

def _load_alerts() -> list:
    if os.path.exists(ALERTS_DB):
        with open(ALERTS_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_alerts(alerts: list):
    with open(ALERTS_DB, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2)


# ── Audit Trail ───────────────────────────────────────────────

def _audit(action: str, details: dict):
    """Append-only audit trail — immutable log."""
    entry = {
        "timestamp": _now(),
        "action": action,
        "details": details,
        "hash": hashlib.sha256(json.dumps(details, sort_keys=True).encode()).hexdigest()[:16],
    }
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    logger.info(f"AUDIT: {action} [{entry['hash']}]")
    return entry


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Leitner Alert Engine ──────────────────────────────────────
# Alerts have "boxes" (1-5). Unresolved alerts escalate box level
# every cycle. Higher box = more urgent. Only manual dismiss clears.

LEITNER_MAX_BOX = 5

def _escalate_alerts():
    """Move all unresolved alerts up one Leitner box."""
    alerts = _load_alerts()
    escalated = 0
    for alert in alerts:
        if alert.get("status") == "active" and alert.get("box", 1) < LEITNER_MAX_BOX:
            alert["box"] = alert.get("box", 1) + 1
            alert["last_escalated"] = _now()
            escalated += 1
    if escalated > 0:
        _save_alerts(alerts)
        logger.info(f"Leitner: Escalated {escalated} alerts")
    return escalated


def _create_alert(alert_type: str, description: str, source: str = "system") -> dict:
    """Create a new security alert in Leitner Box 1."""
    alert = {
        "id": hashlib.sha256(f"{_now()}{description}".encode()).hexdigest()[:12],
        "type": alert_type,
        "description": description,
        "source": source,
        "box": 1,
        "status": "active",
        "created": _now(),
        "last_escalated": _now(),
        "dismissed_at": None,
    }
    alerts = _load_alerts()
    alerts.append(alert)
    _save_alerts(alerts)
    _audit("ALERT_CREATED", {"alert_id": alert["id"], "type": alert_type, "box": 1})
    return alert


# ── Supabase Vector Memory Cross-Reference ───────────────────

def _cross_reference_ledger(agreement_id: str, content_hash: str) -> dict:
    """
    Active Audit Hook: Cross-references a vault transaction against
    the Supabase Vector Memory for duplicate or conflicting entries.
    """
    result = {"match_found": False, "similarity": 0.0, "action": "PROCEED"}

    try:
        # Try importing the memory service for vector comparison
        sys.path.insert(0, os.path.join(SCRIPT_DIR, "..", "Project_Aether"))
        from memory_service import MemoryService
        ms = MemoryService()
        check = ms.pre_flight_check(f"agreement:{agreement_id}:{content_hash}")
        if check.get("mode") == "IMPORT_REFACTOR":
            result = {
                "match_found": True,
                "similarity": check.get("similarity", 0.0),
                "action": "REVIEW_REQUIRED",
                "existing_pattern": check.get("existing_description", ""),
            }
            _create_alert(
                "DUPLICATE_AGREEMENT",
                f"Agreement {agreement_id} matches existing pattern (sim={check.get('similarity', 0):.2f})",
                source="audit_hook",
            )
    except (ImportError, Exception) as e:
        logger.warning(f"Vector cross-reference unavailable: {e}")
        result["note"] = "Vector memory offline — proceeding without cross-reference"

    _audit("CROSS_REFERENCE", {"agreement_id": agreement_id, "result": result})
    return result


# ── FastAPI App ───────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Delegate AI Beta-Agreement Vault starting on port 5007")
    _escalate_alerts()  # Escalate unresolved alerts on startup
    yield
    logger.info("Vault shutting down")

app = FastAPI(
    title="Delegate AI Beta-Agreement Vault",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5008", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────────────────

class EncryptRequest(BaseModel):
    agreement_id: str
    content: str
    party_a: str = ""
    party_b: str = ""
    agreement_type: str = "general"

class RetrieveRequest(BaseModel):
    agreement_id: str

class DismissAlertRequest(BaseModel):
    alert_id: str
    dismissed_by: str = "operator"
    reason: str = ""


# ── Routes ────────────────────────────────────────────────────

@app.get("/health")
def health():
    vault = _load_vault()
    alerts = _load_alerts()
    active_alerts = [a for a in alerts if a["status"] == "active"]
    critical_alerts = [a for a in active_alerts if a.get("box", 1) >= 4]
    return {
        "status": "healthy" if not critical_alerts else "warning",
        "service": "Delegate AI Beta-Agreement Vault",
        "version": "1.0.0",
        "project_id": "DAI-2026-A1F3E7",
        "port": 5007,
        "encryption": "Fernet AES-128",
        "agreements_stored": len(vault.get("agreements", {})),
        "active_alerts": len(active_alerts),
        "critical_alerts": len(critical_alerts),
        "leitner_max_box": LEITNER_MAX_BOX,
        "timestamp": _now(),
    }


@app.post("/vault/encrypt")
def vault_encrypt(req: EncryptRequest):
    """Encrypt and store an agreement in the vault."""
    vault = _load_vault()

    # Encrypt the content
    encrypted_content = encrypt(req.content)
    content_hash = hashlib.sha256(req.content.encode()).hexdigest()[:16]

    # Active Audit: cross-reference against vector memory
    xref = _cross_reference_ledger(req.agreement_id, content_hash)

    if xref.get("action") == "REVIEW_REQUIRED":
        _create_alert(
            "REVIEW_REQUIRED",
            f"Agreement '{req.agreement_id}' flagged for review — similar entry exists",
            source="vault_encrypt",
        )

    # Store encrypted agreement
    entry = {
        "encrypted_content": encrypted_content,
        "content_hash": content_hash,
        "party_a": req.party_a,
        "party_b": req.party_b,
        "agreement_type": req.agreement_type,
        "stored_at": _now(),
        "cross_reference": xref,
    }
    vault["agreements"][req.agreement_id] = entry
    _save_vault(vault)

    _audit("AGREEMENT_STORED", {
        "agreement_id": req.agreement_id,
        "hash": content_hash,
        "type": req.agreement_type,
        "parties": [req.party_a, req.party_b],
        "xref_action": xref.get("action"),
    })

    return {
        "status": "encrypted",
        "agreement_id": req.agreement_id,
        "content_hash": content_hash,
        "encryption": "Fernet AES-128",
        "cross_reference": xref,
        "stored_at": entry["stored_at"],
    }


@app.post("/vault/retrieve")
def vault_retrieve(req: RetrieveRequest):
    """Retrieve and decrypt an agreement from the vault."""
    vault = _load_vault()

    if req.agreement_id not in vault.get("agreements", {}):
        _create_alert(
            "UNAUTHORIZED_ACCESS",
            f"Attempted retrieval of non-existent agreement: {req.agreement_id}",
            source="vault_retrieve",
        )
        raise HTTPException(status_code=404, detail=f"Agreement '{req.agreement_id}' not found")

    entry = vault["agreements"][req.agreement_id]

    try:
        decrypted = decrypt(entry["encrypted_content"])
    except Exception as e:
        _create_alert(
            "DECRYPTION_FAILURE",
            f"Failed to decrypt agreement {req.agreement_id}: {str(e)}",
            source="vault_retrieve",
        )
        raise HTTPException(status_code=500, detail="Decryption failed — key mismatch or corrupted data")

    _audit("AGREEMENT_RETRIEVED", {
        "agreement_id": req.agreement_id,
        "hash": entry.get("content_hash"),
    })

    return {
        "agreement_id": req.agreement_id,
        "content": decrypted,
        "party_a": entry.get("party_a", ""),
        "party_b": entry.get("party_b", ""),
        "agreement_type": entry.get("agreement_type", ""),
        "stored_at": entry.get("stored_at", ""),
        "content_hash": entry.get("content_hash", ""),
    }


@app.get("/vault/list")
def vault_list():
    """List all stored agreements (metadata only — no decrypted content)."""
    vault = _load_vault()
    agreements = []
    for aid, entry in vault.get("agreements", {}).items():
        agreements.append({
            "agreement_id": aid,
            "party_a": entry.get("party_a", ""),
            "party_b": entry.get("party_b", ""),
            "agreement_type": entry.get("agreement_type", ""),
            "stored_at": entry.get("stored_at", ""),
            "content_hash": entry.get("content_hash", ""),
        })
    return {"agreements": agreements, "total": len(agreements)}


# ── Leitner Alert Routes ─────────────────────────────────────

@app.get("/alerts")
def get_alerts(status: str = "all"):
    """Get security alerts, optionally filtered by status."""
    alerts = _load_alerts()
    if status != "all":
        alerts = [a for a in alerts if a.get("status") == status]
    # Sort by box (highest urgency first), then by creation date
    alerts.sort(key=lambda a: (-a.get("box", 1), a.get("created", "")))
    return {"alerts": alerts, "total": len(alerts)}


@app.post("/alerts/dismiss")
def dismiss_alert(req: DismissAlertRequest):
    """Manually dismiss a security alert (only way to clear Leitner alerts)."""
    alerts = _load_alerts()
    found = False
    for alert in alerts:
        if alert["id"] == req.alert_id:
            alert["status"] = "dismissed"
            alert["dismissed_at"] = _now()
            alert["dismissed_by"] = req.dismissed_by
            alert["dismiss_reason"] = req.reason
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"Alert '{req.alert_id}' not found")

    _save_alerts(alerts)
    _audit("ALERT_DISMISSED", {
        "alert_id": req.alert_id,
        "dismissed_by": req.dismissed_by,
        "reason": req.reason,
    })
    return {"status": "dismissed", "alert_id": req.alert_id}


@app.post("/alerts/escalate")
def escalate_alerts():
    """Manually trigger Leitner escalation cycle."""
    count = _escalate_alerts()
    return {"escalated": count, "timestamp": _now()}


@app.get("/audit")
def get_audit_trail(limit: int = 50):
    """Return the last N audit trail entries."""
    entries = []
    if os.path.exists(AUDIT_LOG):
        with open(AUDIT_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                pass
    entries.reverse()  # newest first
    return {"entries": entries, "total": len(entries)}


# ── Entry Point ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5007)
# V3 AUTO-HEAL ACTIVE
