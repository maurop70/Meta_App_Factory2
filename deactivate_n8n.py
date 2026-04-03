import urllib.request
import urllib.error
import urllib.parse
import json

base_url = "https://humanresource.app.n8n.cloud"
api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1ZGM3MWNiMy0yZWRkLTRmMWItODQwMS00MGQ4M2FkOTBmMWIiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY4NTE1NDM5fQ.RibOEnSDVDwlwVJGuac_BTfmZdnpx7SL0-QhxUn4xns"

headers = {"X-N8N-API-KEY": api_key, "accept": "application/json", "content-type": "application/json"}

for wid in ["wunoJBl6p6hfiHOX", "XHYpA1Es2YL9ugjK"]:
    url = f"{base_url}/api/v1/workflows/{wid}/deactivate"
    req = urllib.request.Request(url, headers=headers, method="POST", data=json.dumps({}).encode('utf-8'))
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Deactivated {wid}: {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"Failed to deactivate {wid}: {e.code} - {e.read().decode()}")
    except Exception as e:
        print(f"Error {wid}: {e}")
