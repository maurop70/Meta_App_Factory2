"""
cto_agent.py — CTO Infrastructure Evaluation Agent V3 (Live Fire)
═══════════════════════════════════════════════════════════════════
Live CapEx/OpEx infrastructure cost analysis via Gemini 2.5 Pro Function Calling.

Data source: capex_ledger.json (local pricing ledger — stable, no scraping)
Resilience:  generate_with_backoff_sync wraps the Gemini call.
Fallback:    Conservative static estimates if ledger or API is unavailable.
"""

import os
import json
import logging
from pathlib import Path
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError
from ai_utils import generate_with_backoff_sync
from agent_base import AgentBase, ProvenanceClaim

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# PYDANTIC OUTPUT SCHEMA (strict validation of Gemini's JSON response)
# ─────────────────────────────────────────────────────────────────────────────

class CTOGeminiOutput(BaseModel):
    """
    Strict Pydantic schema for the CTO Gemini output.
    Validation failure routes to _fallback_cto with confidence=0.0,
    guaranteeing the Hallucination Gate catches uncited numeric claims.
    """
    gate_status: str
    infrastructure_cost_monthly: float
    capex_estimate: float
    cloud_comparison_monthly: float
    roi_breakeven_months: int
    cost_breakdown: dict = {}
    recommendation: str = ""
    tech_risks: list[str] = []


_LEDGER_PATH = Path(__file__).parent / "capex_ledger.json"
_ledger_cache: dict = {}


# ─────────────────────────────────────────────────────────────────────────────
# LEDGER LOADER
# ─────────────────────────────────────────────────────────────────────────────

