# CORE PROTOCOL 4: ZERO-TRUST API DOCTRINE
The frontend is structurally classified as a compromised, untrusted client. All state-advancing logic, field mutations, and phase transitions must be aggressively validated by the backend persistence layer prior to database commit. The UI exists strictly as a read-only telemetry dashboard and a dumb actuation trigger.

# CORE PROTOCOL 5: SECURITY DOCTRINE UPDATE
All authentication state must strictly adhere to the Asymmetrical RS256 JWT Architecture. Access Tokens (15m TTL) are strictly in-memory and transmitted via Authorization: Bearer. Refresh Tokens are strictly isolated in HttpOnly, Secure, SameSite=Strict cookies. The frontend Axios instance must natively queue and replay requests on 401 Unauthorized via a centralized refresh interceptor. Legacy trust-based header spoofing (e.g., x_mock_role) is permanently forbidden.
