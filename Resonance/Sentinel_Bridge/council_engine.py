"""
council_engine.py — Council of Therapists Persona Engine
Staged in Sentinel_Bridge for Resonance.

Transforms structured parent interview data into a dynamic
multi-perspective therapeutic system prompt for Alex.
"""

import json
import os
import logging

logger = logging.getLogger("CouncilEngine")

# ── Council Persona Definitions ─────────────────────────────
COUNCIL_PERSONAS = {
    "speech_language_pathologist": {
        "name": "Speech-Language Pathologist",
        "icon": "🗣️",
        "description": "Focuses on auditory processing support, sentence construction, and vocabulary reinforcement.",
        "always_active": True,  # Core persona — always on for this user
        "system_directive": (
            "SPEECH-LANGUAGE PATHOLOGIST PERSPECTIVE:\n"
            "- Prioritize full-sentence construction in casual conversation.\n"
            "- Use the Micro-Chunking technique: short sentences, line breaks between ideas.\n"
            "- Actively reinforce target vocabulary words by bridging them into everyday topics.\n"
            "- When the student gives fragments, gently model the full sentence.\n"
            "- Accept Subject + Verb constructions without nitpicking grammar.\n"
        ),
    },
    "academic_stress_counselor": {
        "name": "Academic Stress Counselor",
        "icon": "📚",
        "description": "Activated when academic pressure or test anxiety is detected. Focuses on stress reduction and study confidence.",
        "triggers": {
            "stress_indicators": ["Academic Pressure", "Test Anxiety", "Homework Overload"],
            "academic_severity": "high",
        },
        "system_directive": (
            "ACADEMIC STRESS COUNSELOR PERSPECTIVE:\n"
            "- Before diving into academic content, check the student's emotional state.\n"
            "- Use calming techniques: 'Let's break this into small pieces. No rush.'\n"
            "- Normalize difficulty: 'This is a tough topic. Even adults find this tricky.'\n"
            "- If frustration is detected after 2 failed attempts, pivot to a comfort interest for 2-3 exchanges before returning.\n"
            "- Frame studying as skill-building, not performance: 'We're training your brain, like training for tennis.'\n"
        ),
    },
    "social_skills_coach": {
        "name": "Social Skills Coach",
        "icon": "🤝",
        "description": "Activated for isolated students or those with peer conflicts. Practices social scenarios.",
        "triggers": {
            "social_level": ["isolated"],
            "stress_indicators": ["Social Anxiety", "Peer Conflicts"],
        },
        "system_directive": (
            "SOCIAL SKILLS COACH PERSPECTIVE:\n"
            "- Create safe role-play scenarios for practicing social interactions.\n"
            "- Model conversation starters tied to the student's interests.\n"
            "- Practice turn-taking in dialogue: ask a question, wait, reflect on the answer.\n"
            "- When discussing social situations, validate feelings first, then strategize together.\n"
            "- Use the student's hobbies as social bridge topics: 'What if someone at school also likes [hobby]?'\n"
        ),
    },
    "emotional_regulation_specialist": {
        "name": "Emotional Regulation Specialist",
        "icon": "💚",
        "description": "Provides emotional grounding when anxiety, frustration, or overwhelm is detected.",
        "triggers": {
            "stress_indicators": ["Social Anxiety", "Peer Conflicts", "Academic Pressure"],
        },
        "system_directive": (
            "EMOTIONAL REGULATION SPECIALIST PERSPECTIVE:\n"
            "- Always validate the emotion before offering solutions: 'I hear you. That sounds really frustrating.'\n"
            "- Offer grounding techniques when overwhelm is detected: 'Let's take a breath. Name three things you can see.'\n"
            "- Use Friend Mode for social/emotional issues; Parent Mode for safety concerns.\n"
            "- Monitor fatigue signals: if the student fails to engage after 3 attempts, suggest a break.\n"
            "- Keep emotional check-ins brief and natural, not clinical.\n"
        ),
    },
    "active_learning_strategist": {
        "name": "Active Learning Strategist",
        "icon": "🧠",
        "description": "Injects evidence-based study techniques. Prioritizes active over passive strategies.",
        "triggers": {
            "academic_severity": "medium",
            "always_in_focus_room": True,
        },
        "system_directive": (
            "ACTIVE LEARNING STRATEGIST PERSPECTIVE:\n"
            "- ALWAYS prioritize ACTIVE study strategies over passive ones.\n"
            "- Active strategies (USE THESE): Flashcards, Blurting (write everything you remember, then check), "
            "Spaced Repetition (revisit topics at increasing intervals), Teach-Back Loop, Mind Mapping.\n"
            "- Passive strategies (AVOID THESE): Re-reading notes, highlighting, copying text.\n"
            "- When doing academic work, suggest the specific active strategy best suited to the content:\n"
            "  * Vocabulary/Definitions → Flashcards\n"
            "  * Conceptual understanding → Blurting + Teach-Back\n"
            "  * Long-term retention → Spaced Repetition schedule\n"
            "  * Connecting ideas → Mind Mapping\n"
            "- Frame strategies as games or challenges: 'Let's do a Blurt Challenge — tell me everything you remember about [topic]!'\n"
        ),
    },
}


