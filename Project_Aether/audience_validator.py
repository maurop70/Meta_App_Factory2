"""
Audience Validator — Aether Platform Module
==============================================
Project Aether | Meta_App_Factory

Shared service that validates app content/UX against target audience personas
using AI-powered simulation. All child apps inherit this capability.

Usage:
    from Project_Aether.audience_validator import AudienceValidator

    validator = AudienceValidator()
    result = validator.validate_conversation(messages, "teen_learner")
    print(result["overall_score"])  # 1-10
"""

import os
import json
import glob
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

# ── Paths ─────────────────────────────────────────
AETHER_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(AETHER_DIR, "audience_profiles")

# ── Gemini Config ─────────────────────────────────
VALIDATION_MODEL = "gemini-2.5-flash"


@dataclass
class AudienceProfile:
    """Target audience persona for validation."""
    id: str
    name: str
    age_range: str
    description: str
    interests: List[str] = field(default_factory=list)
    tone_keywords: List[str] = field(default_factory=list)
    deal_breakers: List[str] = field(default_factory=list)
    accessibility_needs: List[str] = field(default_factory=list)
    evaluation_prompt: str = ""

    @classmethod
    def from_json(cls, filepath: str) -> "AudienceProfile":
        """Load a profile from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            id=data.get("id", os.path.splitext(os.path.basename(filepath))[0]),
            name=data["name"],
            age_range=data["age_range"],
            description=data["description"],
            interests=data.get("interests", []),
            tone_keywords=data.get("tone_keywords", []),
            deal_breakers=data.get("deal_breakers", []),
            accessibility_needs=data.get("accessibility_needs", []),
            evaluation_prompt=data.get("evaluation_prompt", ""),
        )


@dataclass
class ValidationResult:
    """Structured result from audience validation."""
    profile_id: str
    profile_name: str
    engagement_score: float
    tone_match_score: float
    accessibility_score: float
    overall_score: float
    feedback: str
    deal_breaker_flags: List[str] = field(default_factory=list)
    timestamp: str = ""
    app_name: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "scores": {
                "engagement": self.engagement_score,
                "tone_match": self.tone_match_score,
                "accessibility": self.accessibility_score,
                "overall": self.overall_score,
            },
            "feedback": self.feedback,
            "deal_breaker_flags": self.deal_breaker_flags,
            "pass": self.overall_score >= 7.0 and len(self.deal_breaker_flags) == 0,
            "timestamp": self.timestamp,
            "app_name": self.app_name,
        }

    def summary(self) -> str:
        """Human-readable summary."""
        status = "✅ PASS" if self.overall_score >= 7.0 and not self.deal_breaker_flags else "❌ FAIL"
        lines = [
            f"╔══ Audience Validation Report ══╗",
            f"  Profile:       {self.profile_name} ({self.profile_id})",
            f"  App:           {self.app_name or 'N/A'}",
            f"  Status:        {status}",
            f"  ──────────────────────────────",
            f"  Engagement:    {self.engagement_score}/10",
            f"  Tone Match:    {self.tone_match_score}/10",
            f"  Accessibility: {self.accessibility_score}/10",
            f"  Overall:       {self.overall_score}/10",
            f"  ──────────────────────────────",
        ]
        if self.deal_breaker_flags:
            lines.append(f"  ⚠️  Deal Breakers: {', '.join(self.deal_breaker_flags)}")
        lines.append(f"  Feedback:")
        for line in self.feedback.strip().split("\n"):
            lines.append(f"    {line}")
        lines.append(f"╚═══════════════════════════════╝")
        return "\n".join(lines)


class AudienceValidator:
    """
    Validates app content against audience personas using Gemini.
    
    This is a shared Aether service. Child apps call it via:
        validator = AudienceValidator()
        result = validator.validate_conversation(messages, "teen_learner")
    """

    # ── Audience Intent Detection Patterns ─────────────────────
    # Fast keyword/regex patterns — NO API call, runs instantly
    AUDIENCE_PATTERNS = [
        # Direct audience mentions
        (r'\b(?:for|aimed at|designed for|target(?:ing|ed)?(?:\s+at)?)\s+(.{5,60}?)(?:\.|,|!|\?|$)', 0.9),
        (r'\b(?:target|intended)\s+audience\s+(?:is|are|will be|:)\s*(.{5,60}?)(?:\.|,|!|\?|$)', 0.95),
        (r'\b(?:users?|customers?|clients?|readers?|viewers?|listeners?)\s+(?:are|will be|include)\s+(.{5,60}?)(?:\.|,|!|\?|$)', 0.85),
        (r'\b(?:building|creating|making|developing)\s+(?:an?\s+)?(?:app|product|platform|tool|site|website|presentation|pitch|brochure|book)\s+for\s+(.{5,60}?)(?:\.|,|!|\?|$)', 0.95),
        (r'\b(?:present(?:ing|ation)?|pitch(?:ing)?)\s+(?:to|for)\s+(.{5,60}?)(?:\.|,|!|\?|$)', 0.85),
        (r'\b(?:audience|demographic|market\s+segment)\s+(?:is|:|—)\s*(.{5,60}?)(?:\.|,|!|\?|$)', 0.9),
        (r'\bwritten\s+for\s+(.{5,60}?)(?:\.|,|!|\?|$)', 0.85),
        (r'\b(?:appealing?|cater(?:ing)?)\s+to\s+(.{5,60}?)(?:\.|,|!|\?|$)', 0.85),
        (r'\b(?:teenagers?|teens?|kids?|children|parents?|seniors?|professionals?|students?|teachers?|investors?|traders?)\b', 0.7),
    ]

    def __init__(self, api_key: str = None):
        self.profiles: Dict[str, AudienceProfile] = {}
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._load_profiles()

    # ══════════════════════════════════════════════════════════════
    #  AUDIENCE INTENT DETECTION — Fast, No API Call
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def detect_audience_intent(text: str) -> dict:
        """
        Detect if text mentions a target audience. Runs instantly (no API call).

        Returns:
            {
                "detected": bool,
                "audience_hint": str,   # extracted audience description
                "confidence": float,    # 0.0-1.0
                "trigger_phrase": str,   # the matched text
            }
        """
        import re
        if not text or len(text) < 10:
            return {"detected": False, "audience_hint": "", "confidence": 0.0, "trigger_phrase": ""}

        text_lower = text.lower().strip()
        best_match = {"detected": False, "audience_hint": "", "confidence": 0.0, "trigger_phrase": ""}

        for pattern, confidence in AudienceValidator.AUDIENCE_PATTERNS:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match and confidence > best_match["confidence"]:
                # Extract audience hint from capture group if available
                hint = match.group(1).strip() if match.lastindex else match.group(0).strip()
                # Clean up the hint
                hint = re.sub(r'^(an?|the|some|many|all)\s+', '', hint)
                hint = hint.rstrip('.,!?;:')
                if len(hint) < 3:
                    continue
                best_match = {
                    "detected": True,
                    "audience_hint": hint,
                    "confidence": confidence,
                    "trigger_phrase": match.group(0).strip(),
                }

        return best_match

    def _load_profiles(self):
        """Load all audience profiles from the profiles directory."""
        if not os.path.isdir(PROFILES_DIR):
            print(f"[AudienceValidator] Profiles directory not found: {PROFILES_DIR}")
            return
        for filepath in glob.glob(os.path.join(PROFILES_DIR, "*.json")):
            try:
                profile = AudienceProfile.from_json(filepath)
                self.profiles[profile.id] = profile
                print(f"[AudienceValidator] Loaded profile: {profile.id} ({profile.name})")
            except Exception as e:
                print(f"[AudienceValidator] Error loading {filepath}: {e}")

    def list_profiles(self) -> List[dict]:
        """Return available audience profiles."""
        return [
            {
                "id": p.id,
                "name": p.name,
                "age_range": p.age_range,
                "description": p.description,
            }
            for p in self.profiles.values()
        ]

    def get_profile(self, profile_id: str) -> Optional[AudienceProfile]:
        """Get a specific audience profile."""
        return self.profiles.get(profile_id)

    # ══════════════════════════════════════════════════════════════
    #  AI PROFILE GENERATION — Deep_Crawler + Gemini Synthesis
    # ══════════════════════════════════════════════════════════════

    def generate_profile(
        self,
        audience_description: str,
        profile_id: str = None,
        context: str = "",
        use_web_research: bool = True,
    ) -> AudienceProfile:
        """
        Auto-generate an audience profile from a developer's description.

        Uses a 2-stage pipeline:
          1. Deep_Crawler web-mines market best practices for the target audience
          2. Gemini synthesizes research into a structured profile JSON

        This is a universal tool — use it for apps, presentations, pitches,
        brochures, books, or any content that needs audience alignment.

        Args:
            audience_description: e.g. "Pet owners aged 25-40 who use mobile apps"
            profile_id: Optional custom ID (auto-generated from description if not set)
            context: Optional context about the product/content being built
            use_web_research: If True, uses Deep_Crawler for real web research first

        Returns:
            AudienceProfile saved to audience_profiles/ and loaded into memory
        """
        if not profile_id:
            # Auto-generate ID from description
            profile_id = audience_description.lower()
            profile_id = "".join(c if c.isalnum() or c == " " else "" for c in profile_id)
            profile_id = "_".join(profile_id.split()[:4])

        print(f"\n🔬 Generating audience profile: '{audience_description}'")
        print(f"   Profile ID: {profile_id}")

        # ── Stage 1: Deep_Crawler Web Research ──────────────────
        web_research = ""
        if use_web_research:
            web_research = self._crawl_audience_research(audience_description, context)

        # ── Stage 2: Gemini Profile Synthesis ───────────────────
        profile_data = self._synthesize_profile(audience_description, profile_id, context, web_research)

        # Save to disk
        filepath = os.path.join(PROFILES_DIR, f"{profile_id}.json")
        os.makedirs(PROFILES_DIR, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)
        print(f"   💾 Saved: {filepath}")

        # Load into memory
        profile = AudienceProfile.from_json(filepath)
        self.profiles[profile.id] = profile
        print(f"   ✅ Profile '{profile.id}' ready for use\n")
        return profile

    def _crawl_audience_research(self, audience_description: str, context: str) -> str:
        """Stage 1: Use Deep_Crawler to web-mine audience best practices."""
        import requests as req

        # Deep_Crawler webhook (same as CEO/CTO — shared Gemini Flash endpoint)
        CRAWLER_WEBHOOK = "https://humanresource.app.n8n.cloud/webhook/gemini-flash"

        research_prompt = f"""You are the Deep Crawler — a specialist in high-velocity web mining.

