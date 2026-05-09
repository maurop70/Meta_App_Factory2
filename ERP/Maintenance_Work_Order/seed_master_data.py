import requests
import sys

# Edge Cluster Routing (Nginx proxies /api/ -> FastAPI :8000/)
BASE_URL = "http://68.183.30.128/api"

# IAM Gateway uses /api/v1/auth/login with emp_id/pin fields
AUTH_URL = "http://68.183.30.128/api/v1/auth/login"
AUTH_PAYLOAD = {"emp_id": "ERP-1000", "pin": "1234"}


def authenticate() -> str:
    print("[*] Initiating IAM Gateway Authentication...")
    response = requests.post(AUTH_URL, json=AUTH_PAYLOAD)

    if response.status_code != 200:
        print(f"[!] FATAL: Authentication blocked. {response.text}")
        sys.exit(1)

    data = response.json()
    token = data.get("access_token")
    user = data.get("user", {})
    print(f"[+] Authenticated: {user.get('sub')} | Role: {user.get('role')}")
    return token


def ingest(endpoint: str, payload_list: list, headers: dict):
    print(f"[*] Hydrating Matrix: {endpoint} ({len(payload_list)} records)")
    for idx, payload in enumerate(payload_list):
        res = requests.post(f"{BASE_URL}{endpoint}", json=payload, headers=headers)
        if res.status_code != 201:
            print(f"[!] FATAL EXCEPTION at Record {idx}: HTTP {res.status_code} | {res.text}")
            print(f"    Payload: {payload}")
            sys.exit(1)
        print(f"    [{idx+1}/{len(payload_list)}] {res.json().get('detail')}")
    print(f"[+] SUCCESS: {endpoint} mathematically sealed.\n")


def execute_hydration():
    print("=" * 60)
    print("  PRODUCTION MASTER DATA HYDRATION SEQUENCE")
    print("  Target: 68.183.30.128 (DigitalOcean Edge Cluster)")
    print("=" * 60 + "\n")

    token = authenticate()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ========== LEVEL 0: Independent Entities ==========
    ingest("/locations", [
        {"id": "LOC-WH1",  "name": "Main Warehouse"},
        {"id": "LOC-FLR1", "name": "Production Floor"},
    ], headers)

    ingest("/departments", [
        {"id": "DEPT-MECH", "name": "Mechanical Maintenance"},
        {"id": "DEPT-ELEC", "name": "Electrical Systems"},
    ], headers)

    ingest("/categories", [
        {"id": "CAT-MOTORS",  "name": "Industrial Motors"},
        {"id": "CAT-SENSORS", "name": "Telemetry Sensors"},
    ], headers)

    # ========== LEVEL 1: FK -> Level 0 ==========
    ingest("/employees", [
        {"id": "ERP-1029", "name": "Marcus Kane",    "role": "TECH", "pin_code": "8492", "department_id": "DEPT-MECH"},
        {"id": "ERP-1030", "name": "Elena Rostova",  "role": "HM",   "pin_code": "1194", "department_id": "DEPT-ELEC"},
    ], headers)

    ingest("/skus", [
        {"id": "SKU-9901", "nomenclature": "3-Phase Servo Motor",      "category_id": "CAT-MOTORS",  "unit_cost": 450.00, "reorder_threshold": 5},
        {"id": "SKU-9902", "nomenclature": "Optical Proximity Sensor", "category_id": "CAT-SENSORS", "unit_cost": 125.50, "reorder_threshold": 15},
    ], headers)

    # ========== LEVEL 2: FK -> Level 0 + Level 1 ==========
    ingest("/equipment", [
        {
            "id": "EQ-ASSEMBLY-01",
            "nomenclature": "Robotic Assembly Arm A1",
            "category_id": "CAT-MOTORS",
            "department_id": "DEPT-MECH",
            "location_id": "LOC-FLR1",
            "assigned_hm_id": "ERP-1030",
            "status": "ACTIVE",
        },
    ], headers)

    print("=" * 60)
    print("  PRODUCTION EDGE FULLY HYDRATED")
    print("=" * 60)


if __name__ == "__main__":
    execute_hydration()
