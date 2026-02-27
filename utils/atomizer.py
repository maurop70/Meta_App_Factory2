
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
                    import requests
                    
                    # Wrap the request to catch 502/504 errors before JSON decoding
                    r = requests.post(atomizer_url, json={"prompt": prompt}, timeout=60)
                    
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
