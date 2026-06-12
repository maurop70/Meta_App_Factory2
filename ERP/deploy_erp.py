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
    tar -xzf payload.tar.gz \\
        --transform='s|^Maintenance_Work_Order|backend|' \\
        --transform='s|^maintenance_frontend/dist|frontend|'
    rm payload.tar.gz

    cd {REMOTE_DIR}/backend
    source venv/bin/activate || python3 -m venv venv && source venv/bin/activate
    venv/bin/python3 -m pip install -r requirements.txt

    # Patch stale venv path in all venv scripts (prevents crash loop if deployed from old Maintenance_Work_Order path)
    grep -rl '/opt/erp/Maintenance_Work_Order/venv/bin/python3' {REMOTE_DIR}/backend/venv/bin/ 2>/dev/null | xargs -r sed -i 's|#!/opt/erp/Maintenance_Work_Order/venv/bin/python3|#!/opt/erp/backend/venv/bin/python3|g' || true
    sed -i 's|Maintenance_Work_Order/venv|backend/venv|g' /etc/systemd/system/erp-backend.service || true
    systemctl daemon-reload

    # Pre-migration safety net: timestamped backup of the live DB, kept in
    # archives/ until the user confirms post-deploy health. Never auto-deleted.
    mkdir -p {REMOTE_DIR}/backend/archives
    TS=$(date +%Y%m%d_%H%M%S)
    if [ -f {REMOTE_DIR}/backend/data/maintenance_erp.db ]; then
        cp {REMOTE_DIR}/backend/data/maintenance_erp.db {REMOTE_DIR}/backend/archives/maintenance_erp.pre_deploy_$TS.db
        echo "Pre-migration backup: {REMOTE_DIR}/backend/archives/maintenance_erp.pre_deploy_$TS.db"
    fi

    # Schema synchronization: idempotent inventory migration (suppliers, POs,
    # manual logs, CFO role). set -e aborts the deploy if it fails, preventing
    # new code from booting against an unmigrated database.
    echo "Running inventory schema migration..."
    venv/bin/python3 migration_inventory.py

    echo "Restarting erp-backend..."
    systemctl restart erp-backend.service
    systemctl restart nginx.service

    sleep 2
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{{http_code}}" http://localhost/)
    echo "HTTP status: $HTTP_STATUS"
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
