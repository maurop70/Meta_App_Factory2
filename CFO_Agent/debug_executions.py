import requests, json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv(os.path.join('..', '.env'))

H = {'X-N8N-API-KEY': os.getenv('N8N_API_KEY',''), 'Content-Type': 'application/json'}
r = requests.get('https://humanresource.app.n8n.cloud/api/v1/executions?workflowId=beFBb85gonIaMzAo&limit=5&includeData=true', headers=H, timeout=15)
execs = r.json().get('data', [])

for e in execs[:3]:
    eid = e['id']
    status = e.get('status', '?')
    print(f"\n{'='*50}")
    print(f"Execution {eid}: {status}")
    
    rd = e.get('data', {}).get('resultData', {})
    
    # Check lastNodeExecuted
    last_node = rd.get('lastNodeExecuted', '?')
    print(f"Last node: {last_node}")
    
    # Check error
    error = rd.get('error', {})
    if error:
        print(f"Error: {json.dumps(error, indent=2)[:500]}")
    
    # Check run data
    run_data = rd.get('runData', {})
    for node_name, node_runs in run_data.items():
        for run in node_runs:
            st = run.get('executionStatus', '?')
            err = run.get('error', '')
            if err:
                print(f"  {node_name}: {st} ERROR: {json.dumps(err, default=str)[:200]}")
            else:
                data = run.get('data', {}).get('main', [[]])
                items = data[0] if data and data[0] else []
                if items:
                    first_json = items[0].get('json', {})
                    keys = list(first_json.keys())[:5]
                    print(f"  {node_name}: {st} keys={keys}")
                else:
                    print(f"  {node_name}: {st} (no items)")
