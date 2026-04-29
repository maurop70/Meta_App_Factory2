# CORE PROTOCOL 4: ZERO-TRUST API DOCTRINE
The frontend is structurally classified as a compromised, untrusted client. All state-advancing logic, field mutations, and phase transitions must be aggressively validated by the backend persistence layer prior to database commit. The UI exists strictly as a read-only telemetry dashboard and a dumb actuation trigger.

# CORE PROTOCOL 5: SECURITY DOCTRINE UPDATE
All authentication state must strictly adhere to the Asymmetrical RS256 JWT Architecture. Access Tokens (15m TTL) are strictly in-memory and transmitted via Authorization: Bearer. Refresh Tokens are strictly isolated in HttpOnly, Secure, SameSite=Strict cookies. The frontend Axios instance must natively queue and replay requests on 401 Unauthorized via a centralized refresh interceptor. Legacy trust-based header spoofing (e.g., x_mock_role) is permanently forbidden.

# [MANDATORY MEMORY INJECTION]
AUTONOMOUS AGENT (AY) PROTOCOL: STATE MIGRATION & CONTEXT TEARDOWN
If the Autonomous Agent (AY) detects recursive execution failures, fails to resolve an environment/DOM discrepancy after three (3) consecutive attempts, or begins dropping previously established architectural constraints, it must autonomously classify the session as Degraded.

Upon degradation, AY must execute the following sequence:

Halt Execution: Immediately cease all codebase mutations.

Alert: Output exactly the phrase: [STATE DEGRADATION ALERT] Context threshold exceeded. Execution loop halted. Manual state migration required.

Generate Payload: Output a highly compressed, factual summary of the environment for the user to transport to a new session, strictly formatted as:

[STABILIZED INFRASTRUCTURE]: (Bullet points of working, tested systems)

[CURRENT PHASE]: (The specific task that was being attempted)

[ACTIVE BLOCKERS]: (The exact error, stack trace, or loop that triggered the degradation)

[IMMEDIATE NEXT MANDATE]: (The precise next step required to resume development in the fresh session)

# [MANDATORY MEMORY INJECTION]: STRICT EXCEPTION ESCALATION
Autonomous agents are permanently forbidden from silently mutating architectural parameters, taxonomies, or data models to bypass engine-level exceptions (e.g., SQLite CHECK constraints). If an execution mandate conflicts with the established physical schema, the agent must immediately halt execution and output the raw physical exception for architectural resolution. Forging compliance diffs to pass structural audits is a fatal system violation.

[MANDATORY MEMORY INJECTION]
REACT PORTAL SUPREMACY: All enterprise UI modals, blocking overlays, and floating context menus are strictly forbidden from rendering inline within standard component hierarchies. They must be physically ejected to the root DOM utilizing ReactDOM.createPortal(element, document.body). Failure to eject components traps position: fixed elements inside parent CSS stacking contexts (triggered by transform, filter, or overflow bounds), causing catastrophic visual clipping and deadlocked viewports.

[MANDATORY MEMORY INJECTION]
STRICT PAGINATION BOUNDARIES: Unbounded data fetching (e.g., SELECT * FROM table) is permanently forbidden. Any backend GET route querying a collection must natively ingest and enforce limit and offset query parameters, binding them directly to the database execution layer. The frontend Axios matrix must strictly pass these parameters to limit the React reconciliation tree payload. Masking massive DOM bloat with CSS overflow: hidden is a fatal architecture violation.

[MANDATORY MEMORY INJECTION]
AXIOS PREFIX TRUNCATION: When utilizing a centralized frontend HTTP client (e.g., Axios) pre-configured with a baseURL (e.g., /api), all downstream component API calls must strictly omit the root prefix. Writing api.get('/api/resource') triggers a fatal double-prefix routing exception (/api/api/resource). Routes must be strictly truncated to api.get('/resource').
