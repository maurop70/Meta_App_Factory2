"""
Antigravity Preflight Check — Validates environment before app launch.
Usage:
    python preflight.py                  # Check all
    python preflight.py --app alpha      # Check for Alpha V2 Genesis
    python preflight.py --app meta       # Check for Meta App Factory
    python preflight.py --fix            # Attempt auto-fixes where possible

Returns exit code 0 if all checks pass, 1 if critical failures found.
"""
import os, sys, json, importlib

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Check Definitions ───────────────────────────────────────────
# Each check returns (status, message) where status is PASS/WARN/FAIL

def check_env_keys(required_keys, env_path=None):
    """Verify required .env keys are present and non-empty."""
    results = []
    if env_path:
        # Manual parse if dotenv not loaded yet
        env_vars = {}
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip()
        else:
            return [("FAIL", f".env file not found: {env_path}")]
    else:
        env_vars = dict(os.environ)

    for key in required_keys:
        val = env_vars.get(key, "") or os.getenv(key, "")
        if not val or val.startswith("${"):
            results.append(("FAIL", f"Missing or empty: {key}"))
        elif val in ("YOUR_KEY_HERE", "YOUR_WEBHOOK_URL_HERE", "PLACEHOLDER"):
            results.append(("WARN", f"Placeholder value: {key}"))
        else:
            results.append(("PASS", f"{key} = {val[:20]}..."))
    return results


def check_python_deps(requirements_path):
    """Verify pip dependencies are installed."""
    results = []
    if not os.path.exists(requirements_path):
        return [("WARN", "No requirements.txt found")]

    with open(requirements_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Extract package name (before ==, >=, etc.)
            pkg = line.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0].strip()
            # Normalize: underscores → hyphens for import check
            import_name = pkg.replace("-", "_").lower()
            try:
                importlib.import_module(import_name)
                results.append(("PASS", f"{pkg}"))
            except ImportError:
                # Some packages have different import names
                results.append(("WARN", f"{pkg} — not importable (may use different import name)"))
    return results


def check_n8n_connectivity(api_key):
    """Verify N8N API is reachable and key is valid."""
    if not api_key:
        return [("FAIL", "N8N_API_KEY not available — cannot check connectivity")]
    try:
        import requests
        r = requests.get(
            "https://humanresource.app.n8n.cloud/api/v1/workflows?limit=1",
            headers={"X-N8N-API-KEY": api_key},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            count = len(data.get("data", []))
            return [("PASS", f"N8N API reachable — {count}+ workflows found")]
        elif r.status_code == 401:
            return [("FAIL", "N8N API key is invalid (401 Unauthorized)")]
        else:
            return [("WARN", f"N8N API returned HTTP {r.status_code}")]
    except ImportError:
        return [("FAIL", "requests library not installed")]
    except Exception as e:
        return [("FAIL", f"N8N connection failed: {e}")]


def check_docker():
    """Verify Docker is running."""
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True, timeout=10
        )
        if result.returncode == 0:
            return [("PASS", "Docker Engine is running")]
        else:
            return [("WARN", "Docker is installed but not running")]
    except FileNotFoundError:
        return [("WARN", "Docker not installed (not required for all apps)")]
    except Exception as e:
        return [("WARN", f"Docker check failed: {e}")]


def check_file_exists(path, label):
    """Verify a critical file exists."""
    if os.path.exists(path):
        size = os.path.getsize(path)
        return [("PASS", f"{label} ({size:,} bytes)")]
    else:
        return [("FAIL", f"{label} NOT FOUND: {path}")]


