import urllib.request, json

url = 'https://humanresource.app.n8n.cloud/api/v1/workflows'
headers = {
    'X-N8N-API-KEY': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1ZGM3MWNiMy0yZWRkLTRmMWItODQwMS00MGQ4M2FkOTBmMWIiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY4NTE1NDM5fQ.RibOEnSDVDwlwVJGuac_BTfmZdnpx7SL0-QhxUn4xns',
    'accept': 'application/json'
}

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        workflows = data.get('data', [])
        
        target_names = ["Resonance_Watchdog", "SYSTEM_Watchdog_Ping", "Specialist - CFO (V2)", "Specialist - CTO (USE)", "Phantom QA Elite", "Master Architect Elite"]
        
        for wf in workflows:
            name = wf.get('name')
            wid = wf.get('id')
            active = wf.get('active')
            
            match = False
            if 'Specialist' in name or name in target_names or 'Watchdog' in name:
                match = True
            
            if match and active:
                print(f"DEACTIVATING: {wid} - {name}")
                try:
                    update_url = f"{url}/{wid}/deactivate"
                    update_req = urllib.request.Request(update_url, data=b'', headers=headers, method='POST')
                    urllib.request.urlopen(update_req)
                    print(f" -> Success!")
                except Exception as ex:
                    print(f" -> Failed: {ex}")
            elif match and not active:
                print(f"ALREADY INACTIVE: {wid} - {name}")
                
except Exception as e:
    print(f"Error: {e}")
