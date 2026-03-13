# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

from auto_heal import healed_post, auto_heal, diagnose

def _v3_preflight():
    """V3: Ping Resonance_Watchdog_V3 before execution."""
    if not _V3_AVAILABLE:
        return True
    try:
        import json as _j
        _cfg_path = _os.path.join(_FACTORY_DIR, "resilience_config.json")
        if not _os.path.exists(_cfg_path):
            return True
        with open(_cfg_path) as _f:
            _cfg = _j.load(_f)
        _url = _cfg.get("cloud_health", {}).get("watchdog_url", "")
        if not _url:
            return True
        import requests as _rq
        _r = _rq.get(_url, timeout=5)
        return _r.status_code == 200
    except Exception:
        return False



import json
import bridge

class Atomizer:
    def __init__(self, project_name="General_Consulting"):
        self.project_name = project_name

    def evaluate(self, prompt):
        """
        Analyzes the prompt complexity using the N8N bridge.
        Returns a list of chunks if complex, or None/Empty list if simple.
        """
        analysis_prompt = (
            f"SYSTEM OVERRIDE: YOU ARE NOW THE ATOMIZER. \n"
            f"TASK: Deconstruct the following request into a series of IMPERATIVE EXECUTION COMMANDS. \n"
            f"CRITERIA: If the request has >3 distinct deliverables, break it down. \n"
            f"FORMAT: Return ONLY a raw JSON list of strings. \n"
            f"RULES: \n"
            f"1. Start every step with a VERB (EXECUTE, GENERATE, CALCULATE, RESEARCH). \n"
            f"2. Make each step self-contained and actionable. \n"
            f"3. NO CONVERSATIONAL TEXT. \n"
            f"Example: [\"EXECUTE comprehensive market research on...\", \"GENERATE detailed financial model for...\"] \n"
            f"If simple, return []. \n"
            f"Request: {prompt}"
        )

        retry_count = 3
        for attempt in range(retry_count):
            try:
                # Use Dedicated Atomizer Capability if available
                atomizer_url = bridge.AGENT_REGISTRY.get("ATOMIZER")
                if atomizer_url:
                    print(f"DEBUG ATOMIZER: Routing to Dedicated Agent: {atomizer_url} (Attempt {attempt+1})")
                    # Wrap the request to catch 502/504 errors before JSON decoding
                    _v3_status = healed_post(atomizer_url, {"prompt": prompt})

                    r = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
                    
                    if r.status_code != 200:
                         print(f"DEBUG ATOMIZER ERROR: Status {r.status_code} - {r.text[:100]}")
                         if attempt < retry_count - 1:
                             import time; time.sleep(2)
                             continue
                         return []

                    try:
                        response_data = r.json()
                    except json.JSONDecodeError:
                        print(f"DEBUG ATOMIZER JSON ERROR: Could not decode response.")
                        print(f"RAW MSG: {r.text}")
                        if attempt < retry_count - 1: continue
                        return []

                    # The response from N8N might be {"text": "..."} or {"output": "..."}
                    response = response_data.get("text") or response_data.get("output") or response_data
                else:
                    # Fallback to Council (Legacy)
                    print("DEBUG ATOMIZER: Routing to Council (Fallback)")
                    response = bridge.call_app({
                        "prompt": analysis_prompt,
                        "project_name": self.project_name,
                        "context": "ATOMIZER_ANALYSIS",
                        "clean_slate": True
                    })

                print(f"DEBUG ATOMIZER RAW RESPONSE: {str(response)[:100]}...") 
                
                # Attempt to parse JSON from the response
                # The response might be wrapped in text
                if isinstance(response, str):
                    start = response.find('[')
                    end = response.rfind(']')
                    if start != -1 and end != -1:
                        json_str = response[start:end+1]
                        try:
                            chunks = json.loads(json_str)
                            print(f"DEBUG ATOMIZER PARSED: {len(chunks)} chunks")
                            return chunks
                        except json.JSONDecodeError as je:
                            print(f"DEBUG ATOMIZER INTERNAL JSON ERROR: {je}")
                    else:
                        print("DEBUG ATOMIZER: No JSON array found in response")
                elif isinstance(response, list):
                    print(f"DEBUG ATOMIZER: Received List directly: {len(response)} items")
                    return response
                
                # If we got here with a valid response but no chunks, break loop (it's not a connection error)
                break

            except Exception as e:
                print(f"Atomizer Evaluation Error (Attempt {attempt+1}): {e}")
                if attempt < retry_count - 1:
                     import time; time.sleep(2)
                else:
                    return []
        
        return []

    def stitch(self, results):
        """
        Synthesizes multiple results into one report.
        For now, it just concatenates them with headers.
        """
        final_report = "# ATOMIZER SYNTHESIS REPORT\n\n"
        for i, res in enumerate(results):
            final_report += f"## Part {i+1}\n{res}\n\n"
        return final_report

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
