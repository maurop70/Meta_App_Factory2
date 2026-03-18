import os
import json
import requests
from dotenv import load_dotenv

load_dotenv(r'c:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Meta_App_Factory\.env')
N8N_BASE_URL = os.getenv('N8N_BASE_URL', 'https://humanresource.app.n8n.cloud').rstrip('/')
N8N_API_KEY = os.getenv('N8N_API_KEY')
headers = {'X-N8N-API-KEY': N8N_API_KEY, 'Accept': 'application/json', 'Content-Type': 'application/json'}

def set_variable():
    url = "https://script.google.com/macros/s/AKfycbzhc6PNqQg6PaRCz1xC-RSbv2NmXHqS8nEtT6Kd8Gces0aAGyxzqQnuMDYLq1h4AsBY/exec"
    payload = {"key": "AETHER_DASHBOARD_WEBHOOK_URL", "value": url}
    
    # Try POST
    r = requests.post(f"{N8N_BASE_URL}/api/v1/variables", headers=headers, json=payload)
    print("POST /variables", r.status_code, r.text)

if __name__ == "__main__":
    set_variable()

# V3 MIGRATION COMPLETE