RESEARCH TARGET: Best practices for engaging the following target audience:
"{audience_description}"

{f'PRODUCT CONTEXT: {context}' if context else ''}

EXECUTE:
1. Research what successful apps, products, and content creators do to engage this specific audience
2. Identify the top 5 demographic traits, behavioral patterns, and preferences
3. Find the most common UX deal-breakers that cause this audience to abandon a product
4. Research the tone, language style, and communication patterns that resonate with this audience
5. Identify accessibility considerations specific to this demographic
6. Find real-world examples of products that succeed or fail with this audience

OUTPUT: Structured research findings as a detailed report. Include specific data points and patterns.
Do NOT hallucinate — if data is limited, say so explicitly."""

        print("   🕷️  Stage 1: Deep_Crawler researching audience best practices...")
        try:
            resp = req.post(
                CRAWLER_WEBHOOK,
                json={"prompt": research_prompt},
                timeout=45,
            )
            if resp.status_code == 200:
                data = resp.json()
                research = data.get("output", data.get("response", data.get("text", str(data))))
                print(f"   📊 Research collected: {len(research)} chars")
                return research
            else:
                print(f"   ⚠️  Crawler returned {resp.status_code}, falling back to Gemini-only")
                return ""
        except Exception as e:
            print(f"   ⚠️  Crawler unavailable ({e}), falling back to Gemini-only")
            return ""

    def _synthesize_profile(
        self, audience_description: str, profile_id: str, context: str, web_research: str
    ) -> dict:
        """Stage 2: Gemini synthesizes research into a structured profile JSON."""
        research_section = ""
        if web_research:
            research_section = f"""
