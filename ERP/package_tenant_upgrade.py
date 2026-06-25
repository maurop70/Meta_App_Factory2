"""
package_tenant_upgrade.py

Packages the multi-tenant upgrade (Components A-D) into a single deployable zip
and generates a non-coder-friendly DEPLOY_GUIDE.txt.

It bundles ONLY the files that were changed or added for this upgrade. Archive
names match the DROPLET layout (verified from deploy_erp.py): the deploy renames
Maintenance_Work_Order -> backend, so the four Python files ship under backend/
and unzip straight over the live code at /opt/erp/backend. The Nginx config is
not backend code, so it ships at the archive root and is copied into Nginx's
config dir separately (see DEPLOY_GUIDE.txt).

Run:  python package_tenant_upgrade.py
Outputs (both in the ERP directory):
  - mwo_tenant_upgrade.zip
  - DEPLOY_GUIDE.txt
"""

import os
import sys
import zipfile

# This script lives in the ERP directory; resolve everything relative to it so
# it works regardless of the current working directory.
ERP_DIR = os.path.dirname(os.path.abspath(__file__))

ZIP_NAME = "mwo_tenant_upgrade.zip"
GUIDE_NAME = "DEPLOY_GUIDE.txt"

# (source path relative to ERP_DIR, archive name). The archive name maps the repo
# layout to the droplet layout so `unzip -o ... -d /opt/erp` lands each file in
# the right place.
FILES = [
    ("Maintenance_Work_Order/maintenance_backend.py", "backend/maintenance_backend.py"),
    ("Maintenance_Work_Order/local_db.py", "backend/local_db.py"),
    ("Maintenance_Work_Order/plugin_manager.py", "backend/plugin_manager.py"),
    ("Maintenance_Work_Order/agent_matrix.py", "backend/agent_matrix.py"),
    ("Maintenance_Work_Order/nginx_erp.conf", "nginx_erp.conf"),
]


def build_zip() -> str:
    zip_path = os.path.join(ERP_DIR, ZIP_NAME)

    # Verify every file exists BEFORE writing anything, so we never ship a
    # partial archive.
    missing = [src for src, _ in FILES if not os.path.isfile(os.path.join(ERP_DIR, src))]
    if missing:
        print("ERROR: refusing to build archive; missing files:")
        for f in missing:
            print(f"  - {f}")
        sys.exit(1)

    if os.path.exists(zip_path):
        os.remove(zip_path)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, arcname in FILES:
            zf.write(os.path.join(ERP_DIR, src), arcname)

    print(f"Created {ZIP_NAME} with {len(FILES)} files:")
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            print(f"  {info.file_size:>9,d} B  {info.filename}")
    print(f"Archive size: {os.path.getsize(zip_path):,d} B")
    return zip_path


