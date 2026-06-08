"""
MAF Production Deploy
---------------------
Packages the MAF backend using Python's tarfile library,
uploads via paramiko SFTP, then restarts systemd services.

Usage:
    python deploy_maf.py

Target: root@104.248.233.220:/var/www/meta_app_factory/backend/
"""

import os
import sys
import tarfile
import tempfile
import time
from pathlib import Path

# Reconfigure stdout/stderr to UTF-8 so remote systemctl output (● etc.) prints cleanly
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Config ────────────────────────────────────────────────────────────────────
REMOTE_USER = "root"
REMOTE_HOST = "104.248.233.220"
REMOTE_DIR  = "/var/www/meta_app_factory/backend"
SSH_KEY     = os.path.expanduser("~/.ssh/id_rsa")
MAF_ROOT    = Path(__file__).parent

# Path components that trigger exclusion (matched against every part of the path)
EXCLUDE_DIRS: set[str] = {
    ".git", "node_modules", "venv", "__pycache__", ".pytest_cache",
    ".claude", ".Gemini_state", ".agents", ".audit_snapshots",
    ".secure_backup", "dist", "build",
}

# File-level exclusions
EXCLUDE_SUFFIXES: set[str] = {".pyc", ".pyo"}
EXCLUDE_NAMES:    set[str]  = {".DS_Store"}


# ── Paramiko bootstrap ────────────────────────────────────────────────────────

def _ensure_paramiko():
    """Import paramiko, auto-installing if absent."""
    try:
        import paramiko
        return paramiko
    except ImportError:
        print("[*] paramiko not found — installing...")
        import subprocess
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "paramiko", "-q"],
            check=True,
        )
        req = MAF_ROOT / "requirements.txt"
        if req.exists() and "paramiko" not in req.read_text():
            with open(req, "a") as f:
                f.write("paramiko\n")
            print("[+] Added paramiko to requirements.txt")
        import paramiko
        return paramiko


# ── Archive builder ───────────────────────────────────────────────────────────

def _should_exclude(rel: Path) -> bool:
    for part in rel.parts:
        if part in EXCLUDE_DIRS:
            return True
        if part.startswith(".env"):      # .env, .env.local, .env.production …
            return True
    if rel.suffix in EXCLUDE_SUFFIXES:
        return True
    if rel.name in EXCLUDE_NAMES:
        return True
    return False


def _build_archive() -> tuple[str, int]:
    """
    Walk MAF_ROOT and pack all non-excluded files into a gzip tarball.
    Returns (tmp_path, compressed_size_bytes).
    """
    print("[1/4] Building archive...")
    fd, tmp_path = tempfile.mkstemp(suffix=".tar.gz", prefix="maf_deploy_")
    os.close(fd)

    file_count = 0
    with tarfile.open(tmp_path, "w:gz") as tar:
        for item in sorted(MAF_ROOT.rglob("*")):
            if not item.is_file():
                continue
            rel = item.relative_to(MAF_ROOT)
            if _should_exclude(rel):
                continue
            arcname = str(rel).replace("\\", "/")   # normalise to POSIX paths
            tar.add(item, arcname=arcname)
            file_count += 1

    size = os.path.getsize(tmp_path)
    print(f"    {file_count} files  ->  {size / 1024 / 1024:.1f} MB compressed")

    # ── Integrity check: read the archive back before any upload ─────────────
    print("    Verifying archive integrity...")
    KEY_MEMBER = "claude-mcp-bridge/rules/CLAUDE_RULES.md"
    try:
        with tarfile.open(tmp_path, "r:gz") as verify:
            members = verify.getnames()
    except (tarfile.TarError, EOFError, OSError) as exc:
        os.remove(tmp_path)
        raise RuntimeError(f"Archive failed integrity check (corrupt gzip): {exc}") from exc

    if not members:
        os.remove(tmp_path)
        raise RuntimeError("Archive failed integrity check: 0 members found")

    if KEY_MEMBER not in members:
        os.remove(tmp_path)
        raise RuntimeError(
            f"Archive failed integrity check: key file missing — {KEY_MEMBER}\n"
            f"  (found {len(members)} members; check EXCLUDE_DIRS)"
        )

    print(f"    Archive OK — {len(members)} members, key file present")
    return tmp_path, size