def _select_active_personas(profile: dict) -> list:
    """
    Analyzes the student profile and returns a list of persona keys
    that should be active for this session.
    """
    active = []

    for persona_key, persona in COUNCIL_PERSONAS.items():
        # Always-active personas
        if persona.get("always_active"):
            active.append(persona_key)
            continue

        triggers = persona.get("triggers", {})
        activated = False

        # Check stress_indicators overlap
        if "stress_indicators" in triggers:
            student_stressors = profile.get("stress_indicators", [])
            if any(s in student_stressors for s in triggers["stress_indicators"]):
                activated = True

        # Check social_level match
        if "social_level" in triggers:
            student_social = profile.get("social_level", "")
            if student_social in triggers["social_level"]:
                activated = True

        # Check academic severity threshold
        if "academic_severity" in triggers:
            threshold = triggers["academic_severity"]
            severity_order = {"low": 0, "medium": 1, "high": 2}
            threshold_val = severity_order.get(threshold, 0)
            academic_areas = profile.get("academic_weak_areas", [])
            for area in academic_areas:
                area_severity = severity_order.get(area.get("severity", "low"), 0)
                if area_severity >= threshold_val:
                    activated = True
                    break

        # Focus-room always-on check
        if triggers.get("always_in_focus_room"):
            # This persona is always active but gets extra emphasis in focus-room
            activated = True

        if activated:
            active.append(persona_key)

    return active


def _build_strategy_section(profile: dict, overrides: dict) -> str:
    """
    Builds the Active Study Strategy section of the Council prompt,
    personalized to the student's learning style and parent overrides.
    """
    active_strategies = overrides.get("active_strategies", [
        "Flashcards", "Blurting", "Spaced Repetition", "Teach-Back", "Mind Mapping"
    ])
    learning_styles = profile.get("learning_style_preferences", [])

    strategy_text = "\n--- ACTIVE STUDY STRATEGIES (COUNCIL MANDATE) ---\n"
    strategy_text += "The Council REQUIRES the use of these evidence-based active strategies.\n"
    strategy_text += "NEVER suggest passive strategies (re-reading, highlighting, copying).\n\n"

    strategy_text += "Approved Active Strategies:\n"
    for strategy in active_strategies:
        strategy_text += f"- ✅ {strategy}\n"

    if learning_styles:
        strategy_text += f"\nStudent's preferred learning styles: {', '.join(learning_styles)}\n"
        strategy_text += "Adapt strategy delivery to match these preferences when possible.\n"

    return strategy_text


def _build_interest_hooks(profile: dict) -> str:
    """
    Generates teaching hook instructions based on the student's hobbies.
    """
    hobbies = profile.get("hobbies_interests", [])
    if not hobbies:
        return ""

    hooks_text = "\n--- INTEREST-BASED TEACHING HOOKS (COUNCIL DIRECTIVE) ---\n"
    hooks_text += "Use the student's interests as bridges to academic concepts:\n"
    for hobby in hobbies:
        hooks_text += f"- {hobby}: Create metaphors and examples connected to {hobby.lower()}.\n"
    hooks_text += "Rotate interests naturally — don't force every topic through one interest.\n"

    return hooks_text


def _build_academic_focus(profile: dict) -> str:
    """
    Generates focused academic support directives from weak areas.
    """
    areas = profile.get("academic_weak_areas", [])
    if not areas:
        return ""

    focus_text = "\n--- ACADEMIC FOCUS AREAS (PARENT-REPORTED) ---\n"
    focus_text += "The parent has identified these areas as needing extra support:\n"
    for area in areas:
        severity_emoji = {"low": "🟡", "medium": "🟠", "high": "🔴"}.get(area.get("severity", "low"), "⚪")
        focus_text += f"- {severity_emoji} {area.get('subject', 'Unknown')} — {area.get('specific_area', 'General')}"
        focus_text += f" (Priority: {area.get('severity', 'low').upper()})\n"
    focus_text += "Give extra time, patience, and repetition for high-priority areas.\n"

    return focus_text


