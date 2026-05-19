import urllib.request
import json

def verify():
    url = 'http://127.0.0.1:5000/api/v3/map'
    print(f"Querying {url}...")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode('utf-8')
            data = json.loads(res_body)
            
            print("\n[SUCCESS] Loaded map API successfully.")
            print(f"Total Nodes: {len(data.get('nodes', []))}")
            print(f"Total Edges: {len(data.get('edges', []))}")
            print(f"Stats Matrix: {data.get('stats')}")
            
            # Find and verify the CIO Agent node
            nodes = data.get('nodes', [])
            cio_node = next((n for n in nodes if n['id'] == 'cio-agent'), None)
            if cio_node:
                print("\n[SUCCESS] Found CIO Agent spatial node:")
                print(json.dumps(cio_node, indent=2))
            else:
                print("\n[ERROR] CIO Agent spatial node ('cio-agent') NOT found in response.")
                
            # Find the edge for CIO Agent
            edges = data.get('edges', [])
            cio_edge = next((e for e in edges if e['target'] == 'cio-agent'), None)
            if cio_edge:
                print("\n[SUCCESS] Found CIO Agent edge connection:")
                print(json.dumps(cio_edge, indent=2))
            else:
                print("\n[ERROR] Edge connection to 'cio-agent' NOT found.")
                
            # Verify coordinates schema
            for n in nodes:
                pos = n.get('position', {})
                if 'x' not in pos or 'y' not in pos:
                    print(f"[ERROR] Node {n.get('id')} lacks valid coordinate position schema.")
                    return
                dt = n.get('data', {})
                if 'label' not in dt or 'status' not in dt:
                    print(f"[ERROR] Node {n.get('id')} lacks valid data envelope schema.")
                    return
            print("\n[SUCCESS] All nodes strictly conform to the AST Compliance Schema ({ data, position }).")
    except Exception as e:
        print(f"\n[ERROR] Request failed: {e}")

if __name__ == '__main__':
    verify()
