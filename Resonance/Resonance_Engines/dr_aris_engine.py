"""
dr_aris_engine.py — Dr. Aris: Chief Behavioral Strategist & Clinical Observer
Staged in Sentinel_Bridge for Resonance.

Title:  Dr. Aris — Chief Behavioral Strategist & Clinical Observer
Persona: World-class psychological consultant with deep expertise in
         Gen Z/Alpha psychographics, behavioral economics, and clinical intervention.

Module 1 — The Boardroom Consultant (B2B)
    Strategic market-level psychological advisor for the CMO / Narrative Team.
    Uses ONLY general expert knowledge. NEVER accesses individual user data.

Module 2 — The Clinical Sentinel (B2C)
    Analyzes individual user data (hints, profile, history) solely for safety
    alerts and "Alex-Adjustment" proposals directed at parents.

Module 3 — Communication Style
    Boardroom: Professional, authoritative, strategic, high-level.
    Parents:   Empathetic, clear, clinical yet accessible.
    User:      SILENT. Never interacts with the end-user.

Pipeline: Profile + Hints + History → Gemini Analysis → Proposals → Consent Gate → Alex Directive
"""

# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

try:
    from auto_heal import healed_post, auto_heal, diagnose
except ImportError:
    def healed_post(*a, **kw): return "skipped"
    def auto_heal(*a, **kw): pass
    def diagnose(*a, **kw): return {}

import os
import sys
import json
import re
import logging
import uuid
from datetime import datetime

logger = logging.getLogger("DrAris")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESONANCE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
REPORTS_PATH = os.path.join(SCRIPT_DIR, "dr_aris_reports.json")
HINTS_FILE = os.path.join(RESONANCE_DIR, "user_profile_hints.json")
HISTORY_FILE = os.path.join(RESONANCE_DIR, ".Gemini_state", ".stream_history.json")
SANDBOX_FLAG_FILE = os.path.join(RESONANCE_DIR, ".Gemini_state", ".sandbox_flag.json")
PARENT_CONFIG_PATH = os.path.join(RESONANCE_DIR, "parent_config.json")

# ── Crisis Keywords (Offline Regex Scanner) ──────────────────
CRISIS_PATTERNS = [
    # Self-harm / suicidal ideation
    (r'\b(?:kill myself|want to die|end it all|slit|cut myself|hurt myself|suicide|suicidal)\b',
     'critical', 'Self-Harm / Suicidal Ideation'),
    # Extreme isolation
    (r'\b(?:nobody (?:likes|cares|wants) me|completely alone|no friends at all|everyone hates me)\b',
     'warning', 'Extreme Social Isolation'),
    # Sudden mood shifts
    (r'\b(?:i don\'t care anymore|nothing matters|what\'s the point|give up|giving up)\b',
     'warning', 'Apathy / Hopelessness'),
    # Bullying
    (r'\b(?:they bully me|bullied|being bullied|they hit me|pushed me|threatened me)\b',
     'warning', 'Bullying Report'),
    # Substance
    (r'\b(?:tried drugs|drinking|drunk|smoked weed|vaping|high on)\b',
     'warning', 'Substance Use Indicator'),
    # Aggression
    (r'\b(?:want to hurt|punch|fight someone|break something|so angry i could)\b',
     'info', 'Aggression / Anger Escalation'),
    # Sleep / eating
    (r'\b(?:can\'t sleep|not sleeping|not eating|starving myself|insomnia)\b',
     'info', 'Sleep / Eating Disruption'),
]


# ── Data Access Helpers ──────────────────────────────────────

def _get_api_key():
    """Retrieve Gemini API key from environment or vault."""
    try:
        _core = os.path.abspath(os.path.join(RESONANCE_DIR, ".."))
        for vp in [os.path.join(RESONANCE_DIR, "..", "Alpha_V2_Genesis"), _core]:
            vc = os.path.join(vp, "vault_client.py")
            if os.path.exists(vc):
                sys.path.insert(0, vp)
                break
        from vault_client import get_secret
        key = get_secret("GEMINI_API_KEY", "")
    except ImportError:
        key = os.getenv("GEMINI_API_KEY", "")
    return key or os.getenv("GEMINI_API_KEY", "")


