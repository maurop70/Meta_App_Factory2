import subprocess
import os
import sys

def run_command(command, description, cwd=None):
    print(f"[*] {description}")
    print(f"    Executing: {' '.join(command)}")
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            shell=False
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            print(f"[!] FAILED: {description}")
            print(f"    Exit Code: {process.returncode}")
            print(f"    Error: {stderr.strip()}")
            sys.exit(1)
            
        print(f"[+] SUCCESS: {description}\n")
        return stdout
    except Exception as e:
        print(f"[!] FATAL EXCEPTION: {str(e)}")
        sys.exit(1)

def deploy():
    print("--- INITIATING DIGITALOCEAN DEPLOYMENT ORCHESTRATOR ---")
    
    REMOTE_USER = "root"
    REMOTE_HOST = "68.183.30.128"
    REMOTE_DIR = "/opt/erp"
    SSH_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa")
    
    # 1. Local Presentation Compilation (Avoid Remote OOM)
    run_command(
        ["npm.cmd" if sys.platform == 'win32' else "npm", "run", "build"],
        "Compiling local React/Vite binary matrix",
        cwd="./maintenance_frontend"
    )
    
    # 2. Zip the payload securely
    run_command(
        [
            "tar", "-czf", "payload.tar.gz", 
            "--exclude=Maintenance_Work_Order/data/*.db*", 
            "--exclude=Maintenance_Work_Order/__pycache__", 
            "--exclude=maintenance_frontend/node_modules",
            "Maintenance_Work_Order",
            "maintenance_frontend/dist"
        ],
        "Archiving Phase 47 payload (excluding database, including static binary)"
    )
    
    # 3. Transmit via SCP
    run_command(
        ["scp", "-i", SSH_KEY_PATH, "payload.tar.gz", f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DIR}/payload.tar.gz"],
        "Transmitting encrypted payload to DigitalOcean edge cluster"
    )
    
    # 4. Remote Execution
    remote_script = f"""
    set -e
    
    cd {REMOTE_DIR}
    tar -xzf payload.tar.gz
    rm payload.tar.gz
    
    cd {REMOTE_DIR}/Maintenance_Work_Order
    source venv/bin/activate || python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    
    echo "Cycling structural daemons..."
    systemctl restart erp-maintenance-backend.service
    systemctl restart erp-iam-gateway.service
    systemctl restart nginx.service
    """
    
    run_command(
        ["ssh", "-i", SSH_KEY_PATH, f"{REMOTE_USER}@{REMOTE_HOST}", remote_script],
        "Executing remote matrix extraction and absolute daemon cycling"
    )
    
    # 5. Cleanup
    if os.path.exists("payload.tar.gz"):
        os.remove("payload.tar.gz")
    print("--- DIGITALOCEAN DEPLOYMENT SECURED AND MATHEMATICALLY SYNCHRONIZED ---")

if __name__ == "__main__":
    deploy()
