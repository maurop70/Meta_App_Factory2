import os

# N8N Configuration
N8N_BASE_URL = "https://humanresource.app.n8n.cloud"
# API Key retrieved from Alpha_Architect/deploy_n8n.py
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1ZGM3MWNiMy0yZWRkLTRmMWItODQwMS00MGQ4M2FkOTBmMWIiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY4NTE1NDM5fQ.RibOEnSDVDwlwVJGuac_BTfmZdnpx7SL0-QhxUn4xns"

def get_headers():
    return {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Content-Type": "application/json"
    }