# ── Upload ────────────────────────────────────────────────────────────────────

def _upload(paramiko, ssh, local_path: str, size: int) -> None:
    """SFTP upload with a live progress bar."""
    print("\n[2/4] Uploading archive to server...")
    remote_path = f"{REMOTE_DIR}/deploy.tar.gz"
    start = time.monotonic()

    def _progress(sent: int, total: int) -> None:
        pct  = sent * 100 // total
        rate = (sent / 1024) / max(time.monotonic() - start, 0.001)
        print(
            f"\r    {pct:3d}%  {sent / 1024 / 1024:.1f} / {total / 1024 / 1024:.1f} MB"
            f"  @ {rate:.0f} KB/s ",
            end="",
            flush=True,
        )

    with ssh.open_sftp() as sftp:
        sftp.put(local_path, remote_path, callback=_progress)

    elapsed = time.monotonic() - start
    print(f"\n    Transfer complete in {elapsed:.1f}s")


# ── Remote execution ──────────────────────────────────────────────────────────

def _remote(ssh, cmd: str, description: str, allow_fail: bool = False) -> tuple[int, str]:
    """Run a remote command, stream its output, exit on failure (unless allow_fail)."""
    print(f"\n[*] {description}")
    _stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    rc  = stdout.channel.recv_exit_status()

    for line in out.strip().splitlines():
        print(f"    {line}")
    if err.strip():
        for line in err.strip().splitlines():
            print(f"    STDERR: {line}")

    if rc != 0 and not allow_fail:
        print(f"[!] FAILED (exit {rc})")
        sys.exit(1)
    print("[+] OK" if rc == 0 else f"[!] exit {rc} (non-fatal)")
    return rc, out


# ── Main deploy ───────────────────────────────────────────────────────────────

def deploy() -> None:
    paramiko = _ensure_paramiko()

    print("=" * 60)
    print("  MAF — Production Deploy")
    print(f"  Target : {REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DIR}")
    print(f"  SSH key: {SSH_KEY}")
    print("=" * 60)

    tmp_path = None
    try:
        # ── 1. Build archive ───────────────────────────────────
        tmp_path, archive_size = _build_archive()

        # ── 2. Connect ─────────────────────────────────────────
        print(f"\n[*] Connecting to {REMOTE_USER}@{REMOTE_HOST}...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            REMOTE_HOST,
            username=REMOTE_USER,
            key_filename=SSH_KEY,
            timeout=30,
        )
        print("[+] Connected")

        # ── 3. Upload ──────────────────────────────────────────
        _upload(paramiko, ssh, tmp_path, archive_size)

        # ── 4. Extract on server ───────────────────────────────
        _remote(ssh, f"""
set -e
cd {REMOTE_DIR}
echo "Extracting archive..."
tar -xzf deploy.tar.gz
rm -f deploy.tar.gz
echo "Extraction complete"
""", "Extracting archive on server")

        # ── 5. Install Python deps ─────────────────────────────
        _remote(
            ssh,
            f"{REMOTE_DIR}/venv/bin/pip install -r {REMOTE_DIR}/requirements.txt -q",
            "Installing Python dependencies",
        )

        # ── 6. Restart services ────────────────────────────────
        _remote(ssh, "systemctl restart core-engine phantom-qa",
                "Restarting core-engine and phantom-qa")

        # ── 7. Post-restart verify ─────────────────────────────
        print("\n[4/4] Waiting 5s for services to settle...")
        time.sleep(5)

        _remote(
            ssh,
            "systemctl status core-engine phantom-qa --no-pager",
            "Post-restart service status",
            allow_fail=True,
        )

        ssh.close()

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
            print("\n[*] Cleaned up local temp archive")

    print("\n" + "=" * 60)
    print("  DEPLOY COMPLETE")
    print(f"  Production: http://{REMOTE_HOST}")
    print("=" * 60)


if __name__ == "__main__":
    deploy()
