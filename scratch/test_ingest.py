import requests
import time
import os
import glob

url = 'http://127.0.0.1:5041/api/v1/economics/ingest_ledger'
csv_path = r'C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\CFO_Agent\test_ledger.csv'

with open(csv_path, 'rb') as f:
    resp = requests.post(url, files={'ledger_file': f})
    
print("=== PRIMARY API RESPONSE ===")
print(resp.text)
data = resp.json()
job_id = data.get('job_id')

print("\nWaiting for decoupled worker...")
time.sleep(3)

summary_file = f"/tmp/cfo_ingest/job_{job_id}_summary.json"
print("\n=== DECOUPLED WORKER SUMMARY ===")
try:
    with open(summary_file, 'r') as f:
        print(f.read())
except Exception as e:
    print("Could not read summary:", e)
    print("Contents of /tmp/cfo_ingest/:")
    for file in glob.glob("/tmp/cfo_ingest/*"):
        print(file)

os.remove(csv_path)