## Web Research Findings (from Deep_Crawler)
Use these real market findings to inform your profile. Prioritize data-backed insights:
---
{web_research[:4000]}
---
"""

        synthesis_prompt = f"""You are an expert UX researcher and audience strategist.

A developer has described their target audience:
"{audience_description}"

{f'Product/content context: {context}' if context else ''}
{research_section}

Generate a comprehensive audience profile based on market best practices.
This profile will be used to validate apps, presentations, pitches, brochures, and books.

Respond ONLY with valid JSON (no markdown, no code fences):
{{
  "id": "{profile_id}",
  "name": "<concise audience name, e.g. 'Pet Parent'>",
  "age_range": "<e.g. '25-40'>",
  "description": "<2-3 sentence description of this audience persona, including their motivations and pain points>",
  "interests": ["<list 6-8 interests relevant to this audience>"],
  "tone_keywords": ["<list 6-8 tone descriptors that resonate: e.g. 'warm', 'trustworthy', 'playful'>"],
  "deal_breakers": [
    "<list 5-7 things that would cause this audience to immediately reject the content>",
    "<be specific and actionable, based on real market patterns>"
  ],
  "accessibility_needs": [
    "<list 4-5 accessibility or usability requirements specific to this demographic>"
  ],
  "evaluation_prompt": "<a 2-3 sentence instruction telling the AI evaluator what to pay special attention to when validating content for this audience. Reference real-world expectations.>"
}}

