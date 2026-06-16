from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
from pydantic import BaseModel
from typing import Optional
import sqlite3
import bcrypt
import time

from core.database import get_db_connection
from security.minting_engine import minting_engine
from routes.taxonomy_router import router as taxonomy_router

app = FastAPI(title="Module 0: Gateway Core")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "http://127.0.0.1:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the Taxonomy Router
app.include_router(taxonomy_router, prefix="/api/v1/taxonomy", tags=["Taxonomy"])

bearer_scheme = HTTPBearer(auto_error=True)

# --- Transient login-attempt lockout -----------------------------------------
# In-memory tracker. The gateway runs as a single uvicorn worker, so a process
# dict is sufficient for "5 fails -> 15 min lock". Resets on restart by design.
_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 15 * 60
_login_attempts = {}  # lock_key -> {"fails": int, "locked_until": float}


def _is_locked(lock_key: str) -> bool:
    rec = _login_attempts.get(lock_key)
    if not rec:
        return False
    locked_until = rec.get("locked_until", 0)
    if locked_until > time.time():
        return True
    if locked_until:
        # A real lock window elapsed -> clear the slate. (locked_until == 0
        # means "accruing failures, never locked" — leave the counter intact.)
        _login_attempts.pop(lock_key, None)
    return False


def _register_failure(lock_key: str):
    rec = _login_attempts.setdefault(lock_key, {"fails": 0, "locked_until": 0})
    rec["fails"] += 1
    if rec["fails"] >= _MAX_ATTEMPTS:
        rec["locked_until"] = time.time() + _LOCKOUT_SECONDS


def _clear_failures(lock_key: str):
    _login_attempts.pop(lock_key, None)


def verify_gateway_jwt_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Inbound authorization for protected gateway endpoints.
    Decodes the Bearer access token with the RS256 public key and rejects
    refresh tokens. The authenticated emp_id is taken from `sub` only.
    """
    payload = minting_engine.verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired authorization token.")
    if payload.get("type") == "refresh":
        raise HTTPException(status_code=403, detail="Refresh tokens cannot authorize API requests.")
    if not payload.get("sub"):
        raise HTTPException(status_code=403, detail="Token missing subject.")
    return payload


class LoginRequest(BaseModel):
    emp_id: Optional[str] = None  # may be an emp_id, username, or phone_number
    pin: str
    device_id: Optional[str] = None  # recognized-device quick login


@app.post("/api/v1/auth/login")
def login(request: LoginRequest, response: Response):
    """
    Centralized Identity Minting Endpoint.
    Accepts either a typed identifier (emp_id / username / phone_number) or a
    recognized device_id, validates the PIN against the bcrypt hash, and mints
    an RS256 JWT pair.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # 1. Resolve identity. A recognized-device login supplies device_id and
        #    no identifier; the gateway maps it to an emp_id server-side so no
        #    identifier is ever exposed to the browser.
        identity = (request.emp_id or "").strip()
        via_device = False
        if request.device_id and not identity:
            cursor.execute(
                "SELECT emp_id FROM erp_user_devices WHERE device_id = ?",
                (request.device_id,),
            )
            drow = cursor.fetchone()
            if not drow:
                raise HTTPException(status_code=401, detail="Device not recognized.")
            identity = drow["emp_id"]
            via_device = True

        if not identity:
            raise HTTPException(status_code=400, detail="An identifier or recognized device is required.")

        lock_key = identity.lower()
        if _is_locked(lock_key):
            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Try again in 15 minutes.",
            )

        # 2. Look up the employee. Device logins resolve to a single emp_id;
        #    standard logins match across the three identity columns.
        if via_device:
            cursor.execute("SELECT * FROM erp_employees WHERE emp_id = ?", (identity,))
        else:
            cursor.execute(
                "SELECT * FROM erp_employees WHERE emp_id = ? OR username = ? OR phone_number = ?",
                (identity, identity, identity),
            )
        rows = cursor.fetchall()

        # Ambiguity guard: one submitted value must not resolve to two people.
        if len({r["id"] for r in rows}) > 1:
            raise HTTPException(status_code=401, detail="Ambiguous credentials.")
        user = rows[0] if rows else None

        # 3. Verify PIN against the bcrypt hash (plaintext pin is retired).
        pin_verified = False
        if user and user["pin_hash"]:
            try:
                pin_verified = bcrypt.checkpw(
                    request.pin.encode("utf-8"), user["pin_hash"].encode("utf-8")
                )
            except Exception:
                pin_verified = False

        if not user or not pin_verified:
            _register_failure(lock_key)
            raise HTTPException(status_code=401, detail="Invalid credentials.")

        if user["status"] != "ACTIVE":
            raise HTTPException(status_code=403, detail="Account is disabled")

        _clear_failures(lock_key)

        # Touch device recency on a successful device-bound login.
        if via_device and request.device_id:
            cursor.execute(
                "UPDATE erp_user_devices SET last_used_at = CURRENT_TIMESTAMP WHERE device_id = ?",
                (request.device_id,),
            )
            conn.commit()

        # 4. Construct the JWT Payload
        token_payload = {
            "sub": user["emp_id"],
            "role": user["role"],
            "department": user["department"],
            "name": f"{user['first_name']} {user['last_name']}",
        }

        # Mint Dual Tokens
        access_token = minting_engine.mint_access_token(token_payload)
        refresh_token = minting_engine.mint_refresh_token(token_payload)

        # Actuate the HttpOnly Cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,  # Set to True when migrating behind an HTTPS load balancer
            samesite="lax",  # 'lax' required for localhost cross-port bridging, 'strict' in production
            max_age=7 * 24 * 60 * 60,  # 7 Days
        )

        # Only expose the short-lived access token to the DOM
        return {
            "status": "success",
            "access_token": access_token,
            "user": token_payload,
        }
    finally:
        conn.close()


