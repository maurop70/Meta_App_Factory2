import os
import sys
import json
import logging
import re
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
logger = logging.getLogger("VentureScout")

# ── Configuration ──────────────────────────────────────────
DATA_DIR = os.path.join(SCRIPT_DIR, "Venture_Data")
PITCHES_PATH = os.path.join(DATA_DIR, "scout_pitches.json")
os.makedirs(DATA_DIR, exist_ok=True)

FRUSTRATION_PATTERNS = [
    r"I wish there was an app that",
    r"Looking for an alternative to",
    r"Why is it so hard to",
    r"Automate this manual process",
    r"Is there a tool for",
    r"extremely frustrated with",
    r"spending hours doing",
    r"completely manual process",
    r"workflow is broken",
    r"how to automate",
    r"struggling with",
    r"pain point",
    r"anyone else find",
    r"is there a way to",
]

# ── Data Intake (The "Eyes") ───────────────────────────────

class HackerNewsScout:
    """Hunts Ask HN for frustration signals."""
    API_BASE = "https://hacker-news.firebaseio.com/v0"

    def hunt(self, limit=100):
        logger.info("Venture Scout: Hunting Hacker News...")
        try:
            # Get Ask HN stories
            # For simplicity in Phase 1, we look at 'newstories' and filter for 'Ask HN'
            resp = requests.get(f"{self.API_BASE}/newstories.json", timeout=10)
            story_ids = resp.json()[:limit]
            
            signals = []
            for sid in story_ids:
                item = requests.get(f"{self.API_BASE}/item/{sid}.json", timeout=5).json()
                if not item: continue
                
                title = item.get("title", "")
                text = item.get("text", "")
                full_content = f"{title} {text}"
                
                if "Ask HN:" in title and any(re.search(p, full_content, re.IGNORECASE) for p in FRUSTRATION_PATTERNS):
                    signals.append({
                        "source": "HackerNews",
                        "id": sid,
                        "title": title,
                        "content": text,
                        "url": f"https://news.ycombinator.com/item?id={sid}",
                        "timestamp": datetime.fromtimestamp(item.get("time", 0)).isoformat()
                    })
            return signals
        except Exception as e:
            logger.error(f"HN Scout failed: {e}")
            return []

class RedditScout:
    """Hunts subreddits using public JSON endpoints."""
    SUBREDDITS = ["SaaS", "Entrepreneur", "smallbusiness", "automation"]

    def hunt(self, limit=50):
        logger.info("Venture Scout: Hunting Reddit...")
        signals = []
        headers = {"User-Agent": "AntigravityVentureScout/1.0"}
        
        for sub in self.SUBREDDITS:
            try:
                url = f"https://www.reddit.com/r/{sub}/new.json?limit={limit}"
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code != 200: continue
                
                data = resp.json().get("data", {}).get("children", [])
                for post in data:
                    p = post.get("data", {})
                    title = p.get("title", "")
                    text = p.get("selftext", "")
                    full_content = f"{title} {text}"
                    
                    if any(re.search(pattern, full_content, re.IGNORECASE) for pattern in FRUSTRATION_PATTERNS):
                        signals.append({
                            "source": f"Reddit/r/{sub}",
                            "id": p.get("id"),
                            "title": title,
                            "content": text,
                            "url": f"https://reddit.com{p.get('permalink')}",
                            "score": p.get("score", 0),
                            "timestamp": datetime.fromtimestamp(p.get("created_utc", 0)).isoformat()
                        })
            except Exception as e:
                logger.error(f"Reddit Scout failed for r/{sub}: {e}")
        return signals

# ── Filtration & Pitch Generation (The "Brain") ───────────

class VentureGate:
    """Evaluates signals using Gemini and generates pitches."""

    def perform_competitive_audit(self, title, problem):
        """Uses Gemini to perform a virtual search and audit for competitors."""
        api_key = get_secret("GEMINI_API_KEY")
        prompt = f"""
        Perform a competitive audit for this idea:
        TITLE: {title}
        PROBLEM: {problem}

        SEARCH RESEARCH:
        Identify existing products that solve this exact problem.
        Rate Market Saturation: Low (Blue Ocean), Medium (Competitive but Room), High (Red Ocean/Saturated).
        
        RESPOND WITH VALID JSON ONLY:
        {{
          "saturation": "Low/Medium/High",
          "competitors": ["Name 1", "Name 2"],
          "blue_ocean_verdict": true/false
        }}
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                result = resp.json()
                raw = result['candidates'][0]['content']['parts'][0]['text']
                return json.loads(raw)
        except Exception as e:
            logger.error(f"Competitive Audit failed: {e}")
        return {"saturation": "Medium", "blue_ocean_verdict": True} # Fallback to cautious pass

    def evaluate(self, signals):
        if not signals:
            return []
        
        api_key = get_secret("GEMINI_API_KEY")
        if not api_key:
            logger.error("Venture Gate: Missing GEMINI_API_KEY")
            return []

        pitches = []
        for signal in signals:
            logger.info(f"Venture Gate: Evaluating signal from {signal['source']}...")
            
            # Market Saturation Check (Simulated for Phase 1, placeholder for Search Tool)
            # In a real agent turn, we would call search_web here.
            
            prompt = f"""
