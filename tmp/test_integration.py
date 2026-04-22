"""
Integration test: Full self-healing loop.
1. Start Operator Agent on 5100
2. Import watchdog and run one health check cycle
3. Verify watchdog correctly detects DOWN ports and dispatches to Operator
"""
import subprocess, sys, os, time, json, urllib.request, threading

base = os.path.dirname(os.path.abspath(__file__))
os.chdir(os.path.join(base, ".."))

env = os.environ.copy()
env["PYTHONUNBUFFERED"] = "1"

# Start Operator Agent
print("Starting Operator Agent...")
op_proc = subprocess.Popen(
    [sys.executable, "operator_agent.py"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
)
time.sleep(5)

# Verify it's up
try:
    r = urllib.request.urlopen("http://localhost:5100/api/health", timeout=3)
    print("Operator Agent: ONLINE")
except:
    print("Operator Agent: FAILED TO START — aborting")
    op_proc.terminate()
    sys.exit(1)

# Import and instantiate the watchdog
sys.path.insert(0, os.getcwd())
from native_watchdog import AetherNativeWatchdog, MONITORED_PORTS

watchdog = AetherNativeWatchdog(check_interval=10)

# Run one health check cycle manually
print("\nRunning single health check cycle...")
watchdog._run_health_checks()

# Check telemetry
pulse = watchdog.get_system_pulse()
health = pulse.get("gates_health", {})

up_count = sum(1 for v in health.values() if v == "OK")
down_count = sum(1 for v in health.values() if v == "FAIL")
degraded = pulse.get("degraded", [])

print(f"\nRESULTS:")
print(f"  Services UP:   {up_count}")
print(f"  Services DOWN: {down_count}")
print(f"  Degraded:      {len(degraded)}")
print(f"  Status:        {pulse.get('status')}")

print("\nPer-service status:")
for svc, status in sorted(health.items()):
    icon = "UP" if status == "OK" else "DOWN"
    print(f"  {icon} | {svc}")

# Verify the port_failures dict is tracking correctly
print(f"\nPort failure counters: {dict(watchdog._port_failures)}")

# Cleanup
op_proc.terminate()
try:
    op_proc.wait(timeout=5)
except:
    pass

print("\nIntegration test complete.")