@app.post("/api/v1/auth/refresh")
def refresh(request: Request):
    """
    Autonomous Refresh Actuation.
    Extracts the HttpOnly refresh cookie, verifies database state, and remints the access token.
    """
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh Token Missing.")

    payload = minting_engine.verify_token(token)
    if not payload:
        raise HTTPException(status_code=403, detail="Cryptographic Verification Failed.")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=403, detail="Invalid Token Type.")

    # State Verification: Query gateway_core.db to ensure user is still ACTIVE
    emp_id = payload.get("sub")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status, role, department, first_name, last_name FROM erp_employees WHERE emp_id = ?", (emp_id,))
        user = cursor.fetchone()

        if not user or user["status"] != "ACTIVE":
            raise HTTPException(status_code=403, detail="Account is disabled or terminated.")

        # Re-Mint Access Token
        token_payload = {
            "sub": emp_id,
            "role": user["role"],
            "department": user["department"],
            "name": f"{user['first_name']} {user['last_name']}"
        }

        access_token = minting_engine.mint_access_token(token_payload)

        return {
            "status": "success",
            "access_token": access_token
        }
    finally:
        conn.close()


# --- Custom credentials + device recognition ---------------------------------

class SetupCredentialsRequest(BaseModel):
    username: Optional[str] = None
    phone_number: Optional[str] = None
    pin: Optional[str] = None