Make this profile comprehensive, specific, and grounded in real market behavior.
Generic profiles are useless — be opinionated and data-driven."""

        print("   🧠 Stage 2: Gemini synthesizing profile from research...")
        response = self._call_gemini(synthesis_prompt)

        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(cleaned)
            # Ensure required fields
            data.setdefault("id", profile_id)
            data.setdefault("name", audience_description[:40])
            data.setdefault("age_range", "varies")
            data.setdefault("description", audience_description)
            return data
        except json.JSONDecodeError:
            # Fallback: create basic profile from description
            print("   ⚠️  Failed to parse Gemini response, creating basic profile")
            return {
                "id": profile_id,
                "name": audience_description[:40],
                "age_range": "varies",
                "description": audience_description,
                "interests": [],
                "tone_keywords": [],
                "deal_breakers": [],
                "accessibility_needs": [],
                "evaluation_prompt": f"Evaluate as if you are: {audience_description}",
            }


    def validate(self, content: str, profile_id: str, app_name: str = "") -> ValidationResult:
        """
        Validate a piece of content against an audience profile.
        
        Args:
            content: The text content to validate (UI text, response, etc.)
            profile_id: ID of the audience profile to validate against
            app_name: Name of the app being validated
            
        Returns:
            ValidationResult with scores and feedback
        """
        profile = self.profiles.get(profile_id)
        if not profile:
            available = ", ".join(self.profiles.keys()) or "none"
            raise ValueError(f"Profile '{profile_id}' not found. Available: {available}")

        prompt = self._build_validation_prompt(content, profile, "content")
        response = self._call_gemini(prompt)
        return self._parse_response(response, profile, app_name)

    def validate_conversation(self, messages: List[dict], profile_id: str, app_name: str = "") -> ValidationResult:
        """
        Validate a full conversation transcript against an audience profile.
        
        Args:
            messages: List of { role: str, text: str } message objects
            profile_id: ID of the audience profile
            app_name: Name of the app being validated
            
        Returns:
            ValidationResult with scores and feedback
        """
        profile = self.profiles.get(profile_id)
        if not profile:
            available = ", ".join(self.profiles.keys()) or "none"
            raise ValueError(f"Profile '{profile_id}' not found. Available: {available}")

        # Format conversation for evaluation
        transcript = "\n".join(
            f"[{m.get('role', 'unknown').upper()}]: {m.get('text', '')}"
            for m in messages if m.get("text")
        )
        prompt = self._build_validation_prompt(transcript, profile, "conversation")
        response = self._call_gemini(prompt)
        return self._parse_response(response, profile, app_name)

    def _build_validation_prompt(self, content: str, profile: AudienceProfile, content_type: str) -> str:
        """Build the Gemini prompt for audience validation."""
        deal_breaker_text = "\n".join(f"  - {db}" for db in profile.deal_breakers) if profile.deal_breakers else "  None specified"
        tone_text = ", ".join(profile.tone_keywords) if profile.tone_keywords else "No specific tone specified"
        accessibility_text = "\n".join(f"  - {a}" for a in profile.accessibility_needs) if profile.accessibility_needs else "  None specified"

        custom_eval = f"\n\nAdditional Evaluation Criteria:\n{profile.evaluation_prompt}" if profile.evaluation_prompt else ""

        return f"""You are an expert UX researcher simulating a target audience member.