def check_port_available(port):
    """Check if a port is available or already in use."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        sock.close()
        return [("PASS", f"Port {port} is available")]
    except OSError:
        return [("WARN", f"Port {port} already in use (existing instance?)")]


# ── Preflight Profiles ──────────────────────────────────────────

PROFILES = {
    "alpha": {
        "name": "Alpha V2 Genesis",
        "env_keys": ["NGROK_AUTH_TOKEN", "N8N_API_KEY", "WEBHOOK_URL"],
        "check_docker": False,
        "check_port": 5005,
        "critical_files": [
            ("server.py", "server.py"),
            ("n8n_lifecycle.py", "n8n_lifecycle.py"),
        ],
    },
    "meta": {
        "name": "Meta App Factory",
        "env_keys": ["N8N_API_KEY"],
        "check_docker": True,
        "check_port": 8000,
        "critical_files": [],
    },
    "generic": {
        "name": "Generic App",
        "env_keys": ["N8N_API_KEY", "WEBHOOK_URL"],
        "check_docker": False,
        "check_port": None,
        "critical_files": [
            ("config.json", "config.json"),
        ],
    },
}


# ── Runner ──────────────────────────────────────────────────────

def run_preflight(profile_name="generic", app_dir=None):
    """Run all preflight checks for a given profile. Returns (passed, failed, warnings)."""
    if app_dir is None:
        app_dir = SCRIPT_DIR

    profile = PROFILES.get(profile_name, PROFILES["generic"])
    env_path = os.path.join(app_dir, ".env")

    print(f"\n{'='*60}")
    print(f"  PREFLIGHT CHECK — {profile['name']}")
    print(f"{'='*60}\n")

    all_results = []
    sections = []

    # 1. Environment Variables
    section_results = check_env_keys(profile["env_keys"], env_path)
    sections.append(("Environment Variables", section_results))
    all_results.extend(section_results)

    # 2. Python Dependencies
    req_path = os.path.join(app_dir, "requirements.txt")
    section_results = check_python_deps(req_path)
    sections.append(("Python Dependencies", section_results))
    all_results.extend(section_results)

    # 3. N8N Connectivity
    # Load API key from .env
    api_key = None
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if line.strip().startswith("N8N_API_KEY="):
                    api_key = line.strip().split("=", 1)[1]
    api_key = api_key or os.getenv("N8N_API_KEY")
    section_results = check_n8n_connectivity(api_key)
    sections.append(("N8N Connectivity", section_results))
    all_results.extend(section_results)

    # 4. Docker (if needed)
    if profile["check_docker"]:
        section_results = check_docker()
        sections.append(("Docker Engine", section_results))
        all_results.extend(section_results)

    # 5. Critical Files
    for label, filename in profile.get("critical_files", []):
        path = os.path.join(app_dir, filename)
        section_results = check_file_exists(path, label)
        sections.append((f"File: {label}", section_results))
        all_results.extend(section_results)

    # 6. Port Check
    if profile.get("check_port"):
        section_results = check_port_available(profile["check_port"])
        sections.append(("Network", section_results))
        all_results.extend(section_results)

    # ── Print Report ────────────────────────────────────────────
    icons = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}

    for section_name, results in sections:
        print(f"  {section_name}:")
        for status, msg in results:
            print(f"    {icons[status]} {msg}")
        print()

    # ── Summary ─────────────────────────────────────────────────
    passed  = sum(1 for s, _ in all_results if s == "PASS")
    warns   = sum(1 for s, _ in all_results if s == "WARN")
    failed  = sum(1 for s, _ in all_results if s == "FAIL")
    total   = len(all_results)

    print(f"{'='*60}")
    if failed == 0:
        print(f"  ✅ PREFLIGHT PASSED — {passed}/{total} checks OK, {warns} warnings")
    else:
        print(f"  ❌ PREFLIGHT FAILED — {failed} critical issue(s) found")
        print(f"     {passed} passed, {warns} warnings, {failed} failures")
    print(f"{'='*60}\n")

    return passed, failed, warns


# ── CLI ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Antigravity Preflight Check")
    parser.add_argument("--app", default="generic", choices=["alpha", "meta", "generic"],
                        help="App profile to check")
    parser.add_argument("--dir", default=None, help="App directory (defaults to script dir)")
    args = parser.parse_args()

    passed, failed, warns = run_preflight(args.app, args.dir)
    sys.exit(1 if failed > 0 else 0)
