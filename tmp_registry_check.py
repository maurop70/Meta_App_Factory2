import urllib.request, json

data = json.loads(urllib.request.urlopen("http://localhost:5000/api/registry").read())
apps = data.get("apps", [])
print(f"Apps returned by API: {len(apps)}")
active = [a for a in apps if a["status"] == "active"]
print(f"Active: {len(active)}")
for a in apps:
    print(f"  [{a['status']}] {a['name']}")
