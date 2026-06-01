import sys
import requests

def test_workspace_persistence_proxy_traversal():
    print("=== IGNETING PROXY-ENFORCED E2E WORKSPACE FUZZER (PORT 5173) ===")
    
    # ── Proxy Boundary Routing ──
    # Target exclusively the Vite Proxy Port 5173 to verify rewrite logic
    base_url = "http://127.0.0.1:5173/api/projects/"
    
    payload = {
        "project_name": "Project Heinlein Foods",
        "financial_matrix": {
            "fixed_costs": 600000,
            "margin_percent": 50,
            "revenue_projections": [1200000, 1500000, 1800000]
        },
        "operational_context": {
            "location": "Sector 4-A",
            "duration_months": 24,
            "team_size": 12
        }
    }
    
    # 1. POST /api/projects/ - Proxy Traversal Write
    print(f"1. Sending POST request to {base_url}...")
    try:
        post_resp = requests.post(base_url, json=payload, timeout=10.0)
    except Exception as exc:
        print(f"[FATAL NETWORK FRACTURE] Failed to connect to Vite Proxy: {exc}")
        sys.exit(1)
        
    print(f"   - Response Status: {post_resp.status_code}")
    print(f"   - Response Body: {post_resp.text}")
    assert post_resp.status_code == 200, f"POST failed: status code is {post_resp.status_code}, expected 200"
    
    post_json = post_resp.json()
    assert post_json.get("status") == "success", "POST response 'status' is not 'success'"
    project_id = post_json.get("id")
    assert project_id is not None, "POST response did not return a valid project ID"
    print(f"[PASSED] Workspace committed. ID: {project_id}")
    
    # 2. GET /api/projects/?limit=10&offset=0 - Query-Safe Proxy Traversal Read
    get_url = f"{base_url}?limit=10&offset=0"
    print(f"\n2. Sending GET request to {get_url}...")
    get_resp = requests.get(get_url, timeout=10.0)
    print(f"   - Response Status: {get_resp.status_code}")
    assert get_resp.status_code == 200, f"GET failed: status code is {get_resp.status_code}, expected 200"
    
    get_json = get_resp.json()
    
    # ── UNIFIED I/O SERIALIZATION ENVELOPE MATHEMATICAL ASSERTIONS ──
    print("   - Asserting UNIFIED I/O SERIALIZATION ENVELOPE structure...")
    assert "items" in get_json, "Serialization Envelope FAILED: 'items' is missing!"
    assert "total" in get_json, "Serialization Envelope FAILED: 'total' is missing!"
    assert "limit" in get_json, "Serialization Envelope FAILED: 'limit' is missing!"
    assert "offset" in get_json, "Serialization Envelope FAILED: 'offset' is missing!"
    
    assert isinstance(get_json["items"], list), "Type FAILED: 'items' is not a list!"
    assert isinstance(get_json["total"], int), "Type FAILED: 'total' is not an integer!"
    assert isinstance(get_json["limit"], int), "Type FAILED: 'limit' is not an integer!"
    assert isinstance(get_json["offset"], int), "Type FAILED: 'offset' is not an integer!"
    print("[PASSED] Envelope integrity verified.")
    
    # Verify injected project presence
    matched_item = None
    for item in get_json["items"]:
        if item["project_name"] == "Project Heinlein Foods":
            matched_item = item
            break
            
    assert matched_item is not None, "Data Verification FAILED: 'Project Heinlein Foods' was not found in the collection!"
    assert matched_item["financial_matrix"]["fixed_costs"] == 600000, f"Data Verification FAILED: fixed_costs is {matched_item['financial_matrix']['fixed_costs']}, expected 600000"
    print("[PASSED] 'Project Heinlein Foods' matching item verified in collection.")
    
    # 3. PATCH /api/projects/{project_id}/ - Selective Context Mutation
    patch_url = f"{base_url}{project_id}/"
    print(f"\n3. Sending PATCH request to {patch_url}...")
    patch_payload = {
        "financial_matrix": {
            "fixed_costs": 650000,
            "margin_percent": 50
        }
    }
    patch_resp = requests.patch(patch_url, json=patch_payload, timeout=10.0)
    print(f"   - Response Status: {patch_resp.status_code}")
    print(f"   - Response Body: {patch_resp.text}")
    assert patch_resp.status_code == 200, f"PATCH failed: status code is {patch_resp.status_code}, expected 200"
    
    patch_json = patch_resp.json()
    assert patch_json.get("status") == "success", "PATCH response 'status' is not 'success'"
    assert patch_json.get("id") == project_id, f"PATCH response ID mismatch: expected {project_id}, got {patch_json.get('id')}"
    print("[PASSED] Financial matrix successfully updated.")
    
    # 4. Re-Verify GET with query parameters for the mutation
    print(f"\n4. Sending GET request again to verify the mutation...")
    re_get_resp = requests.get(get_url, timeout=10.0)
    re_get_json = re_get_resp.json()
    
    re_matched_item = None
    for item in re_get_json["items"]:
        if item["id"] == project_id:
            re_matched_item = item
            break
            
    assert re_matched_item is not None, "Re-verification FAILED: Updated project not found in collection!"
    assert re_matched_item["financial_matrix"]["fixed_costs"] == 650000, f"Re-verification FAILED: fixed_costs is {re_matched_item['financial_matrix']['fixed_costs']}, expected 650000"
    print("[PASSED] Mutation verified on the persistent disk.")
    
    print("\n=== E2E FUZZER TRAVERSAL COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    try:
        test_workspace_persistence_proxy_traversal()
        sys.exit(0)
    except AssertionError as ae:
        print(f"\n[ASSERTION FRACTURE] E2E verification failed: {ae}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FATAL FRACTURE] E2E verification failed with unexpected exception: {e}")
        sys.exit(1)