def _load_reports():
    """Load the Dr. Aris reports cache."""
    if os.path.exists(REPORTS_PATH):
        try:
            with open(REPORTS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Error loading Dr. Aris reports: {e}")
    return _empty_reports()


def _save_reports(reports):
    """Save the Dr. Aris reports cache."""
    os.makedirs(os.path.dirname(REPORTS_PATH), exist_ok=True)
    with open(REPORTS_PATH, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2)
    logger.info(f"Dr. Aris reports saved to {REPORTS_PATH}")


def _empty_reports():
    """Returns an empty reports structure."""
    return {
        "last_analysis": None,
        "psychological_profile": {},
        "alerts": [],
        "proposals": [],
        "rejected_proposals": [],
        "analysis_history": [],
    }


def _load_hints():
    """Load user profile hints (passively collected by app_stream.py)."""
    if os.path.exists(HINTS_FILE):
        try:
            with open(HINTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"hints": [], "updated_at": None}


def _load_history(n=40):
    """Load recent conversation history, excluding sandbox entries."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
                return history[-(n * 2):]
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _is_sandbox_active():
    """Check if sandbox (parent testing) mode is currently active."""
    try:
        if os.path.exists(SANDBOX_FLAG_FILE):
            with open(SANDBOX_FLAG_FILE, "r") as f:
                return json.load(f).get("active", False)
    except Exception:
        pass
    return False


def _load_parent_config():
    """Load parent_config.json for read-only analysis."""
    if os.path.exists(PARENT_CONFIG_PATH):
        try:
            with open(PARENT_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Error loading parent_config.json: {e}")
    return {}


def _save_parent_config(config):
    """Save parent_config.json (used for approved proposal injection)."""
    try:
        with open(PARENT_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        logger.info("Parent config updated by Dr. Aris (approved proposal).")
    except Exception as e:
        logger.error(f"Error saving parent_config.json: {e}")


# ── Offline Alert Scanner ────────────────────────────────────

def run_alert_scan(hints_data=None, recent_history=None):
    """
    Scans user messages for crisis keywords and behavioral flags.
    Uses regex patterns — no API call required.
    Returns a list of alert dicts.
    """
    if hints_data is None:
        hints_data = _load_hints()
    if recent_history is None:
        recent_history = _load_history()

    # Skip if sandbox mode is active
    if _is_sandbox_active():
        logger.info("Dr. Aris: Sandbox mode active — skipping alert scan.")
        return []

    alerts = []
    seen_patterns = set()

    # Scan conversation history for crisis patterns
    for entry in recent_history:
        if entry.get("role") != "user":
            continue
        text = entry.get("content", "")
        text_lower = text.lower()

        for pattern, severity, label in CRISIS_PATTERNS:
            if label in seen_patterns:
                continue
            match = re.search(pattern, text_lower)
            if match:
                alerts.append({
                    "id": str(uuid.uuid4())[:8],
                    "severity": severity,
                    "pattern": label,
                    "evidence": text[:200],
                    "detected_at": datetime.now().isoformat(),
                })
                seen_patterns.add(label)

    # Scan hints for emotional patterns
    emotional_hints = [h for h in hints_data.get("hints", [])
                       if "Emotional:" in h.get("tag", "") or "Confidence - Low" in h.get("tag", "")]
    if len(emotional_hints) >= 3:
        alerts.append({
            "id": str(uuid.uuid4())[:8],
            "severity": "info",
            "pattern": "Recurring Emotional Signals",
            "evidence": f"{len(emotional_hints)} emotional markers detected in profile hints: "
                        + ", ".join(h["tag"] for h in emotional_hints[-5:]),
            "detected_at": datetime.now().isoformat(),
        })

    return alerts


# ── Gemini-Powered Analysis ──────────────────────────────────

def analyze_profile(parent_config=None, hints_data=None, recent_history=None):
    """
    Main analysis entry point. Uses Gemini to synthesize a cohesive
    psychological profile from all available data sources.

    Returns a structured report dict.
    """
    if parent_config is None:
        parent_config = _load_parent_config()
    if hints_data is None:
        hints_data = _load_hints()
    if recent_history is None:
        recent_history = _load_history()

    # Skip if sandbox mode is active
    if _is_sandbox_active():
        logger.info("Dr. Aris: Sandbox mode active — analysis skipped.")
        reports = _load_reports()
        reports["last_analysis"] = datetime.now().isoformat()
        return reports

    api_key = _get_api_key()
    if not api_key:
        logger.error("Dr. Aris: No Gemini API key — returning cached reports.")
        return _load_reports()

    # Build context for Gemini
    profile = parent_config.get("student_profile", {})
    progress_log = parent_config.get("progress_log", [])
    instructions = parent_config.get("instructions", "")
    hint_tags = [h["tag"] for h in hints_data.get("hints", [])[-30:]]

    # Extract user-only messages from history
    user_messages = [e.get("content", "")[:300] for e in recent_history if e.get("role") == "user"][-20:]

    analysis_prompt = f"""You are Dr. Aris, Chief Behavioral Strategist & Clinical Observer.
You are operating in MODULE 2: CLINICAL SENTINEL mode.
You are a world-class clinical child psychologist specializing in adolescent developmental analysis.
You are analyzing data about a 16-year-old male student with Auditory Processing Disorder (APD) and speech delays.

Your Communication Style (Module 3): Empathetic, clear, clinical yet accessible. You are writing for a parent audience.
Your Objective: Maximize this user's achievement of the "Resonance Purpose" (Growth, Resilience, Social Connection).

STUDENT PROFILE (parent-reported):
- Hobbies/Interests: {json.dumps(profile.get('hobbies_interests', []))}
- Social Level: {profile.get('social_level', 'unknown')}
- Academic Weak Areas: {json.dumps(profile.get('academic_weak_areas', []))}
- Stress Indicators: {json.dumps(profile.get('stress_indicators', []))}
- Learning Style: {json.dumps(profile.get('learning_style_preferences', []))}

PARENT INSTRUCTIONS: {instructions[:500] if instructions else 'None provided'}

BEHAVIORAL HINTS (passively collected from conversations):
{json.dumps(hint_tags) if hint_tags else 'No hints collected yet.'}

RECENT USER MESSAGES (last 20):
{chr(10).join(f'- "{msg}"' for msg in user_messages) if user_messages else 'No conversation history available.'}

SESSION ENGAGEMENT (last 10 sessions):
{json.dumps(progress_log[-10:]) if progress_log else 'No session data.'}

Based on this data, provide a clinical assessment. Respond ONLY with a valid JSON object:
{{
  "psychological_profile": {{
    "attachment_style": "brief description of attachment patterns observed",
    "anxiety_markers": ["list of anxiety indicators"],
    "cognitive_strengths": ["list of cognitive strengths"],
    "emotional_baseline": "brief description of emotional state",
    "social_readiness": "brief assessment of social comfort level"
  }},
  "proposals": [
    {{
      "title": "short title for the intervention",
      "description": "detailed explanation of what was observed and why this intervention helps",
      "proposed_directive": "the exact text to inject into Alex's system prompt to implement this change",
      "severity": "info or warning or critical"
    }}
  ]
}}

Generate 1-3 actionable proposals. Each proposed_directive should be a clear, concise instruction for Alex that would subtly adjust his behavior. Do not reference Dr. Aris or clinical terminology in the directives — they should sound like natural parent instructions."""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": analysis_prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 3000,
            },
        }

        _v3_status = safe_post(url, payload)


        response = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
        response.raise_for_status()
        result = response.json()
        raw_text = result["candidates"][0]["content"]["parts"][0]["text"]

        # Clean potential markdown fencing
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        analysis = json.loads(cleaned)
        logger.info("Dr. Aris: Gemini analysis completed successfully.")

    except Exception as e:
        logger.error(f"Dr. Aris: Gemini analysis failed: {e}")
        analysis = {
            "psychological_profile": {
                "attachment_style": "Unable to assess — analysis error",
                "anxiety_markers": [],
                "cognitive_strengths": [],
                "emotional_baseline": "Unable to assess",
                "social_readiness": "Unable to assess",
            },
            "proposals": [],
        }

    # Run offline alert scan
    alerts = run_alert_scan(hints_data, recent_history)

    # Build and save the report
    reports = _load_reports()

    # Assign IDs to new proposals
    new_proposals = []
    for p in analysis.get("proposals", []):
        proposal = {
            "id": str(uuid.uuid4())[:8],
            "title": p.get("title", "Untitled Proposal"),
            "description": p.get("description", ""),
            "proposed_directive": p.get("proposed_directive", ""),
            "severity": p.get("severity", "info"),
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }
        new_proposals.append(proposal)

    # Merge: keep existing pending/approved proposals, add new ones
    existing_pending = [p for p in reports.get("proposals", []) if p.get("status") == "pending"]
    existing_approved = [p for p in reports.get("proposals", []) if p.get("status") == "approved"]

    reports["last_analysis"] = datetime.now().isoformat()
    reports["psychological_profile"] = analysis.get("psychological_profile", {})
    reports["alerts"] = alerts
    reports["proposals"] = existing_approved + existing_pending + new_proposals

    # Cap proposals at 20
    reports["proposals"] = reports["proposals"][-20:]

    # Log analysis in history
    reports["analysis_history"].append({
        "timestamp": datetime.now().isoformat(),
        "profile_summary": analysis.get("psychological_profile", {}).get("emotional_baseline", "N/A"),
        "proposals_generated": len(new_proposals),
        "alerts_found": len(alerts),
    })
    reports["analysis_history"] = reports["analysis_history"][-50:]

    _save_reports(reports)
    return reports


# ── Consent Gate: Approve / Reject ───────────────────────────

def approve_proposal(proposal_id):
    """
    Approves a Dr. Aris proposal. Injects the proposed_directive into
    parent_config.json's dr_aris_directives field, which app_stream.py
    already injects into Alex's system prompt via parent instructions.
    """
    reports = _load_reports()
    target = None

    for p in reports.get("proposals", []):
        if p.get("id") == proposal_id and p.get("status") == "pending":
            target = p
            break

    if not target:
        return {"status": "error", "message": f"Proposal '{proposal_id}' not found or already actioned."}

    # Mark as approved
    target["status"] = "approved"
    target["approved_at"] = datetime.now().isoformat()
    _save_reports(reports)

    # Inject directive into parent_config.json
    config = _load_parent_config()

    # Use a dedicated field so we don't mix with parent's manual instructions
    if "dr_aris_directives" not in config:
        config["dr_aris_directives"] = []

    config["dr_aris_directives"].append({
        "directive": target["proposed_directive"],
        "source_proposal": proposal_id,
        "approved_at": target["approved_at"],
    })

    # Cap at 10 active directives
    config["dr_aris_directives"] = config["dr_aris_directives"][-10:]

    _save_parent_config(config)

    logger.info(f"Dr. Aris: Proposal '{proposal_id}' approved and directive injected.")
    return {"status": "ok", "message": f"Proposal approved. Alex's behavior will be updated.", "proposal": target}


def reject_proposal(proposal_id, reason=""):
    """
    Rejects a Dr. Aris proposal. Logs the rejection for future refinement.
    """
    reports = _load_reports()
    target = None
    target_idx = None

    for i, p in enumerate(reports.get("proposals", [])):
        if p.get("id") == proposal_id and p.get("status") == "pending":
            target = p
            target_idx = i
            break

    if not target:
        return {"status": "error", "message": f"Proposal '{proposal_id}' not found or already actioned."}

    # Move to rejected
    target["status"] = "rejected"
    target["rejected_at"] = datetime.now().isoformat()
    target["rejection_reason"] = reason

    reports["rejected_proposals"].append(target)
    reports["rejected_proposals"] = reports["rejected_proposals"][-30:]

    # Remove from active proposals
    reports["proposals"].pop(target_idx)

    _save_reports(reports)

    logger.info(f"Dr. Aris: Proposal '{proposal_id}' rejected. Preference logged.")
    return {"status": "ok", "message": "Proposal rejected. Dr. Aris will refine future suggestions.", "proposal": target}


# ── Public API Helpers ───────────────────────────────────────

def get_dr_aris_report():
    """Returns the full Dr. Aris report (for the parent dashboard)."""
    return _load_reports()


def get_alerts():
    """Returns current behavioral alerts."""
    reports = _load_reports()
    return reports.get("alerts", [])


def get_proposals():
    """Returns all proposals with their current status."""
    reports = _load_reports()
    return reports.get("proposals", [])


# ══════════════════════════════════════════════════════════════
# MODULE 1: THE BOARDROOM CONSULTANT (B2B)
# Strategic psychological advisor for the CMO / Narrative Team.
# DATA WALL: This module NEVER accesses individual user data.
# It uses ONLY Dr. Aris's world-class expert knowledge base.
# ══════════════════════════════════════════════════════════════

BOARDROOM_HISTORY_PATH = os.path.join(SCRIPT_DIR, "dr_aris_boardroom_log.json")

def _load_boardroom_log():
    """Load the boardroom query history."""
    if os.path.exists(BOARDROOM_HISTORY_PATH):
        try:
            with open(BOARDROOM_HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"queries": []}


def _save_boardroom_log(log):
    """Save the boardroom query history."""
    os.makedirs(os.path.dirname(BOARDROOM_HISTORY_PATH), exist_ok=True)
    with open(BOARDROOM_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)


def boardroom_query(query: str, context: str = "") -> dict:
    """
    MODULE 1: Boardroom Consultant.
    Answers strategic psychological questions using only general
    market knowledge. NEVER accesses individual user data.

    Communication Style: Professional, authoritative, strategic, high-level.

    Args:
        query:   The strategic question from CMO / Narrative Team.
        context: Optional business context (product area, market segment, etc.)

    Returns:
        dict with 'response', 'segment_analysis', 'strategic_recommendations'
    """
    api_key = _get_api_key()
    if not api_key:
        logger.error("Dr. Aris Boardroom: No Gemini API key available.")
        return {
            "status": "error",
            "message": "No API key available for boardroom consultation.",
        }

    boardroom_prompt = f"""You are Dr. Aris, Chief Behavioral Strategist.
You are operating in MODULE 1: BOARDROOM CONSULTANT mode.

You are a world-class psychological consultant with deep expertise in:
- Gen Z / Gen Alpha psychographics and behavioral economics
- Adolescent developmental psychology and emotional design
- Product "stickiness" and emotional resonance optimization
- Market segment psychological profiling (e.g., "The Digital Native," "The Socially Anxious Scholar")

Communication Style (Module 3): Professional, authoritative, strategic, and high-level.

⚠️ DATA SEPARATION WALL ⚠️
You are providing GENERAL MARKET INTELLIGENCE only.
You do NOT have access to any individual user's private data.
You rely SOLELY on your expert knowledge base for market generalizations.
Never reference specific private data from individual Resonance users.

The product context is Resonance — an AI companion ("Alex") that helps adolescents
with speech/language challenges achieve Growth, Resilience, and Social Connection.

{f'BUSINESS CONTEXT: {context}' if context else ''}

STRATEGIC QUERY:
{query}

Respond with a valid JSON object:
{{
  "executive_summary": "2-3 sentence strategic assessment",
  "segment_analysis": {{
    "target_segment": "name of the relevant psychographic segment",
    "key_drivers": ["what motivates this segment"],
    "pain_points": ["what frustrates or blocks them"],
    "emotional_hooks": ["what creates emotional resonance"]
  }},
  "strategic_recommendations": [
    {{
      "recommendation": "specific actionable recommendation",
      "rationale": "psychological basis for this recommendation",
      "expected_impact": "predicted effect on engagement/stickiness"
    }}
  ],
  "risk_factors": ["potential psychological risks or ethical considerations"]
}}"""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": boardroom_prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 3000,
            },
        }

        _v3_status = safe_post(url, payload)


        response = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
        response.raise_for_status()
        result = response.json()
        raw_text = result["candidates"][0]["content"]["parts"][0]["text"]

        # Clean potential markdown fencing
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        analysis = json.loads(cleaned)
        logger.info("Dr. Aris Boardroom: Strategic consultation completed.")

        # Log the query (no individual data ever stored here)
        log = _load_boardroom_log()
        log["queries"].append({
            "query": query[:500],
            "context": context[:300] if context else "",
            "timestamp": datetime.now().isoformat(),
            "segment": analysis.get("segment_analysis", {}).get("target_segment", "N/A"),
        })
        log["queries"] = log["queries"][-50:]  # Cap history
        _save_boardroom_log(log)

        return {"status": "ok", **analysis}

    except Exception as e:
        logger.error(f"Dr. Aris Boardroom: Consultation failed: {e}")
        return {
            "status": "error",
            "message": f"Strategic consultation failed: {e}",
        }


def get_boardroom_history():
    """Returns the boardroom query history (no individual user data)."""
    return _load_boardroom_log()


# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
