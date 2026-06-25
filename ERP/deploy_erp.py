import json
import subprocess
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

RECIPES_LOG = (Path(__file__).parent.parent / "claude-mcp-bridge" / "logs"
               / "deploy_recipes.jsonl")


def _local_git_sha() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"],
                             cwd=str(Path(__file__).parent.parent),
                             capture_output=True, text=True, timeout=15)
        return out.stdout.strip()[:12] or "unknown"
    except Exception:
        return "unknown"


def _record_recipe(recipe: dict) -> None:
    """Rollback recipe BEFORE mutating the target (CLAUDE_RULES 7.5)."""
    RECIPES_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RECIPES_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(recipe) + "\n")
    print(f"[*] Rollback recipe recorded: {json.dumps(recipe)}")


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
            print(f"    Stdout:\n{stdout.strip()}")
            print(f"    Error:\n{stderr.strip()}")
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
            "--exclude=Module_0_Gateway/data/*.db*",
            "--exclude=Module_0_Gateway/__pycache__",
            "Maintenance_Work_Order",
            "Module_0_Gateway",
            "maintenance_frontend/dist"
        ],
        "Archiving Phase 47 payload (excluding databases, including gateway + static binary)"
    )
    
    # 3. Transmit via SCP
    run_command(
        ["scp", "-i", SSH_KEY_PATH, "payload.tar.gz", f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DIR}/payload.tar.gz"],
        "Transmitting encrypted payload to DigitalOcean edge cluster"
    )
    
    # 4. Rollback recipe BEFORE any remote mutation (CLAUDE_RULES 7.5)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    git_sha = _local_git_sha()
    db_backup = f"{REMOTE_DIR}/backend/archives/maintenance_erp.pre_deploy_{ts}.db"
    _record_recipe({
        "ts": datetime.now(timezone.utc).isoformat(),
        "host": REMOTE_HOST,
        "git_sha": git_sha,
        "db_backup": db_backup,
        "code_snapshot": f"{REMOTE_DIR}/backend_prev",
        "services": ["erp-backend.service", "erp-auth.service", "nginx.service"],
        "rollback": ("auto on failed probe; manual: restore backend_prev + "
                     "frontend_prev, restart services"),
    })

    # 5. Remote Execution — snapshot -> mutate -> probe -> auto-rollback
    remote_script = f"""
    set -e

    cd {REMOTE_DIR}

    # Code snapshot for auto-rollback (includes pre-deploy data/ state)
    rm -rf backend_prev frontend_prev gateway_prev
    [ -d backend ]  && cp -a backend  backend_prev
    [ -d frontend ] && cp -a frontend frontend_prev
    [ -d gateway ]  && cp -a gateway  gateway_prev

    rollback() {{
        echo "!! DEPLOY FAILED — AUTO-ROLLBACK INITIATED (recipe ts={ts}, prev sha) !!"
        if [ -d {REMOTE_DIR}/backend_prev ]; then
            rm -rf {REMOTE_DIR}/backend
            cp -a {REMOTE_DIR}/backend_prev {REMOTE_DIR}/backend
        fi
        if [ -d {REMOTE_DIR}/frontend_prev ]; then
            rm -rf {REMOTE_DIR}/frontend
            cp -a {REMOTE_DIR}/frontend_prev {REMOTE_DIR}/frontend
        fi
        if [ -d {REMOTE_DIR}/gateway_prev ]; then
            rm -rf {REMOTE_DIR}/gateway
            cp -a {REMOTE_DIR}/gateway_prev {REMOTE_DIR}/gateway
        fi
        systemctl restart erp-backend.service erp-auth.service nginx.service || true
        sleep 3
        RB_STATUS=$(curl -s -o /dev/null -w "%{{http_code}}" --max-time 5 http://localhost/ || echo 000)
        echo "ROLLBACK_STATUS: HTTP $RB_STATUS"
    }}
    trap 'rollback; exit 1' ERR

    tar -xzf payload.tar.gz \\
        --transform='s|^Maintenance_Work_Order|backend|' \\
        --transform='s|^Module_0_Gateway|gateway|' \\
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
    if [ -f {REMOTE_DIR}/backend/data/maintenance_erp.db ]; then
        cp {REMOTE_DIR}/backend/data/maintenance_erp.db {db_backup}
        echo "Pre-migration backup: {db_backup}"
    fi

    # Schema synchronization: idempotent inventory migration (suppliers, POs,
    # manual logs, CFO role). Failure triggers the ERR trap -> auto-rollback.
    echo "Running inventory schema migration..."
    venv/bin/python3 migration_inventory.py

    # Departmental inventory responsibility: adds erp_employees.is_inventory_manager
    # (ERP + gateway IAM) and erp_categories.department_id. Idempotent. Failure
    # triggers the ERR trap -> auto-rollback.
    echo "Running inventory responsibility migration..."
    venv/bin/python3 migrate_inventory_responsibility.py

    # Dynamic role registry: seeds erp_roles and rebuilds erp_employees without
    # the static CHECK(role IN ...) constraint across the default DB AND every
    # tenant DB under data/tenants/ (the script globs them itself). Each DB is
    # snapshotted to archives/ first. Idempotent. Failure triggers the ERR trap
    # -> auto-rollback.
    echo "Running dynamic roles migration..."
    venv/bin/python3 migrate_dynamic_roles.py

    # Gateway device-recognition migration. Runs with the shared backend venv
    # (the gateway has no venv of its own — erp-auth.service uses backend/venv).
    # The script targets /opt/erp/gateway/data/gateway_core.db via __file__, so
    # cwd is irrelevant. Failure triggers the ERR trap -> auto-rollback.
    echo "Running gateway device-recognition migration..."
    /opt/erp/backend/venv/bin/python3 /opt/erp/gateway/migrate_device_recognition.py

    echo "Restarting erp-backend, erp-auth, nginx..."
    systemctl restart erp-backend.service
    systemctl restart erp-auth.service
    systemctl restart nginx.service

    # Closed-loop probe: 5 attempts, 3s apart. Non-200 -> auto-rollback.
    trap - ERR
    PROBE_OK=0
    for i in 1 2 3 4 5; do
        sleep 3
        HTTP_STATUS=$(curl -s -o /dev/null -w "%{{http_code}}" --max-time 5 http://localhost/ || echo 000)
        echo "Probe $i: HTTP $HTTP_STATUS"
        if [ "$HTTP_STATUS" = "200" ]; then PROBE_OK=1; break; fi
    done
    if [ "$PROBE_OK" != "1" ]; then
        rollback
        exit 1
    fi

    # Gateway health probe: the auth service must answer, not just the frontend.
    # A broken auth deploy would otherwise pass on the frontend-only probe above.
    # Wrap in retry loop to allow service startup latency.
    GW_OK=0
    for i in 1 2 3 4 5; do
        sleep 3
        GW_STATUS=$(curl -s -o /dev/null -w "%{{http_code}}" --max-time 5 http://localhost/auth/api/v1/auth/public-key || echo 000)
        echo "Gateway probe $i: HTTP $GW_STATUS"
        if [ "$GW_STATUS" = "200" ]; then GW_OK=1; break; fi
    done
    if [ "$GW_OK" != "1" ]; then
        echo "!! Gateway unhealthy after deploy — rolling back !!"
        rollback
        exit 1
    fi

    echo "DEPLOY_VERIFIED: HTTP 200 + gateway 200 (sha {git_sha}, backup {db_backup})"
    """

    run_command(
        ["ssh", "-i", SSH_KEY_PATH, f"{REMOTE_USER}@{REMOTE_HOST}", remote_script],
        "Executing remote deploy with snapshot, probe, and auto-rollback"
    )
    
    # 5. Cleanup
    if os.path.exists("payload.tar.gz"):
        os.remove("payload.tar.gz")
    print("--- DIGITALOCEAN DEPLOYMENT SECURED AND MATHEMATICALLY SYNCHRONIZED ---")

if __name__ == "__main__":
    deploy()
