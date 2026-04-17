import os
import sys
import json
import logging
import requests
from datetime import datetime

# ── V3 Resilience & Context ──────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

try:
    from auto_heal import healed_post
except ImportError:
    def healed_post(url, **kwargs):
        return requests.post(url, **kwargs)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
except ImportError:
    pass

def get_secret(key, default="", **kw):
    return os.getenv(key, default)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CIO_Agent")

class CIO_Agent:
    """Technical Strategy & Capability Handshake Agent."""

    def upgrade_pitch(self, pitch):
        """Intercepts a pitch and appends the CIO Integration Blueprint."""
        logger.info(f"CIO Agent: Researching upgrade for pitch: {pitch['id']}")
        
        gap = pitch.get("capability_gap", "General Python automation")
        
        # 1. Research phase (Simulated for Phase 1, placeholder for search tool)
        # In a real turn, I would use search_web to find specific libraries.
        research_context = self.research_libraries(gap)
        
        # 2. Strategy & Security Audit Phase
        blueprint = self.generate_blueprint(pitch, research_context)
        
        # 3. Append to pitch
        pitch["cio_blueprint"] = blueprint
        pitch["status"] = "PENDING_REVIEW" # Upgrade complete, ready for Commander
        pitch["tags"].append("CIO_UPGRADED")
        
        logger.info(f"CIO Agent: Handshake complete for pitch {pitch['id']}.")
        return pitch

    def research_libraries(self, gap):
        """Identify the most stable and 100% native Python libraries for the gap."""
        # This would normally call search_web. 
        # For Phase 1, we rely on Gemini's internal knowledge in the next step.
        return f"Researching stable Python solutions for: {gap}"

    def generate_blueprint(self, pitch, research_context):
        """Generates the technical CIO Integration Blueprint."""
        api_key = get_secret("GEMINI_API_KEY")
        if not api_key:
            return {"error": "Missing GEMINI_API_KEY"}

        prompt = f"""
You are the CIO Agent of the Meta App Factory. Your role is to bridge the technical gap for a high-signal venture idea.

PITCH PROBLEM: {pitch['pitch']['problem']}
CAPABILITY GAP: {pitch.get('capability_gap')}
CONTEXT: {research_context}

YOUR TASK:
1. Identify 1-2 modern, stable, and 100% native Python libraries to solve this.
2. Provide a "CIO Integration Blueprint" covering:
   - Technical Stack (Native Python/FastAPI)
   - Core Library Recommendation
   - Stability & Security Audit (Is it well-maintained? Are there security risks?)
   - Integration Path (How we connect this to the Factory Architect)

RESPOND WITH VALID JSON ONLY.
Structure:
{{
  "recommended_libraries": ["lib1", "lib2"],
  "security_audit": "Concise security/stability verdict",
  "integration_blueprint": {{
    "architecture_summary": "How it works",
    "required_endpoints": ["/endpoint1", "/endpoint2"],
    "implementation_steps": ["Step 1", "Step 2"]
  }}
}}
"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }

        try:
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 200:
                result = resp.json()
                raw_text = result['candidates'][0]['content']['parts'][0]['text']
                return json.loads(raw_text)
        except Exception as e:
            logger.error(f"CIO Blueprint generation failed: {e}")
            return {"error": str(e)}

if __name__ == "__main__":
    # Test
    agent = CIO_Agent()
    mock_pitch = {
        "id": "test_pitch",
        "capability_gap": "Real-time PDF extraction from dynamic websites",
        "pitch": {"problem": "Users can't extract data from interactive PDFs on government sites."}
    }
    result = agent.upgrade_pitch(mock_pitch)
    print(json.dumps(result, indent=2))
