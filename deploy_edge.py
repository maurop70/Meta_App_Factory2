import os
import subprocess
import sys

# Edge Environment Parameters
EDGE_HOST = os.getenv("EDGE_HOST", "root@104.248.233.220") 
EDGE_PATH = "/var/www/meta_app_factory"
NGINX_PATH = "/etc/nginx/conf.d/meta_app_factory.conf"
SSH_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa")

def run_subprocess(cmd: list, shell=False):
    print(f"\n[ACTUATING] {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # Merge stderr into stdout for chronological streaming
        text=True,
        shell=shell,
        bufsize=1,
        encoding='utf-8',
        errors='replace'
    )
    
    # Enforce real-time telemetry streaming
    for line in iter(process.stdout.readline, ''):
        sys.stdout.write(f"  -> {line}")
        sys.stdout.flush()
        
    process.wait()
    if process.returncode != 0:
        print(f"\n[FATAL EXCEPTION] Transmission failed with RC={process.returncode}")
        sys.exit(process.returncode)

def deploy():
    print("========================================================")
    print("  INITIATING HIGH-VELOCITY EDGE TRANSMISSION PROTOCOL")
    print("========================================================")

    # [ARCHITECTURAL PATCH: OS Provisioning removed. Execute infrastructure scripts independently.]

    print("\n[1/4] Validating Remote Filesystem Matrix...")
    run_subprocess(["ssh", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no", EDGE_HOST, f"mkdir -p {EDGE_PATH}/frontend {EDGE_PATH}/backend /etc/nginx/certs"])

    print("\n[2/4] Transmitting Static React Matrix (UI Payload)...")
    run_subprocess(["scp", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no", "-r", "factory_ui/dist/", f"{EDGE_HOST}:{EDGE_PATH}/frontend/"])

    print("\n[3/4] Transmitting Core Backend Matrix (Persistence Exclusion Active)...")
    # Utilizing generic 'tar' instead of 'tar.exe' to prevent OS-lock-in if executed from WSL/Linux
    tar_cmd = [
        "tar", "-cf", "backend_payload.tar",
        "--exclude=*.db", "--exclude=*.db-wal", "--exclude=*.db-shm",
        "--exclude=__pycache__", "--exclude=node_modules", "--exclude=venv",
        "--exclude=.git",
        "."
    ]
    run_subprocess(tar_cmd)
    run_subprocess(["scp", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no", "backend_payload.tar", f"{EDGE_HOST}:{EDGE_PATH}/backend_payload.tar"])
    
    unpack_cmd = f"cd {EDGE_PATH} && tar -xf backend_payload.tar -C backend/ && rm backend_payload.tar"
    run_subprocess(["ssh", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no", EDGE_HOST, unpack_cmd])
    
    if os.path.exists("backend_payload.tar"):
        os.remove("backend_payload.tar")

    print("\n[4/4] Remote Ignition Sequence (Routing & Daemons)...")
    
    # Transmit Configs
    run_subprocess(["scp", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no", "nginx.conf", f"{EDGE_HOST}:/tmp/nginx.conf"])
    # Bypass cert copy if directory is empty locally to prevent SCP crash
    if os.path.exists("certs") and os.listdir("certs"):
        run_subprocess(["scp", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no", "-r", "certs/*", f"{EDGE_HOST}:/etc/nginx/certs/"])
    run_subprocess(["scp", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no", "systemd_units/core-engine.service", f"{EDGE_HOST}:/etc/systemd/system/core-engine.service"])
    run_subprocess(["scp", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no", "systemd_units/phantom-qa.service", f"{EDGE_HOST}:/etc/systemd/system/phantom-qa.service"])

    # Remote Actuation - Chained via logical ANDs for strict failure cascading
    remote_commands = (
        f"cp /tmp/nginx.conf {NGINX_PATH} && "
        f"cd {EDGE_PATH}/backend && "
        "python3 -m venv venv && "
        "venv/bin/pip install --upgrade pip && "
        "venv/bin/pip install -r requirements.txt && "
        "venv/bin/pip install -r Phantom_QA_Elite/backend/requirements.txt && "
        "mkdir -p /var/log/aether_net && "
        "chown -R www-data:www-data /var/log/aether_net && "
        f"chown -R www-data:www-data {EDGE_PATH}/backend/api.py {EDGE_PATH}/backend/factory_stream.py && " # Targeted chown patch
        "sed -i 's/\\r$//' /etc/systemd/system/core-engine.service /etc/systemd/system/phantom-qa.service && "
        "systemctl daemon-reload && "
        "systemctl enable core-engine.service phantom-qa.service && "
        "rm -f /etc/nginx/sites-enabled/default && "
        "systemctl restart nginx core-engine.service phantom-qa.service"
    )
    run_subprocess(["ssh", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no", EDGE_HOST, remote_commands])
    
    print("\n[SUCCESS] Edge transmission complete. Matrices synchronized. Telemetry streaming active.")

if __name__ == "__main__":
    deploy()
