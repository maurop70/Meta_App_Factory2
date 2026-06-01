import os
import sys
import time
import socket
import subprocess
import urllib.request
import urllib.error
import psutil

# ── Configuration Constants ─────────────────────────────────
CMO_PORT = 5020
CMO_DIR = os.path.abspath(r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\Project_Aether\C-Suite_Active_Logic\CMO\backend")
CMO_SCRIPT = "server.py"

VENTURE_PORT = 5110
VENTURE_DIR = os.path.abspath(r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\Venture_Architect_Agent\backend")
VENTURE_SCRIPT = "server.py"

def terminate_process_on_port(port):
    """Scan all active connections and terminate any process listening on the target port."""
    print(f"[PORT CHECK] Scanning for processes listening on port {port}...")
    terminated_any = False
    
    # Locate all active processes using the target port
    for conn in psutil.net_connections(kind='inet'):
        if conn.laddr.port == port and conn.status == 'LISTEN':
            pid = conn.pid
            if pid:
                try:
                    p = psutil.Process(pid)
                    print(f"[KILL] Found process {pid} ({p.name()}) listening on port {port}. Terminating...")
                    
                    # Terminate process and all its children
                    for child in p.children(recursive=True):
                        try:
                            child.terminate()
                        except Exception:
                            pass
                    p.terminate()
                    
                    # Wait for termination
                    try:
                        p.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        print(f"[KILL] Process {pid} did not exit. Force killing...")
                        p.kill()
                    
                    print(f"[KILL] Process {pid} successfully terminated.")
                    terminated_any = True
                except Exception as e:
                    print(f"[WARN] Error terminating process {pid} on port {port}: {e}")
                    
    if not terminated_any:
        print(f"[PORT CHECK] Port {port} is free and clear.")
    else:
        # Give OS socket a moment to release the address binding
        time.sleep(1.5)

def check_socket_ready(port):
    """Quick check to see if a port is actively open and listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except Exception:
            return False

def verify_endpoint_http_200(url):
    """Assert that the endpoint returns a strict 200 OK HTTP status code."""
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Antigravity-C-Suite-Ignition/1.0'}
        )
        with urllib.request.urlopen(req, timeout=1.5) as response:
            return response.status == 200
    except urllib.error.HTTPError as e:
        # If it returns an error page (e.g. 404/500), but still responds
        return e.code == 200
    except Exception as e:
        return False

def spawn_detached_agent(script_dir, script_name, port):
    """Autonomously spawn the FastAPI server in a detached background process."""
    script_path = os.path.join(script_dir, script_name)
    print(f"[LAUNCH] Spawning detached server: {script_path} on port {port}...")
    
    env = os.environ.copy()
    env["PORT"] = str(port)
    
    # Detach and CREATE_NO_WINDOW flags for premium Windows background management
    creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    
    try:
        proc = subprocess.Popen(
            [sys.executable, script_name],
            cwd=script_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags
        )
        print(f"[LAUNCH] detaching uvicorn process. Spawned with OS PID: {proc.pid}")
        return proc
    except Exception as e:
        print(f"[ERROR] Failed to spawn uvicorn process for {script_name}: {e}")
        sys.exit(1)

def main():
    print("====================================================================")
    print("   Autonomous C-Suite Swarm Ignition Engine                         ")
    print("   Meta App Factory | Antigravity V3                                ")
    print("====================================================================")
    
    # ── STAGE 1: Port Collision Mitigation ─────────────────────────
    terminate_process_on_port(CMO_PORT)
    terminate_process_on_port(VENTURE_PORT)
    
    # ── STAGE 2: Detached Process Actuation ────────────────────────
    spawn_detached_agent(CMO_DIR, CMO_SCRIPT, CMO_PORT)
    spawn_detached_agent(VENTURE_DIR, VENTURE_SCRIPT, VENTURE_PORT)
    
    # ── STAGE 3: Diagnostic Socket Verification ───────────────────
    start_time = time.time()
    max_wait = 15.0  # Strict 15-second backoff boundary
    
    print("\n[DIAGNOSTIC] Verification sequence initiated...")
    
    cmo_verified = False
    venture_verified = False
    
    while time.time() - start_time < max_wait:
        elapsed = time.time() - start_time
        
        # Verify CMO Agent (Port 5020)
        if not cmo_verified:
            if check_socket_ready(CMO_PORT) and verify_endpoint_http_200(f"http://127.0.0.1:{CMO_PORT}/"):
                print(f"[OK] CMO Agent actively listening on port {CMO_PORT} (took {elapsed:.2f}s)")
                cmo_verified = True
                
        # Verify Venture Architect Agent (Port 5110)
        if not venture_verified:
            if check_socket_ready(VENTURE_PORT) and verify_endpoint_http_200(f"http://127.0.0.1:{VENTURE_PORT}/"):
                print(f"[OK] Venture Architect Agent actively listening on port {VENTURE_PORT} (took {elapsed:.2f}s)")
                venture_verified = True
                
        if cmo_verified and venture_verified:
            print("\n[SUCCESS] All C-Suite swarm nodes are fully hydrated, verified, and listening!")
            sys.exit(0)
            
        time.sleep(0.5)
        
    # Timeout exceeded check
    print("\n[TIMEOUT] Verification sequence failed within the 15-second socket window.")
    if not cmo_verified:
        print(f"  • CMO Agent (Port {CMO_PORT}) did not respond to health socket.")
    if not venture_verified:
        print(f"  • Venture Architect Agent (Port {VENTURE_PORT}) did not respond to health socket.")
    sys.exit(1)

if __name__ == "__main__":
    main()
