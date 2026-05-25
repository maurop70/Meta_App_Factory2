"""
schemas.py — Genesis Architect Ontology Schema Layer
═════════════════════════════════════════════════════
Phase 11.0 | Meta App Factory | Antigravity V3

The AgentOntology is the canonical, immutable contract for every new
agent artifact synthesized by the Genesis Architect pipeline.

DOCTRINE: The CTO node is STRICTLY FORBIDDEN from consuming raw biological
prompts. It MUST receive only a verified AgentOntology JSON that has passed
the Verification_Node. Any attempt to bypass this schema will raise a
hard OntologyValidationError and halt the pipeline.
"""

import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class RouteLogicSpec(BaseModel):
    """Specification for logic injection into an API endpoint."""
    path: str = Field(..., description="URL path matching an EndpointSpec.path")
    method: str = Field(..., description="HTTP method matching an EndpointSpec.method")
    logic_ast: str = Field(..., description="Python string block containing the route's body logic")
    imports: List[str] = Field(default=[], description="Required python import strings to inject at the top")

    @field_validator("path")
    @classmethod
    def path_must_start_with_api(cls, v: str) -> str:
        if not v.startswith("/api/"):
            raise ValueError(f"RouteLogicSpec.path must start with '/api/', got: '{v}'")
        return v

    @field_validator("method")
    @classmethod
    def method_must_be_valid(cls, v: str) -> str:
        allowed = {"GET", "POST", "PUT", "DELETE", "PATCH"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"RouteLogicSpec.method must be one of {allowed}, got: '{v}'")
        return upper


class EndpointSpec(BaseModel):
    """Specification for a single API endpoint the agent must expose."""
    path: str = Field(..., description="URL path, must start with /api/")
    method: str = Field(..., description="HTTP method: GET | POST | PUT | DELETE | PATCH")
    summary: str = Field(..., description="One-line description of this endpoint's function")
    contract_ref: str = Field(..., description="Name of the matching DataContract in data_contracts[]")

    @field_validator("path")
    @classmethod
    def path_must_start_with_api(cls, v: str) -> str:
        if not v.startswith("/api/"):
            raise ValueError(f"EndpointSpec.path must start with '/api/', got: '{v}'")
        return v

    @field_validator("method")
    @classmethod
    def method_must_be_valid(cls, v: str) -> str:
        allowed = {"GET", "POST", "PUT", "DELETE", "PATCH"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"EndpointSpec.method must be one of {allowed}, got: '{v}'")
        return upper


class DataContract(BaseModel):
    """Input/output schema contract for a single API endpoint."""
    contract_name: str = Field(..., description="Unique name referencing an EndpointSpec.contract_ref")
    input_fields: List[str] = Field(..., description="List of required input field names")
    output_fields: List[str] = Field(..., description="List of guaranteed output field names")
    error_codes: List[int] = Field(
        default=[400, 422, 500],
        description="HTTP status codes this endpoint may return on failure"
    )


class SecurityPosture(BaseModel):
    """Security configuration for the generated agent."""
    auth_method: str = Field(
        default="api_key",
        description="Authentication mechanism: api_key | bearer_token | none | oauth2"
    )
    rate_limit_rpm: int = Field(
        default=60,
        ge=1,
        description="Maximum requests per minute this agent will accept"
    )
    audit_log_enabled: bool = Field(
        default=True,
        description="Whether all requests must be logged to the audit ledger"
    )
    cors_origins: List[str] = Field(
        default=["http://localhost:5173"],
        description="Permitted CORS origins for this agent"
    )

    @field_validator("auth_method")
    @classmethod
    def auth_method_must_be_valid(cls, v: str) -> str:
        allowed = {"api_key", "bearer_token", "none", "oauth2"}
        if v.lower() not in allowed:
            raise ValueError(f"SecurityPosture.auth_method must be one of {allowed}, got: '{v}'")
        return v.lower()


