import subprocess
import os
import sys

def run_command(command, description):
    print(f"[*] {description}")
    print(f"    Executing: {' '.join(command)}")
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
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
    REMOTE_HOST = "your_digitalocean_ip" # To be injected via environment or Vault
    REMOTE_DIR = "/opt/erp/maintenance_module"
    SSH_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa")
    
    # 1. Zip the payload securely
    run_command(
        ["tar", "-czf", "payload.tar.gz", "--exclude=data/maintenance_erp.db", "--exclude=__pycache__", "--exclude=node_modules", "."],
        "Archiving Phase 47 payload (excluding database matrix)"
    )
    
    # 2. Transmit via SCP
    run_command(
        ["scp", "-i", SSH_KEY_PATH, "payload.tar.gz", f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DIR}/payload.tar.gz"],
        "Transmitting encrypted payload to DigitalOcean edge cluster"
    )
    
    # 3. Remote Execution: Extract, Install Dependencies, Restart Daemons
    remote_script = f"""
    cd {REMOTE_DIR}
    tar -xzf payload.tar.gz
    rm payload.tar.gz
    
    # Backend dependencies
    source venv/bin/activate || python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    
    # Frontend dependencies and build
    cd ../maintenance_frontend
    npm ci
    npm run build
    
    # Cycle the systemd daemons
    systemctl restart erp-maintenance-backend.service
    systemctl restart nginx.service
    """
    
    run_command(
        ["ssh", "-i", SSH_KEY_PATH, f"{REMOTE_USER}@{REMOTE_HOST}", remote_script],
        "Executing remote extraction and daemon cycling"
    )
    
    # Cleanup
    os.remove("payload.tar.gz")
    print("--- DIGITALOCEAN DEPLOYMENT SECURED ---")

if __name__ == "__main__":
    deploy()
