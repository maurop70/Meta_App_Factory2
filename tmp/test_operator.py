"""Quick runtime test for Operator Agent endpoints."""
import subprocess, sys, os, time, json, urllib.request

base = os.path.dirname(os.path.abspath(__file__))
os.chdir(base)

env = os.environ.copy()
env["PYTHONUNBUFFERED"] = "1"

print("Starting Operator Agent on port 5100...")
p = subprocess.Popen(
    [sys.executable, "operator_agent.py"],
    cwd=base, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
)
time.sleep(6)

# Test 1: Health check
try:
    r = urllib.request.urlopen("http://localhost:5100/api/health", timeout=3)
    data = json.loads(r.read().decode())
    print("TEST 1 HEALTH:", "PASS" if data.get("status") == "up" else "FAIL", data)
except Exception as e:
    print("TEST 1 HEALTH: FAIL -", e)

# Test 2: Manifest endpoint
try:
    r = urllib.request.urlopen("http://localhost:5100/api/operator/manifest", timeout=3)
    data = json.loads(r.read().decode())
    count = len(data.get("manifest", []))
    print(f"TEST 2 MANIFEST: PASS ({count} services)")
    for m in data["manifest"]:
        flag = " [CRITICAL]" if m.get("critical") else (" [SELF]" if m.get("self") else "")
        print(f"  {m['port']}: {m['name']}{flag}")
except Exception as e:
    print("TEST 2 MANIFEST: FAIL -", e)

# Test 3: Restart endpoint rejects unauthorized
try:
    req = urllib.request.Request(
        "http://localhost:5100/api/operator/restart-service",
        data=json.dumps({"port": 5010, "reason": "test"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=3)
    print("TEST 3 AUTH: FAIL - should have rejected")
except urllib.error.HTTPError as e:
    if e.code == 403:
        print("TEST 3 AUTH: PASS (correctly rejected unauthorized caller)")
    else:
        print(f"TEST 3 AUTH: FAIL - got {e.code} instead of 403")
except Exception as e:
    print("TEST 3 AUTH: FAIL -", e)

# Test 4: Restart endpoint accepts authorized caller
try:
    req = urllib.request.Request(
        "http://localhost:5100/api/operator/restart-service",
        data=json.dumps({"port": 5010, "reason": "test_authorized"}).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Antigravity-Agent": "AetherNativeWatchdog",
        },
    )
    r = urllib.request.urlopen(req, timeout=3)
    data = json.loads(r.read().decode())
    print("TEST 4 RESTART DISPATCH:", "PASS" if data.get("status") == "dispatched" else "FAIL", data)
except Exception as e:
    print("TEST 4 RESTART DISPATCH: FAIL -", e)

# Cleanup
p.terminate()
try:
    p.wait(timeout=5)
except:
    pass

print("\nAll tests complete.")
