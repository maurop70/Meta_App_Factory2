import requests, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

checks = [
    ("CFO Fragility Engine", "http://localhost:5041/api/health"),
    ("Phantom QA Elite", "http://localhost:5030/api/health"),
]

for name, url in checks:
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        print(f"  {name}: ONLINE (port {data.get('port', '?')}, agent={data.get('agent', '?')})")
    except Exception as e:
        print(f"  {name}: OFFLINE ({e})")