def _load_ledger() -> dict:
    """
    Loads capex_ledger.json from disk. Caches it in memory after first read.
    Returns empty dict with error key if the file is missing or malformed.
    """
    global _ledger_cache
    if _ledger_cache:
        return _ledger_cache

    if not _LEDGER_PATH.exists():
        logger.error(f"[CTO Agent] capex_ledger.json not found at {_LEDGER_PATH}")
        return {"_error": f"Ledger file not found: {_LEDGER_PATH}"}

    try:
        with open(_LEDGER_PATH, encoding="utf-8") as f:
            _ledger_cache = json.load(f)
        logger.info(
            f"[CTO Agent] Loaded capex_ledger.json — "
            f"{len(_ledger_cache.get('compute', {}))} compute SKUs, "
            f"{len(_ledger_cache.get('architecture_profiles', {}))} profiles"
        )
        return _ledger_cache
    except Exception as e:
        logger.error(f"[CTO Agent] Failed to parse capex_ledger.json: {e}")
        return {"_error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# NATIVE PYTHON TOOLS (declared to Gemini 2.5 Pro via function calling)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_hardware_capex(architecture_profile: str, pilot_units: int) -> dict:
    """
    Calculates realistic CapEx and monthly OpEx for an enterprise hardware deployment
    by reading from the local capex_ledger.json pricing ledger.

    Args:
        architecture_profile: One of the profile keys from the ledger:
            'enterprise_ai_appliance', 'edge_ai', 'gpu_training_cluster',
            'mid_range_gpu_server', 'cpu_general_purpose'
            (or a free-form description — agent will pick the closest match)
        pilot_units: Number of primary compute units for the pilot (typically 1-5)

    Returns:
        dict with total_capex_usd, monthly_opex_usd, annual_opex_usd, 3yr_tco, breakdown
    """
    ledger = _load_ledger()

    if "_error" in ledger:
        return {"error": ledger["_error"], "total_capex_usd": 0, "monthly_opex_usd": 450}

    profiles = ledger.get("architecture_profiles", {})
    compute_kb = ledger.get("compute", {})
    networking_kb = ledger.get("networking", {})
    software_kb = ledger.get("software_licensing", {})

    # Match the requested profile (exact key first, then fuzzy)
    profile_key = architecture_profile.lower().replace(" ", "_").replace("-", "_")
    if profile_key not in profiles:
        # Fuzzy match: find first profile whose description contains keywords from the request
        arch_lower = architecture_profile.lower()
        for k, v in profiles.items():
            if k == "_comment":
                continue
            desc_lower = v.get("description", "").lower()
            if any(kw in arch_lower or kw in desc_lower
                   for kw in ["appliance", "edge", "training", "mid", "cpu", "gpu", "hardware"]):
                profile_key = k
                break
        else:
            profile_key = "enterprise_ai_appliance"  # safe default

    profile = profiles.get(profile_key, profiles.get("enterprise_ai_appliance"))
    units = max(1, min(pilot_units, 20))  # sanity cap

    # Resolve component costs from all sections of the ledger
    component_costs = {}
    all_sections = {**compute_kb, **networking_kb, **software_kb}

    total_capex = 0.0
    total_monthly_opex = 0.0

    for comp_key in profile.get("components", []):
        comp = all_sections.get(comp_key)
        if not comp:
            logger.warning(f"[CTO Agent] Component '{comp_key}' not found in ledger")
            continue

        # Per-unit scaling: compute scales with pilot_units, networking = 1 rack, software scales
        if comp_key in compute_kb:
            multiplier = units
        elif comp_key in networking_kb:
            rack_count = max(1, units // 4)  # ~4 servers per rack
            multiplier = rack_count
        else:  # software — scales per unit
            multiplier = units

        cap = comp.get("capex_usd", 0) * multiplier
        opex = comp.get("monthly_opex_usd", 0) * multiplier
        total_capex += cap
        total_monthly_opex += opex

        component_costs[comp_key] = {
            "label": comp.get("label", comp_key),
            "units": multiplier,
            "capex_per_unit_usd": comp.get("capex_usd", 0),
            "monthly_opex_per_unit_usd": comp.get("monthly_opex_usd", 0),
            "total_capex_usd": cap,
            "total_monthly_opex_usd": opex,
        }

    tco_3yr = total_capex + (total_monthly_opex * 36)

    return {
        "profile_used": profile_key,
        "profile_description": profile.get("description", ""),
        "pilot_units": units,
        "total_capex_usd": round(total_capex, 2),
        "monthly_opex_usd": round(total_monthly_opex, 2),
        "annual_opex_usd": round(total_monthly_opex * 12, 2),
        "tco_3yr_usd": round(tco_3yr, 2),
        "component_breakdown": component_costs,
        "ledger_source": str(_LEDGER_PATH),
    }


def get_cloud_equivalent_cost(architecture_profile: str) -> dict:
    """
    Returns the equivalent monthly cloud cost for the requested architecture
    by reading the cloud_equivalents section of capex_ledger.json.
    Used to calculate ROI breakeven vs on-premise deployment.

    Args:
        architecture_profile: Profile key or description
            (e.g. 'enterprise_ai_appliance', 'gpu_training_cluster', 'edge_ai')

    Returns:
        dict with provider, monthly_usd, annual_usd, notes
    """
    ledger = _load_ledger()

    if "_error" in ledger:
        return {"error": ledger["_error"], "monthly_usd": 900}

    profiles = ledger.get("architecture_profiles", {})
    cloud_kb = ledger.get("cloud_equivalents", {})

    # Find the profile and its cloud_equivalent_key
    profile_key = architecture_profile.lower().replace(" ", "_").replace("-", "_")
    arch_lower = architecture_profile.lower()

    # Fuzzy match
    if profile_key not in profiles:
        for k, v in profiles.items():
            if k == "_comment":
                continue
            desc_lower = v.get("description", "").lower()
            if any(kw in arch_lower or kw in desc_lower
                   for kw in ["appliance", "edge", "training", "mid", "cpu", "gpu"]):
                profile_key = k
                break
        else:
            profile_key = "enterprise_ai_appliance"

    profile = profiles.get(profile_key, {})
    cloud_key = profile.get("cloud_equivalent_key", "aws_g6_4xlarge")
    cloud_entry = cloud_kb.get(cloud_key, {})

    if not cloud_entry:
        return {
            "profile": profile_key,
            "cloud_key": cloud_key,
            "error": f"Cloud key '{cloud_key}' not found in ledger",
            "monthly_usd": 900,
        }

    return {
        "profile": profile_key,
        "cloud_key": cloud_key,
        "provider": cloud_entry.get("label", cloud_key),
        "hourly_usd": cloud_entry.get("hourly_usd", 0),
        "monthly_usd": cloud_entry.get("monthly_usd", 900),
        "annual_usd": cloud_entry.get("monthly_usd", 900) * 12,
        "reserved_discount_pct": cloud_entry.get("on_demand_vs_reserved_discount_pct", 35),
        "notes": cloud_entry.get("notes", ""),
        "ledger_source": str(_LEDGER_PATH),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CTO AGENT MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_cto_evaluation(intent: str) -> dict:
    """
    Live CTO infrastructure feasibility analysis using Gemini 2.5 Pro Function Calling.
    Called via asyncio.to_thread() from native_sequence().
    All cost data is read from capex_ledger.json — no live scraping.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("[CTO Agent] GEMINI_API_KEY missing — using conservative fallback.")
        return _fallback_cto(intent, error="GEMINI_API_KEY missing")

    # Pre-load the ledger (validates it exists before firing Gemini)
    ledger = _load_ledger()
    if "_error" in ledger:
        return _fallback_cto(intent, error=ledger["_error"])

    client = genai.Client(api_key=api_key)

    # Surface available profiles to the model for accurate selection
    profiles_summary = {
        k: v.get("description", "")
        for k, v in ledger.get("architecture_profiles", {}).items()
        if k != "_comment"
    }

    prompt = f"""You are the Chief Technology Officer of the Antigravity AI platform.

The Commander has issued this strategic directive:
"{intent}"

Your mission: Evaluate INFRASTRUCTURE FEASIBILITY and REAL COSTS using the pricing ledger tools.

Available architecture profiles in capex_ledger.json:
{json.dumps(profiles_summary, indent=2)}

REQUIRED STEPS:
1. Select the most appropriate architecture_profile for the intent above
2. Call calculate_hardware_capex with that profile and a sensible pilot_units count (1-5)
3. Call get_cloud_equivalent_cost with the same profile to get the cloud comparison
4. Calculate ROI breakeven: roi_breakeven_months = round(capex / (cloud_monthly - on_prem_monthly))
   (If on-premise monthly cost exceeds cloud, breakeven = -1, meaning "no ROI")

Return a JSON object with these exact keys:
{{
    "gate_status": "PASSED" or "FAILED",
    "infrastructure_cost_monthly": <float, monthly OpEx from ledger calc>,
    "capex_estimate": <float, total CapEx from ledger calc>,
    "cloud_comparison_monthly": <float, equivalent cloud monthly from ledger>,
    "roi_breakeven_months": <int, calculated breakeven>,
    "cost_breakdown": {{
        "profile_used": "<profile key>",
        "pilot_units": <int>,
        "tco_3yr_usd": <float>
    }},
    "recommendation": "<your CTO assessment — 1-2 sentences, specific to the intent>",
    "tech_risks": ["<specific risk 1>", "<specific risk 2>", "<specific risk 3>"]
}}

gate_status is FAILED only if the architecture is technically impossible or catastrophically misaligned.
Return only valid JSON, no markdown fences.
"""

    tools = [calculate_hardware_capex, get_cloud_equivalent_cost]

    try:
        response = generate_with_backoff_sync(
            client.models.generate_content,
            model="gemini-2.5-pro",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False),
            ),
        )

        raw = response.text.strip().replace("```json", "").replace("```", "").strip()

        try:
            parsed = CTOGeminiOutput(**json.loads(raw))
        except (ValidationError, json.JSONDecodeError, ValueError) as ve:
            logger.error(f"[CTO Agent] Pydantic validation failed: {ve}")
            # confidence=0.0 forces [SIMULATED] citation in CTOAgent._attach_provenance
            return _fallback_cto(intent, error=f"Pydantic validation: {ve}")

        result = {
            "gate_status": parsed.gate_status,
            "infrastructure_cost_monthly": parsed.infrastructure_cost_monthly,
            "capex_estimate": parsed.capex_estimate,
            "cloud_comparison_monthly": parsed.cloud_comparison_monthly,
            "roi_breakeven_months": parsed.roi_breakeven_months,
            "cost_breakdown": parsed.cost_breakdown,
            "recommendation": parsed.recommendation,
            "tech_risks": parsed.tech_risks,
            "live_data": True,
        }
        logger.info(
            f"[CTO Agent] Evaluation complete: {result['gate_status']} | "
            f"${result['infrastructure_cost_monthly']:,.0f}/mo OpEx | "
            f"CapEx: ${result['capex_estimate']:,.0f} | "
            f"Breakeven: {result['roi_breakeven_months']} months"
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[CTO Agent] JSON parse failed: {e}")
        return _fallback_cto(intent, error=f"JSON parse error: {e}")
    except Exception as e:
        logger.error(f"[CTO Agent] Gemini call failed: {e}")
        return _fallback_cto(intent, error=str(e))


def _fallback_cto(intent: str, error: str = None) -> dict:
    """Conservative static fallback when API or ledger is unavailable."""
    note = f" [Error: {error}]" if error else ""
    return {
        "gate_status": "PASSED",
        "infrastructure_cost_monthly": 450,
        "capex_estimate": 0,
        "cloud_comparison_monthly": 900,
        "roi_breakeven_months": 0,
        "cost_breakdown": {},
        "recommendation": f"[SIMULATED — live evaluation unavailable{note}]",
        "tech_risks": [],
        "live_data": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PROVENANCE WRAPPER
# ─────────────────────────────────────────────────────────────────────────────

class CTOAgent(AgentBase):
    """AgentBase subclass that attaches UDPP provenance to CTO evaluation output."""
    AGENT_ID = "cto"

    def run(self, intent: str) -> dict:
        result = run_cto_evaluation(intent)
        return self._attach_provenance(result)

    def _attach_provenance(self, result: dict) -> dict:
        """Build and attach the _provenance sidecar based on live_data flag."""
        breakdown = result.get("cost_breakdown", {})
        profile_used = breakdown.get("profile_used", "unknown_profile")

        if result.get("live_data"):
            # Source: local ledger file with specific profile fragment
            ledger_citation = (
                f"file://capex_ledger.json"
                f"#architecture_profiles.{profile_used}"
            )
            tool = "ledger_query"
            confidence_score = 0.97  # structured, versioned local data
        else:
            ledger_citation = f"[SIMULATED — capex_ledger.json query failed]"
            tool = "fallback_simulation"
            confidence_score = 0.0

        provenance = self.build_provenance_block({
            "infrastructure_cost_monthly": ProvenanceClaim.build(
                result.get("infrastructure_cost_monthly"), ledger_citation, tool, confidence_score),
            "capex_estimate": ProvenanceClaim.build(
                result.get("capex_estimate"), ledger_citation, tool, confidence_score),
            "cloud_comparison_monthly": ProvenanceClaim.build(
                result.get("cloud_comparison_monthly"), ledger_citation, tool, confidence_score),
            "roi_breakeven_months": ProvenanceClaim.build(
                result.get("roi_breakeven_months"), ledger_citation, tool, confidence_score),
            "gate_status": ProvenanceClaim.build(
                result.get("gate_status"), ledger_citation, tool, confidence_score),
        })

        return self.merge_into_output(result, provenance)


if __name__ == "__main__":
    import sys
    test_intent = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "Migrate Antigravity to a 100% on-premise AI hardware model selling to Enterprise clients."
    )
    agent = CTOAgent()
    print(json.dumps(agent.run(test_intent), indent=2))