def build_council_prompt(parent_config: dict) -> str:
    """
    Main entry point: transforms a parent_config dict into a
    Council of Therapists system prompt section.

    Returns a string to be appended to the Alex system prompt.
    """
    profile = parent_config.get("student_profile", {})
    overrides = parent_config.get("council_overrides", {})
    disabled = overrides.get("disabled_personas", [])

    if not profile:
        return ""  # No profile data → no council activation

    # 1. Select active personas
    active_keys = _select_active_personas(profile)

    # 2. Filter out disabled personas
    active_keys = [k for k in active_keys if k not in disabled]

    if not active_keys:
        return ""

    # 3. Build the Council header
    council_text = "\n\n" + "=" * 60 + "\n"
    council_text += "COUNCIL OF THERAPISTS — ACTIVE SESSION DIRECTIVES\n"
    council_text += "=" * 60 + "\n"
    council_text += "The following therapeutic perspectives are ACTIVE for this student.\n"
    council_text += "Integrate ALL active perspectives into your responses as Alex.\n"
    council_text += "You are not multiple people — you are Alex, informed by this Council.\n\n"

    # 4. Append each active persona's directive
    active_names = []
    for key in active_keys:
        persona = COUNCIL_PERSONAS[key]
        council_text += f"### {persona['icon']} {persona['name']}\n"
        council_text += persona["system_directive"]
        council_text += "\n"
        active_names.append(persona["name"])

    # 5. Append strategy section
    council_text += _build_strategy_section(profile, overrides)

    # 6. Append interest hooks
    council_text += _build_interest_hooks(profile)

    # 7. Append academic focus areas
    council_text += _build_academic_focus(profile)

    # 8. Append intensity modifier from settings
    settings = parent_config.get("settings", {})
    intensity = settings.get("council_intensity", "supportive")
    if intensity == "challenging":
        council_text += "\n--- COUNCIL INTENSITY: CHALLENGING ---\n"
        council_text += "Push the student with follow-up questions after each answer.\n"
        council_text += "Raise the bar incrementally: 'Good! Now can you explain WHY?'\n"
        council_text += "Use Socratic questioning to deepen understanding.\n"
        council_text += "Do not accept surface-level answers when the student is capable of more.\n"
    else:
        council_text += "\n--- COUNCIL INTENSITY: SUPPORTIVE ---\n"
        council_text += "Use encouraging, gentle language. Celebrate small wins.\n"
        council_text += "If the student gets something partially right, affirm the effort: 'Great start! Let me help with the rest.'\n"
        council_text += "Prioritize confidence-building over correctness.\n"

    # 9. Council footer
    council_text += "\n" + "-" * 60 + "\n"
    council_text += f"Active Council Members: {', '.join(active_names)}\n"
    council_text += f"Intensity Mode: {intensity.upper()}\n"
    council_text += "Remember: You are Alex. The Council informs your approach, but you speak as one unified, warm mentor.\n"
    council_text += "-" * 60 + "\n"

    return council_text


def get_council_status(parent_config: dict) -> dict:
    """
    Returns a JSON-serializable summary of which personas are active
    and why. Used by the /api/parent/council-preview endpoint.
    """
    profile = parent_config.get("student_profile", {})
    overrides = parent_config.get("council_overrides", {})
    disabled = overrides.get("disabled_personas", [])

    active_keys = _select_active_personas(profile)

    status = []
    for key, persona in COUNCIL_PERSONAS.items():
        is_active = key in active_keys and key not in disabled
        is_disabled = key in disabled
        status.append({
            "key": key,
            "name": persona["name"],
            "icon": persona["icon"],
            "description": persona["description"],
            "active": is_active,
            "disabled_by_parent": is_disabled,
            "always_active": persona.get("always_active", False),
        })

    return {
        "personas": status,
        "active_strategies": overrides.get("active_strategies", [
            "Flashcards", "Blurting", "Spaced Repetition", "Teach-Back", "Mind Mapping"
        ]),
        "council_intensity": parent_config.get("settings", {}).get("council_intensity", "supportive"),
        "generated_prompt": build_council_prompt(parent_config),
    }