# ── Primary Ontology Model ────────────────────────────────────────────────────

class AgentOntology(BaseModel):
    """
    The canonical, immutable contract for every new agent synthesized by
    the Genesis Architect pipeline.

    IMPORTANT: verified=True may ONLY be set by the Verification_Node.
    Any external mutation of this field is a doctrine violation.
    """

    agent_name: str = Field(
        ...,
        description="PascalCase agent name with no spaces or special characters"
    )
    role_summary: str = Field(
        ...,
        max_length=280,
        description="280-char max summary of the agent's role and primary directive"
    )
    primary_capabilities: List[str] = Field(
        ...,
        min_length=3,
        max_length=8,
        description="List of 3–8 capability strings describing what this agent can do"
    )
    api_endpoints: List[EndpointSpec] = Field(
        ...,
        min_length=1,
        description="At least one POST endpoint this agent must expose"
    )
    data_contracts: List[DataContract] = Field(
        ...,
        min_length=1,
        description="One DataContract per api_endpoint (matched by contract_ref)"
    )
    dependencies: List[str] = Field(
        default=[],
        description="pip package names required by this agent (e.g. 'fastapi>=0.110.0')"
    )
    route_logic_blocks: List[RouteLogicSpec] = Field(
        default=[],
        description="Optional custom python logic blocks to inject into specific routes during compile rendering"
    )
    startup_logic_ast: str = Field(
        default="",
        description="Optional custom python logic block to inject into the app startup event handler"
    )
    security_posture: SecurityPosture = Field(
        default_factory=SecurityPosture,
        description="Security configuration governing auth, rate limits, and audit logging"
    )
    research_citations: List[str] = Field(
        default=[],
        description="Source URLs gathered by Research_Node during ontology synthesis"
    )
    ontology_version: str = Field(
        default="1.0.0",
        description="Semantic version of this ontology specification"
    )
    verified: bool = Field(
        default=False,
        description="Set to True ONLY by Verification_Node after all checks pass. Never set externally."
    )

    # ── Field Validators ──────────────────────────────────────────────────────

    @field_validator("agent_name")
    @classmethod
    def agent_name_must_be_pascal_case(cls, v: str) -> str:
        """
        Enforces PascalCase: starts with uppercase, contains only letters,
        digits, and underscores. No spaces, hyphens, or special chars.
        """
        pattern = r'^[A-Z][A-Za-z0-9_]*$'
        if not re.match(pattern, v):
            raise ValueError(
                f"agent_name must be PascalCase (e.g. 'StockAlertAgent'), "
                f"got: '{v}'. No spaces, hyphens, or special characters allowed."
            )
        return v

    @field_validator("role_summary")
    @classmethod
    def role_summary_must_not_be_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("role_summary must not be empty or whitespace-only")
        return stripped

    @field_validator("api_endpoints")
    @classmethod
    def must_have_at_least_one_post_endpoint(cls, v: List[EndpointSpec]) -> List[EndpointSpec]:
        has_post = any(ep.method == "POST" for ep in v)
        if not has_post:
            raise ValueError(
                "api_endpoints must contain at least one POST endpoint. "
                "Agents must expose a POST interface for inbound instruction payloads."
            )
        return v

    # ── Cross-Field Validators ────────────────────────────────────────────────

    @model_validator(mode="after")
    def every_endpoint_must_have_a_contract(self) -> "AgentOntology":
        """
        Logical invariant: every EndpointSpec.contract_ref must have a matching
        DataContract.contract_name. If any endpoint is orphaned, reject the ontology.
        """
        contract_names = {dc.contract_name for dc in self.data_contracts}
        for ep in self.api_endpoints:
            if ep.contract_ref not in contract_names:
                raise ValueError(
                    f"Endpoint '{ep.path}' references contract_ref '{ep.contract_ref}' "
                    f"but no matching DataContract exists. "
                    f"Available contracts: {sorted(contract_names)}"
                )
        return self
