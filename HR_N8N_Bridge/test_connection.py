import requests
import config

def test_connection():
    url = f"{config.N8N_BASE_URL}/api/v1/active-workflows" # Using a safe endpoint to check auth
    # Note: /active-workflows might not exist, checking /workflows instead with limit
    url = f"{config.N8N_BASE_URL}/api/v1/workflows?limit=1"
    
    print(f"Testing connection to: {url}")
    
    try:
        response = requests.get(url, headers=config.get_headers())
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("SUCCESS: Connection established and authenticated.")
            print(f"Response snippet: {response.text[:200]}")
        elif response.status_code == 401:
            print("FAILURE: Unauthorized. API Key may be invalid.")
        else:
            print(f"FAILURE: Unexpected status code. {response.text}")
            
    except Exception as e:
        print(f"ERROR: Could not connect. {e}")

if __name__ == "__main__":
    test_connection()
