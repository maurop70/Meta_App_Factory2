import os
import sys
import subprocess
import json
import argparse

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRIDGE_PATH = os.path.join(BASE_DIR, "bridge.py")
FACTORY_PATH = os.path.join(BASE_DIR, "factory.py")

class MetaSupervisor:
    def __init__(self):
        pass

    def supervise(self, prompt: str):
        print(f"--- Supervisor: Analyzing Request ---", flush=True)

        user_satisfied = False
        current_prompt = prompt
        app_built = False
        decision = None

        while True:
            # 1. Consult Gemini via Bridge to determine blueprint and name
            context = f"""
            SYSTEM ROLE: You are the Meta_App_Factory ARCHITECT.
            IMPORTANT: Do NOT implement the request. Do NOT write code. Do NOT provide markdown.
            
            YOUR ONLY TASK: Map the user's request to one of the following 3 Blueprints.
            
            Blueprints:
            1. multi_agent_core: For HEAVY requests involving complex planning, multiple personas (CEO, CMO, etc.), and file/Drive updates. (USE THIS FOR THE CURRENT REQUEST).
            2. file_factory: For simple file/folder manipulation tasks.
            3. gemini_reasoner: For pure conversation or reasoning tasks.
            
            Current Mode: {'Evolution' if app_built else 'Conceptual'}
            
            CRITICAL RULES:
            - Output ONLY a JSON object. No explanation before or after.
            - Wrap JSON between delimiters: START_JSON_BLOCK and END_JSON_BLOCK.
            - Map complex requirements (like the one provided) to 'multi_agent_core'.
            
            JSON Schema:
            {{
              "options": [
                {{
                  "score": 10,
                  "app_name": "SeniorBusinessStrategist",
                  "blueprint": "multi_agent_core",
                  "explanation": "Handles complex personas, RAG vector memory, and Google Workspace integration.",
                  "system_prompt": "Mandatory logic instructions go here."
                }}
              ]
            }}
            """
            
            try:
                # Shield the user prompt to prevent 'instruction leakage'
                shielded_prompt = f"USER DATA FOR CATEGORIZATION:\n```\n{current_prompt}\n```\n\nMANDATORY: OUTPUT JSON OPTIONS ONLY."
                
                print("--- Supervisor: Brain is thinking... (Please wait) ---", flush=True)
                cmd = [
                    sys.executable, BRIDGE_PATH,
                    "--prompt", shielded_prompt,
                    "--context", context
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
                
                # Relay Sentry alerts from stderr to the Factory UI
                if result.stderr:
                    print(result.stderr.strip(), flush=True)

                raw_response = result.stdout.strip()

                json_str = ""
                if "START_JSON_BLOCK" in raw_response and "END_JSON_BLOCK" in raw_response:
                    json_str = raw_response.split("START_JSON_BLOCK")[1].split("END_JSON_BLOCK")[0].strip()
                elif "{" in raw_response and "}" in raw_response:
                    start = raw_response.find("{")
                    end = raw_response.rfind("}") + 1
                    json_str = raw_response[start:end]
                
                options = []
                try:
                    if json_str:
                        raw_data = json.loads(json_str)
                        # Standard list format
                        options = raw_data.get("options", [])
                        
                        # Fallback: AI returned a single object (dict) describing the app
                        if not options and isinstance(raw_data, dict):
                            if raw_data.get("app_name") or raw_data.get("blueprint"):
                                print("--- Supervisor: Auto-Wrapping Single Option Response ---", flush=True)
                                options = [raw_data]
                except Exception as e:
                    print(f"--- ERROR: JSON Parsing failed: {e} ---", flush=True)
                    pass

                if not options and len(current_prompt) > 400:
                    print("--- Supervisor: Complexity Guard engaged for High-Impact App ---", flush=True)
                    options = [{
                        "score": 10,
                        "app_name": "Elite_Business_Strategist",
                        "blueprint": "multi_agent_core",
                        "explanation": "Automatic high-level architecture mapping for your enterprise request.",
                        "system_prompt": current_prompt
                    }]
                
                if not options:
                    print("--- ERROR: Internal Brain Failure (No options found) ---", flush=True)
                    if raw_response: print(f"Raw Brain Feedback: {raw_response[:200]}...", flush=True)
                    return

                print(f"--- Supervisor: {'Evolution' if app_built else 'Conceptual'} Options ---", flush=True)
                for i, opt in enumerate(options):
                    print(f"OPTION {i+1} [Score: {opt.get('score', 0)}/10]", flush=True)
                    print(f"- Name: {opt.get('app_name')}", flush=True)
                    print(f"- Blueprint: {opt.get('blueprint')}", flush=True)
                    print(f"- Rationale: {opt.get('explanation')}", flush=True)
                    print("", flush=True)
                
                if app_built:
                    print("--- EVOLUTION MODE: Enter prompt to refine current app, or 'done' ---")
                else:
                    print("--- SELECTION MODE: Type option number (1, 2) to build, or feedback to refine ---")
                
                print(f"WAITING_FOR_USER_INPUT", flush=True) # Signal to GUI

                # Wait for user input
                user_msg = sys.stdin.readline().strip()
                
                if user_msg.lower() == 'done':
                    print("--- Supervisor: Job Complete. Enjoy your new App! ---")
                    break

                # Handle numeric selection
                if user_msg.isdigit():
                    idx = int(user_msg) - 1
                    if 0 <= idx < len(options):
                        decision = options[idx]
                        
                        # Standardize blueprint ID
                        bp = str(decision["blueprint"]).lower()
                        if "multi" in bp: decision["blueprint"] = "multi_agent_core"
                        elif "file" in bp: decision["blueprint"] = "file_factory"
                        else: decision["blueprint"] = "gemini_reasoner"

                        # Build/Update it!
                        print(f"--- Supervisor: Implementing OPTION {idx+1} ---")
                        try:
                            factory_cmd = [
                                sys.executable, FACTORY_PATH,
                                "--name", decision['app_name'],
                                "--blueprint", decision['blueprint'],
                                "--desc", decision.get('explanation', '')
                            ]
                            if decision.get("system_prompt"):
                                factory_cmd.extend(["--system_prompt", decision["system_prompt"]])
                                
                            subprocess.run(factory_cmd, check=True)
                            app_built = True
                            print(f"--- Supervisor: Implementation Success! (Evolution Loop Active) ---")
                            current_prompt = f"App '{decision['app_name']}' is live. User wants to improve it further. "
                        except Exception as build_err:
                            print(f"--- ERROR DURING CREATION: {build_err} ---")
                        continue
                
                # Treat everything else as feedback/refinement
                print(f"--- Supervisor: Processing Feedback ---")
                current_prompt = f"Previous context: {current_prompt}\nUser Feedback: {user_msg}"

            except Exception as e:
                print(f"--- CRITICAL SUPERVISOR ERROR: {e} ---")
                return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Meta App Factory Supervisor")
    parser.add_argument("prompt", help="Natural language request for a new app")
    
    args = parser.parse_args()
    
    supervisor = MetaSupervisor()
    supervisor.supervise(args.prompt)