def write_guide() -> str:
    guide_path = os.path.join(ERP_DIR, GUIDE_NAME)
    with open(guide_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(DEPLOY_GUIDE)
    print(f"Wrote {GUIDE_NAME} ({os.path.getsize(guide_path):,d} B)")
    return guide_path


DEPLOY_GUIDE = r"""========================================================================
  MWO MULTI-TENANT UPGRADE - DEPLOYMENT GUIDE
========================================================================

This guide deploys "mwo_tenant_upgrade.zip" to the production droplet at
68.183.30.128. Paths and service names below are the VERIFIED droplet
layout (from deploy_erp.py). Copy-paste the commands in order. Do NOT
skip the Nginx test step.

VERIFIED DROPLET LAYOUT
  - Backend code .......... /opt/erp/backend
  - Secrets file (.env) ... /opt/erp/.env
  - Nginx config dir ...... /etc/nginx/sites-available/erp (or similar)
  - Services .............. erp-backend.service, erp-auth.service, nginx.service

WHAT THIS UPGRADE CONTAINS
  backend/maintenance_backend.py  (tenant routing + agent endpoints)
  backend/local_db.py             (per-tenant databases)
  backend/plugin_manager.py       (per-tenant plugin hooks)
  backend/agent_matrix.py         (AI Ops / Support agent endpoints)
  nginx_erp.conf                  (subdomain routing for Nginx)

The zip is laid out for the droplet: the four .py files are under
"backend/" so they unzip straight over /opt/erp/backend. The Nginx file
sits at the top of the zip and is copied into place by hand (Step 5).

You will need:
  - The server login (SSH).
  - Access to your domain registrar.
  - Your Anthropic API key (for the AI Concierge chat endpoint).
  - About 15 minutes.

------------------------------------------------------------------------
STEP 1 - UPLOAD THE ZIP TO THE SERVER
------------------------------------------------------------------------
From your own computer, in the folder that holds the zip:

    scp mwo_tenant_upgrade.zip root@68.183.30.128:/opt/erp/

------------------------------------------------------------------------
STEP 2 - LOG IN AND BACK UP THE CURRENT CODE
------------------------------------------------------------------------
    ssh root@68.183.30.128
    cd /opt/erp
    cp -a backend backend.backup_$(date +%Y%m%d_%H%M%S)

(That copies the live backend so you can undo. Your databases live in
backend/data and are NOT touched by this upgrade.)

------------------------------------------------------------------------
STEP 3 - UNZIP THE UPGRADE (OVERWRITES 4 BACKEND FILES)
------------------------------------------------------------------------
    cd /opt/erp
    unzip -o mwo_tenant_upgrade.zip -d /opt/erp

This overwrites the four files in /opt/erp/backend and drops
/opt/erp/nginx_erp.conf for the next step. Nothing else is touched.

------------------------------------------------------------------------
STEP 4 - ADD THE SECRET KEYS TO /opt/erp/.env
------------------------------------------------------------------------
The AI agent endpoints stay LOCKED until these are set. Generate strong
random values for the two agent keys (run twice, save each result):

    python3 -c "import secrets; print(secrets.token_urlsafe(32))"

Open the secrets file:

    nano /opt/erp/.env

Add these lines (paste your two generated keys, and your real Anthropic
key, after the = signs):

    AGENT_MATRIX_API_KEY=PASTE_FIRST_GENERATED_KEY
    AGENT_SENTRY_PATCH_KEY=PASTE_SECOND_GENERATED_KEY
    ANTHROPIC_API_KEY=sk-ant-...YOUR-REAL-ANTHROPIC-KEY

Optional settings:
    # Pin your real apex domain for tenant detection (recommended):
    TENANT_BASE_DOMAIN=yourdomain.com
    # AI Concierge model. Defaults to claude-opus-4-8 (most capable). Set to
    # claude-sonnet-4-6 for the cheaper current Sonnet tier if you prefer:
    AGENT_CONCIERGE_MODEL=claude-opus-4-8
    # Turn on automatic SSL during tenant provisioning (needs certbot+nginx):
    AGENT_PROVISION_ENABLE_SSL=1
    AGENT_PROVISION_WEBROOT=/opt/erp/frontend

Save and exit (nano: Ctrl+O, Enter, Ctrl+X).

The services read /opt/erp/.env at startup, so the new values only take
effect after the restart in Step 8.

KEEP THESE KEYS PRIVATE. Anyone with AGENT_SENTRY_PATCH_KEY can change
server code through the patch endpoint - treat it like a root password.

------------------------------------------------------------------------
STEP 5 - INSTALL THE NEW NGINX CONFIG
------------------------------------------------------------------------
Edit the new config and replace the placeholder "domain.com" with your
REAL domain:

    nano /opt/erp/nginx_erp.conf

Find this line:
    server_name ~^(?<tenant>[a-zA-Z0-9\-]+)\.domain\.com$ 68.183.30.128;
and change "domain.com" to your domain, e.g.:
    server_name ~^(?<tenant>[a-zA-Z0-9\-]+)\.acmecorp\.com$ 68.183.30.128;
Save and exit.

Find your existing ERP site config and overwrite it with the new file.
It is commonly here:

    cp /opt/erp/nginx_erp.conf /etc/nginx/sites-available/erp

If your site file has a different name, list the directory to find it:

    ls -la /etc/nginx/sites-available/
    ls -la /etc/nginx/sites-enabled/

Overwrite the existing ERP server file (the one currently serving
68.183.30.128) and make sure it is symlinked into sites-enabled:

    ln -sf /etc/nginx/sites-available/erp /etc/nginx/sites-enabled/erp

------------------------------------------------------------------------
STEP 6 - SET UP WILDCARD DNS AT YOUR REGISTRAR
------------------------------------------------------------------------
At your domain registrar, add ONE record so every subdomain reaches the
server:

    Type:  A
    Name:  *            (an asterisk - the wildcard)
    Value: 68.183.30.128
    TTL:   default (or 1 hour)

DNS can take a few minutes to a few hours to propagate.

------------------------------------------------------------------------
STEP 7 - TEST NGINX, THEN RELOAD (DO NOT SKIP THE TEST)
------------------------------------------------------------------------
TEST first (changes nothing live):

    nginx -t

  - "syntax is ok" + "test is successful"  -> continue.
  - Any error -> DO NOT reload. Re-check Step 5 (domain edit + file
    path), fix, and run "nginx -t" again.

Only after the test passes:

    systemctl reload nginx.service

------------------------------------------------------------------------
STEP 8 - RESTART THE APPLICATION SERVICES
------------------------------------------------------------------------
The new code and the new .env values take effect on restart:

    systemctl restart erp-backend.service
    systemctl restart erp-auth.service

Check they came up cleanly:

    systemctl status erp-backend.service --no-pager
    systemctl status erp-auth.service --no-pager

------------------------------------------------------------------------
STEP 9 - VERIFY IT WORKS
------------------------------------------------------------------------
The backend is proxied under /mwo/ and the gateway under /auth/ (matching
the droplet's live Nginx). Direct IP still answers (default tenant):

    curl -I http://68.183.30.128/mwo/

Tenant subdomain is recognized (look for "X-Tenant-Id: clienta"):

    curl -I -H "Host: clienta.yourdomain.com" http://68.183.30.128/mwo/

If X-Tenant-Id matches the subdomain, multi-tenant routing is live. Each
tenant database is created automatically on first use, or provision one
ahead of time by POSTing to /mwo/api/agent/provision/tenant (needs the
X-Agent-Matrix-Key header you set in Step 4).

------------------------------------------------------------------------
IF SOMETHING GOES WRONG (ROLLBACK)
------------------------------------------------------------------------
1) Restore the backed-up code from Step 2:

       cd /opt/erp
       rm -rf backend
       mv backend.backup_YYYYMMDD_HHMMSS backend
       (use the actual backup folder name from Step 2)

2) Restart services:

       systemctl restart erp-backend.service erp-auth.service

3) If you changed Nginx, restore the previous site file, then:

       nginx -t && systemctl reload nginx.service

------------------------------------------------------------------------
QUICK CHECKLIST
------------------------------------------------------------------------
[ ] 1. Uploaded zip to /opt/erp
[ ] 2. Backed up /opt/erp/backend
[ ] 3. unzip -o ... -d /opt/erp  (overwrote backend files)
[ ] 4. Added AGENT_MATRIX_API_KEY, AGENT_SENTRY_PATCH_KEY, ANTHROPIC_API_KEY to /opt/erp/.env
[ ] 5. Edited domain in nginx_erp.conf and installed it to /etc/nginx
[ ] 6. Added wildcard (*) DNS A record at registrar
[ ] 7. Ran "nginx -t" (passed) then reloaded nginx.service
[ ] 8. Restarted erp-backend.service and erp-auth.service
[ ] 9. Verified with curl (default IP + tenant subdomain)
========================================================================
"""


if __name__ == "__main__":
    print(f"ERP directory: {ERP_DIR}\n")
    build_zip()
    print()
    write_guide()
    print("\nPackaging complete.")
