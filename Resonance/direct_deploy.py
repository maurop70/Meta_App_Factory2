import os, requests, json
from dotenv import load_dotenv

load_dotenv(r"C:\Users\mpetr\My Drive\Antigravity-AI Agents\Meta_App_Factory\Resonance\.env")
N8N_URL = "https://humanresource.app.n8n.cloud/api/v1/workflows"
HEADERS = {"X-N8N-API-KEY": os.getenv("N8N_API_KEY"), "Content-Type": "application/json"}

def deploy_workflow(wf_dict):
    try:
        wf_dict.pop("active", None)
        wf_dict["settings"] = {}
        res = requests.post(N8N_URL, json=wf_dict, headers=HEADERS)
        if res.status_code == 200:
            print("Successfully deployed:", wf_dict["name"])
            data = res.json()
            if "id" in data:
                # Activate it
                requests.post(f"{N8N_URL}/{data['id']}/activate", headers=HEADERS)
                print(f" -> Activated {data['id']}")
        else:
            print("Failed to deploy:", wf_dict["name"], res.status_code, res.text)
    except Exception as e:
        print("Error deploying:", e)

from deploy_aether_workflows import build_socratic_bridge, build_aether_memory, build_aether_streak

deploy_workflow(build_socratic_bridge())
deploy_workflow(build_aether_memory())
deploy_workflow(build_aether_streak())
