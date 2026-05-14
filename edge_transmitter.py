import subprocess
import sys
import os

# === Edge Node Configuration ===
EDGE_IP = "104.248.233.220"
REMOTE_USER = "root"
REMOTE_TARGET_DIR = "/var/www/meta_app_factory"

# === Artifact Manifest ===
LOCAL_FRONTEND_DIST = "factory_ui/dist/"
LOCAL_BACKEND_FILES = ["api.py", "factory_stream.py", "socratic_challenger.py"]

def execute_subprocess(command_list: list, step_name: str):
    """
    Executes a native OS command via subprocess.Popen.
    Mathematically traps stderr and halts the pipeline on failure.
    """
    print(f"[{step_name}] Actuating: {' '.join(command_list)}")
    try:
        process = subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            print(f"\n[FATAL] {step_name} FRACTURED.")
            print(f"Exit Code: {process.returncode}")
            print(f"Error Stream:\n{stderr.strip()}")
            sys.exit(1)
            
        print(f"[{step_name}] VERIFIED.")
        if stdout.strip():
            print(f"Output:\n{stdout.strip()}")
            
    except Exception as e:
        print(f"\n[FATAL] {step_name} UNHANDLED EXCEPTION: {str(e)}")
        sys.exit(1)

def transmit_payload():
    print("=== INITIALIZING CONTINUOUS DEPLOYMENT TRANSMITTER ===")
    
    # 1. Cryptographic Transfer (SCP)
    # Push frontend matrix
    if os.path.exists(LOCAL_FRONTEND_DIST):
        scp_frontend = ["scp", "-r", LOCAL_FRONTEND_DIST, f"{REMOTE_USER}@{EDGE_IP}:{REMOTE_TARGET_DIR}/frontend/"]
        execute_subprocess(scp_frontend, "SCP_FRONTEND_DIST")
    else:
        print(f"[WARNING] Local frontend build not found at {LOCAL_FRONTEND_DIST}. Execute 'npm run build' first.")

    # Push backend monoliths
    valid_backend_files = [f for f in LOCAL_BACKEND_FILES if os.path.exists(f)]
    if valid_backend_files:
        scp_backend = ["scp"] + valid_backend_files + [f"{REMOTE_USER}@{EDGE_IP}:{REMOTE_TARGET_DIR}/backend/"]
        execute_subprocess(scp_backend, "SCP_BACKEND_CONSOLIDATED")
    else:
        print("[WARNING] No local backend artifacts found.")

    # 2. Remote Actuation (SSH)
    # Flush remote ASGI cache and reload new atomic mutations via systemd
    print("\n=== INITIATING REMOTE ACTUATION ===")
    ssh_restart_core = ["ssh", f"{REMOTE_USER}@{EDGE_IP}", "systemctl restart core-engine"]
    execute_subprocess(ssh_restart_core, "SSH_RESTART_CORE_ENGINE")
    
    ssh_restart_qa = ["ssh", f"{REMOTE_USER}@{EDGE_IP}", "systemctl restart phantom-qa"]
    execute_subprocess(ssh_restart_qa, "SSH_RESTART_PHANTOM_QA")
    
    print("\n=== EDGE TRANSMISSION PIPELINE SEALED ===")

if __name__ == "__main__":
    transmit_payload()