## Your Persona
You are a {profile.age_range} year old person matching this profile:
- Name: {profile.name}
- Description: {profile.description}
- Interests: {', '.join(profile.interests)}
- Preferred Tone: {tone_text}

## Your Task
Evaluate the following {content_type} as if you are this person. Would this {content_type} engage you? Would it feel natural? Would it meet your needs?

## Deal Breakers (automatic fail if detected)
{deal_breaker_text}

## Accessibility Requirements
{accessibility_text}
{custom_eval}

## {content_type.upper()} TO EVALUATE:
---
{content}
---

## Required Output Format
Respond ONLY with valid JSON (no markdown, no code fences):
{{
  "engagement_score": <1-10>,
  "tone_match_score": <1-10>,
  "accessibility_score": <1-10>,
  "overall_score": <1-10>,
  "feedback": "<2-4 sentences of constructive feedback from the persona's perspective>",
  "deal_breaker_flags": ["<list any deal breakers detected, empty array if none>"]
}}"""

    def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API for validation."""
        if not self._api_key:
            raise RuntimeError("GEMINI_API_KEY not set. Cannot perform audience validation.")

        import requests
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{VALIDATION_MODEL}:generateContent?key={self._api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 4096,
                "responseMimeType": "application/json",
            },
        }
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def _parse_response(self, response: str, profile: AudienceProfile, app_name: str) -> ValidationResult:
        """Parse Gemini response into ValidationResult."""
        try:
            # Clean potential markdown fences
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback: return error result
            return ValidationResult(
                profile_id=profile.id,
                profile_name=profile.name,
                engagement_score=0,
                tone_match_score=0,
                accessibility_score=0,
                overall_score=0,
                feedback=f"Failed to parse AI response: {response[:200]}",
                app_name=app_name,
            )

        return ValidationResult(
            profile_id=profile.id,
            profile_name=profile.name,
            engagement_score=float(data.get("engagement_score", 0)),
            tone_match_score=float(data.get("tone_match_score", 0)),
            accessibility_score=float(data.get("accessibility_score", 0)),
            overall_score=float(data.get("overall_score", 0)),
            feedback=data.get("feedback", "No feedback provided."),
            deal_breaker_flags=data.get("deal_breaker_flags", []),
            app_name=app_name,
        )
