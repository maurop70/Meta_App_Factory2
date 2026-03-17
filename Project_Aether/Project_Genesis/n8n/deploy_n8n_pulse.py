import os
import sys
import json
import logging
import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pulse.deployer")

load_dotenv(r'c:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Meta_App_Factory\.env')

N8N_BASE_URL = os.getenv('N8N_BASE_URL', 'https://humanresource.app.n8n.cloud').rstrip('/')
N8N_API_KEY = os.getenv('N8N_API_KEY')

headers = {
    'X-N8N-API-KEY': N8N_API_KEY,
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

def create_workflow(wf_json):
    payload = {
        "name": wf_json['name'],
        "nodes": wf_json['nodes'],
        "connections": wf_json['connections'],
        "settings": wf_json.get('settings', {})
    }
    r = requests.post(f"{N8N_BASE_URL}/api/v1/workflows", headers=headers, json=payload)
    if r.status_code == 200:
        logger.info("Successfully created legal-delegation-router on n8n Cloud.")
        return r.json()
    else:
        logger.error(f"Failed to create workflow: {r.status_code} {r.text}")
        return None

def main():
    r = requests.get(f"{N8N_BASE_URL}/api/v1/workflows?limit=100", headers=headers)
    workflows = r.json().get('data', [])
    pulse_id = None
    existing_router_id = None
    for w in workflows:
        if 'pulse' in w['name'].lower():
            pulse_id = w['id']
        elif 'legal-delegation-router' in w['name'].lower():
            existing_router_id = w['id']
            
    if not pulse_id:
        logger.error("Pulse ID not found. Import it first.")
        sys.exit(1)
        
    router_path = r'c:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Meta_App_Factory\Project_Aether\Project_Genesis\n8n\legal_delegation_router.json'
    with open(router_path, 'r', encoding='utf-8') as f:
        wf_data = json.load(f)
        
    nodes = wf_data.get('nodes', [])
    connections = wf_data.get('connections', {})
    
    finalize_pos = [1120, 300]
    for n in nodes:
        if 'Finalize' in n['name']:
            finalize_pos = n['position']
            break
            
    import uuid
    pulse_node = {
        "parameters": {
            "workflowId": pulse_id,
        },
        "id": str(uuid.uuid4()),
        "name": "Call Aether Pulse",
        "type": "n8n-nodes-base.executeWorkflow",
        "typeVersion": 1,
        "position": [
            finalize_pos[0] + 250,
            finalize_pos[1]
        ]
    }
    
    node_names = [n['name'] for n in nodes]
    if "Call Aether Pulse" not in node_names:
        nodes.append(pulse_node)
        
        if 'Finalize Routing' not in connections:
            connections['Finalize Routing'] = {'main': [[]]}
        connections['Finalize Routing']['main'][0].append({
            "node": "Call Aether Pulse",
            "type": "main",
            "index": 0
        })
        
    wf_data['nodes'] = nodes
    wf_data['connections'] = connections
    
    if existing_router_id:
        logger.info(f"Updating existing legal-delegation-router (ID: {existing_router_id})")
        payload = {
            "name": wf_data['name'],
            "nodes": wf_data['nodes'],
            "connections": wf_data['connections'],
            "settings": wf_data.get('settings', {})
        }
        r_upd = requests.put(f"{N8N_BASE_URL}/api/v1/workflows/{existing_router_id}", headers=headers, json=payload)
        logger.info(f"Update status: {r_upd.status_code}")
        # Activate workflow
        requests.post(f"{N8N_BASE_URL}/api/v1/workflows/{existing_router_id}/activate", headers=headers)
    else:
        logger.info("Creating new legal-delegation-router on n8n...")
        created = create_workflow(wf_data)
        if created:
            logger.info("Activating workflow")
            requests.post(f"{N8N_BASE_URL}/api/v1/workflows/{created['id']}/activate", headers=headers)

if __name__ == "__main__":
    main()
