"""
CMO Agent — Persona Engine (Search-Grounded)
═════════════════════════════════════════════════
AI-powered audience persona builder with psychographic
profiling, buyer journey mapping, and segment analysis.

Layer 1: Gemini Search Grounding (real-time Google Search)
"""

import json
import os
from google import genai
from google.genai import types

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GROUNDING_TOOL = types.Tool(google_search=types.GoogleSearch())

PERSONA_PROMPT = """You are an elite audience researcher and consumer psychologist at a world-class marketing agency.
You have access to real-time internet search. USE IT to find current demographic data, consumer behavior trends, and market research reports.

Given the following product/company information, create detailed buyer personas.

INPUT:
{user_input}

ADDITIONAL CONTEXT:
{context}

Produce a JSON response with EXACTLY this structure:
{{
  "company_name": "string",
  "product_name": "string",
  "total_addressable_segments": "number — how many distinct segments identified",
  "personas": [
    {{
      "name": "string — a memorable first name for the persona",
      "title": "string — e.g. 'The Deliberate Trader', 'The Overwhelmed Founder'",
      "avatar_emoji": "string — a single emoji that represents this persona",
      "demographics": {{
        "age_range": "string — e.g. '28-42'",
        "income_range": "string — e.g. '$75K-$200K'",
        "education": "string",
        "location": "string — geographic tendency",
        "job_title": "string — typical role"
      }},
      "psychographics": {{
        "values": ["string — 3 core values"],
        "motivations": ["string — 3 key motivations"],
        "fears": ["string — 3 primary fears/anxieties"],
        "personality_traits": ["string — 4-5 personality descriptors"]
      }},
      "behavior_patterns": {{
        "daily_routine": "string — brief daily context",
        "information_sources": ["string — where they get info"],
        "purchase_behavior": "string — how they buy",
        "technology_comfort": "HIGH | MEDIUM | LOW",
        "decision_speed": "FAST | MODERATE | SLOW"
      }},
      "pain_points": [
        {{
          "pain": "string — the specific problem",
          "intensity": "CRITICAL | HIGH | MODERATE",
          "current_solution": "string — what they do now",
          "frustration": "string — emotional dimension"
        }}
      ],
      "goals": ["string — 3 key goals this product helps achieve"],
      "objections": ["string — 3 likely objections to purchasing"],
      "emotional_hooks": ["string — 3 messages that would resonate deeply"],
      "channels": {{
        "primary": ["string — 2-3 primary channels to reach them"],
        "secondary": ["string — 2-3 secondary channels"],
        "trigger_moments": ["string — 2-3 moments when they're most receptive"]
      }},
      "buyer_journey": {{
        "awareness_trigger": "string — what makes them realize they need a solution",
        "consideration_criteria": ["string — 3 things they evaluate"],
        "decision_driver": "string — the final thing that tips them to buy",
        "post_purchase_expectation": "string — what they expect after buying"
      }},
      "lifetime_value_potential": "HIGH | MEDIUM | LOW",
      "acquisition_difficulty": "HIGH | MEDIUM | LOW"
    }}
  ],
  "segment_prioritization": "string — which persona to target first and why",
  "cross_persona_insights": "string — patterns that span all personas"
}}

IMPORTANT: Return ONLY valid JSON. No markdown, no code fences.
Create 3-4 distinct, realistic personas. Make them feel like real people with genuine motivations and frustrations.
Use specific, vivid details — not generic marketing speak."""


async def generate_personas(user_input: str, context: str = "") -> dict:
    """Generate detailed audience personas."""
    client = get_client()
    
    prompt = PERSONA_PROMPT.format(
        user_input=user_input,
        context=context or "None provided"
    )
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[GROUNDING_TOOL],
            temperature=0.55,
            max_output_tokens=8192,
        )
    )
    
    text = response.text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end+1]
    
    try:
        result = json.loads(text)
        # Run Dr. Aris audit on the personas
        result = await dr_aris_audit(result)
        return result
    except json.JSONDecodeError:
        return {
            "error": "Failed to parse persona response",
            "raw_response": text[:2000]
        }


# ═══════════════════════════════════════════════════════════
#  DR. ARIS MODULE — Cognitive Bias & Emotional Trigger Auditor
#  The CMO's psychological intelligence edge
# ═══════════════════════════════════════════════════════════

DR_ARIS_PROMPT = """You are Dr. Aris — a behavioral strategist and consumer psychologist embedded in the CMO's intelligence engine.

You have just received a set of audience personas. Your job is to AUDIT them for:
1. Cognitive biases that can be ethically leveraged in messaging
2. Emotional triggers that drive purchase decisions
3. Psychological resistance patterns that could block conversion
4. Persuasion architecture recommendations

PERSONAS TO AUDIT:
{personas_json}

Produce a JSON response with EXACTLY this structure:
{{
  "dr_aris_audit": {{
    "audit_status": "COMPLETE",
    "psychological_profile_quality": "HIGH | MEDIUM | LOW",
    "persona_audits": [
      {{
        "persona_name": "string — name from the persona",
        "cognitive_biases": [
          {{
            "bias": "string — bias name (e.g. 'Loss Aversion', 'Social Proof', 'Anchoring')",
            "relevance": "HIGH | MEDIUM",
            "messaging_leverage": "string — how to ethically use this bias in marketing"
          }}
        ],
        "emotional_triggers": [
          {{
            "trigger": "string — emotional trigger",
            "intensity": "STRONG | MODERATE | SUBTLE",
            "activation_context": "string — when/where this trigger fires",
            "recommended_message": "string — example message that activates this trigger"
          }}
        ],
        "resistance_patterns": [
          {{
            "pattern": "string — what causes resistance",
            "counter_strategy": "string — how to overcome it"
          }}
        ],
        "persuasion_score": 0.0
      }}
    ],
    "cross_persona_patterns": ["string — psychological patterns common across all personas"],
    "strategic_recommendation": "string — Dr. Aris's top-level strategic recommendation for messaging"
  }}
}}

IMPORTANT: Return ONLY valid JSON. No markdown, no code fences.
Be specific, scientific, and ethical. Reference real cognitive biases by name.
The persuasion_score is 0.0-1.0 indicating how persuadable this persona is with the right messaging."""


async def dr_aris_audit(personas_data: dict) -> dict:
    """
    Dr. Aris Module: Audit personas for cognitive biases and emotional triggers.
    This is the CMO's unique psychological intelligence edge.
    """
    if "error" in personas_data or not personas_data.get("personas"):
        return personas_data
    
    client = get_client()
    
    # Extract persona summaries to send to Dr. Aris
    personas_summary = json.dumps(personas_data.get("personas", []), indent=2)[:6000]
    
    prompt = DR_ARIS_PROMPT.format(personas_json=personas_summary)
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[GROUNDING_TOOL],
                temperature=0.4,
                max_output_tokens=6144,
            )
        )
        
        text = response.text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end+1]
        
        audit = json.loads(text)
        # Merge Dr. Aris audit into the personas data
        personas_data["dr_aris_audit"] = audit.get("dr_aris_audit", audit)
        
    except Exception as e:
        personas_data["dr_aris_audit"] = {
            "audit_status": "PARTIAL",
            "error": f"Dr. Aris audit encountered an issue: {str(e)[:200]}",
            "strategic_recommendation": "Retry the audit for full psychological profiling."
        }
    
    return personas_data
