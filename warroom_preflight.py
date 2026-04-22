"""
warroom_preflight.py - Readiness check for the C-Suite Agents
Pings the critical ports to ensure they are online before the UI starts.
"""
import socket
import time
import sys

# Define critical ports
PORTS_TO_CHECK = {
    5000: "Backend API (api.py)",
    5070: "CFO Agent",
    5020: "CMO Agent",
    5080: "CLO Agent"
}

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('127.0.0.1', port)) == 0

def wait_for_ports(timeout=30):
    print("===================================================")
    print("  WAR ROOM PRE-FLIGHT CHECKS")
    print("===================================================")
    start_time = time.time()
    
    pending_ports = dict(PORTS_TO_CHECK)
    
    while pending_ports and (time.time() - start_time) < timeout:
        for port in list(pending_ports.keys()):
            if is_port_open(port):
                print(f"  [OK] {pending_ports[port]} is online on port {port}.")
                del pending_ports[port]
        
        if pending_ports:
            time.sleep(2)
            
    if pending_ports:
        print("\n  [WARNING] The following services failed to start within the timeout:")
        for port, name in pending_ports.items():
            print(f"    - {name} (Port {port})")
        print("  War Room UI will launch, but some C-Suite agents may be offline.")
    else:
        print("\n  [SUCCESS] All C-Suite agents are online. Cleared for dispatch.")

if __name__ == "__main__":
    # Give the processes a brief moment to initialize before polling
    time.sleep(3)
    wait_for_ports(timeout=45)