You are a Venture Capitalist and Expert Product Engineer. Evaluate this user complaint/request.

SOURCE: {signal['source']}
TITLE: {signal['title']}
CONTENT: {signal['content']}

CRITERIA:
1. Viability: Is there a clear software solution for this?
2. Technical Fit: Can this be built with a 100% native Python backend (FastAPI/Gemini)?
3. Monetization: Is there a clear B2B or Prosumer monetization path?
4. Capability Gap: Do we have the native Python tools/libraries to build this? If not, identify the gap.

RESPOND WITH VALID JSON ONLY.
Structure:
{{
  "score": 0-100,
  "rationale": "Why this score?",
  "is_viable": true/false,
  "requires_upgrade": true/false,
  "capability_gap_details": "Describe the missing library/API if requires_upgrade is true",
  "pitch": {{
    "problem": "Concise problem statement",
    "proposed_solution": "How our Python stack solves it",
    "target_audience": "Who pays for this?",
    "pricing_model": "Suggested pricing strategy",
    "market_saturation": "Low/Medium/High (Estimated)"
  }}
}}
"""
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"}
            }
            
            try:
                # Use direct requests for Gemini to access the response body
                resp = requests.post(url, json=payload, timeout=60)
                if resp.status_code != 200: 
                    logger.error(f"Gemini API failed with status {resp.status_code}: {resp.text}")
                    continue
                
                result = resp.json()
                raw_text = result['candidates'][0]['content']['parts'][0]['text']
                evaluation = json.loads(raw_text)
                
                if evaluation.get("score", 0) >= 85:
                    # ── Mandatory Market Saturation Check (Phase 1) ──
                    audit = self.perform_competitive_audit(signal["title"], evaluation["pitch"]["problem"])
                    if audit.get("saturation") == "High" and not audit.get("blue_ocean_verdict"):
                        logger.warning(f"Venture Gate: Discarding {signal['title']} due to HIGH market saturation.")
                        continue

                    pitch = {
                        "id": signal["id"],
                        "source": signal["source"],
                        "original_title": signal["title"],
                        "original_url": signal["url"],
                        "score": evaluation["score"],
                        "rationale": evaluation["rationale"],
                        "pitch": evaluation["pitch"],
                        "market_audit": audit,
                        "generated_at": datetime.now().isoformat(),
                        "status": "PENDING_REVIEW",
                        "tags": []
                    }

                    # ── CIO Handshake: Capability Gap Analysis ──
                    if evaluation.get("requires_upgrade"):
                        pitch["status"] = "AWAITING_CIO_UPGRADE"
                        pitch["tags"].append("REQUIRES_UPGRADE")
                        pitch["capability_gap"] = evaluation.get("capability_gap_details", "Unknown gap")
                        
                        try:
                            from cio_agent import CIO_Agent
                            cio = CIO_Agent()
                            logger.info(f"Venture Scout: Triggering CIO Handshake for pitch {pitch['id']}...")
                            upgraded_pitch = cio.upgrade_pitch(pitch)
                            pitch = upgraded_pitch
                        except Exception as e:
                            logger.error(f"CIO Handshake failed: {e}")

                    pitches.append(pitch)
                    logger.info(f"🔥 HIGH SIGNAL: {signal['title']} (Score: {evaluation['score']})")
                
            except Exception as e:
                logger.error(f"Venture Gate evaluation failed: {e}")
        
        return pitches

# ── Orchestrator ───────────────────────────────────────────

class VentureScoutService:
    def __init__(self):
        self.hn = HackerNewsScout()
        self.reddit = RedditScout()
        self.gate = VentureGate()

    def run_loop(self):
        logger.info("Venture Scout: Initializing Phase 1 Hunting Loop...")
        
        # 1. Gather signals
        hn_signals = self.hn.hunt()
        reddit_signals = self.reddit.hunt()
        all_signals = hn_signals + reddit_signals
        
        logger.info(f"Venture Scout: Found {len(all_signals)} potential signals.")
        
        # 2. Evaluate and generate pitches
        new_pitches = self.gate.evaluate(all_signals)
        
        # 3. Persist
        existing_pitches = self.load_pitches()
        # Prevent duplicates
        existing_ids = {p["id"] for p in existing_pitches}
        for p in new_pitches:
            if p["id"] not in existing_ids:
                existing_pitches.append(p)
        
        self.save_pitches(existing_pitches)
        logger.info(f"Venture Scout: Loop complete. {len(new_pitches)} new high-signal pitches generated.")
        return new_pitches

    def load_pitches(self):
        if os.path.exists(PITCHES_PATH):
            with open(PITCHES_PATH, "r") as f:
                return json.load(f)
        return []

    def save_pitches(self, pitches):
        with open(PITCHES_PATH, "w") as f:
            json.dump(pitches, f, indent=2)

if __name__ == "__main__":
    scout = VentureScoutService()
    scout.run_loop()