@app.post("/api/v1/auth/setup-credentials")
def setup_credentials(request: SetupCredentialsRequest, claims: dict = Depends(verify_gateway_jwt_token)):
    """
    Activation/profile endpoint: lets an authenticated employee choose a custom
    username, phone_number, and PIN. The target employee is the token subject;
    nothing in the request body can redirect the write (no IDOR).
    """
    emp_id = claims["sub"]
    if request.username is None and request.phone_number is None and request.pin is None:
        raise HTTPException(status_code=400, detail="No fields provided to update.")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM erp_employees WHERE emp_id = ?", (emp_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Employee not found.")

        def _assert_free(value, label):
            # Must not collide with ANY other employee's id, username, or phone.
            cursor.execute(
                "SELECT 1 FROM erp_employees "
                "WHERE (emp_id = ? OR username = ? OR phone_number = ?) AND emp_id != ?",
                (value, value, value, emp_id),
            )
            if cursor.fetchone():
                raise HTTPException(status_code=409, detail=f"{label} is already in use.")

        updates, params = [], []

        if request.username is not None:
            uname = request.username.strip()
            if len(uname) < 3:
                raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
            _assert_free(uname, "Username")
            updates.append("username = ?")
            params.append(uname)

        if request.phone_number is not None:
            phone = request.phone_number.strip()
            if len(phone) < 4:
                raise HTTPException(status_code=400, detail="Phone number is invalid.")
            _assert_free(phone, "Phone number")
            updates.append("phone_number = ?")
            params.append(phone)

        if request.pin is not None:
            pin = request.pin.strip()
            if not (pin.isdigit() and 4 <= len(pin) <= 8):
                raise HTTPException(status_code=400, detail="PIN must be 4-8 digits.")
            pin_hash = bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            updates.append("pin_hash = ?")
            params.append(pin_hash)
            updates.append("pin = NULL")  # never retain plaintext

        params.append(emp_id)
        try:
            cursor.execute(f"UPDATE erp_employees SET {', '.join(updates)} WHERE emp_id = ?", params)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Username or phone number is already in use.")
        conn.commit()
        return {"status": "success"}
    finally:
        conn.close()


class RegisterDeviceRequest(BaseModel):
    device_id: str
    device_name: Optional[str] = None
    device_type: str  # 'mobile' | 'desktop'


@app.post("/api/v1/auth/register-device")
def register_device(request: RegisterDeviceRequest, claims: dict = Depends(verify_gateway_jwt_token)):
    """Link a client-generated device_id to the authenticated employee (upsert)."""
    if request.device_type not in ("mobile", "desktop"):
        raise HTTPException(status_code=400, detail="device_type must be 'mobile' or 'desktop'.")
    if not request.device_id or len(request.device_id) < 8:
        raise HTTPException(status_code=400, detail="A valid device_id is required.")

    emp_id = claims["sub"]
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO erp_user_devices (device_id, emp_id, device_name, device_type, last_used_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(device_id) DO UPDATE SET
                emp_id = excluded.emp_id,
                device_name = excluded.device_name,
                device_type = excluded.device_type,
                last_used_at = CURRENT_TIMESTAMP
            """,
            (request.device_id, emp_id, request.device_name, request.device_type),
        )
        conn.commit()
        return {"status": "success", "device_id": request.device_id}
    finally:
        conn.close()


@app.get("/api/v1/auth/recognize-device")
def recognize_device(device_id: str):
    """
    Public pre-auth endpoint for the lock screen. Returns only the display name
    plus role/department for visual feedback — never username, phone, or emp_id.
    The device_id itself remains the bearer; the PIN is still required to log in.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT e.name, e.role, e.department
            FROM erp_user_devices d
            JOIN erp_employees e ON e.emp_id = d.emp_id
            WHERE d.device_id = ? AND e.status = 'ACTIVE'
            """,
            (device_id,),
        )
        row = cursor.fetchone()
        if not row:
            return {"recognized": False}
        return {
            "recognized": True,
            "name": row["name"],
            "role": row["role"],
            "department": row["department"],
        }
    finally:
        conn.close()


class DeregisterDeviceRequest(BaseModel):
    device_id: str


@app.delete("/api/v1/auth/deregister-device")
def deregister_device(request: DeregisterDeviceRequest, claims: dict = Depends(verify_gateway_jwt_token)):
    """Remove a device mapping. Scoped to the authenticated user's own devices."""
    emp_id = claims["sub"]
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM erp_user_devices WHERE device_id = ? AND emp_id = ?",
            (request.device_id, emp_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Device not found for this user.")
        return {"status": "success"}
    finally:
        conn.close()


@app.get("/api/v1/auth/public-key")
def get_public_key():
    """Autonomous Key Distribution Endpoint for downstream microservices."""
    from security.minting_engine import PUBLIC_KEY_PATH
    with open(PUBLIC_KEY_PATH, "r") as key_file:
        pub_key = key_file.read()
    return {"public_key": pub_key}

if __name__ == "__main__":
    # Module 0 strictly binds to Port 9000 to prevent collisions
    uvicorn.run(app, host="0.0.0.0", port=9000)
