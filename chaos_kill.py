import subprocess
import re
import sys
import time

def kill_port_process(port):
    print(f"[*] Locating process utilizing Port {port}...")
    try:
        # Run netstat to find the process ID
        netstat_output = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True, text=True)
        
        # Parse the output to extract the PID (last column)
        lines = netstat_output.strip().split('\n')
        pids = set()
        
        for line in lines:
            if 'LISTENING' in line:
                parts = line.split()
                if len(parts) >= 5:
                    pids.add(parts[-1])
                    
        if not pids:
            print(f"[-] No listening process found on Port {port}.")
            return False
            
        for pid in pids:
            if pid == '0':
                continue
                
            print(f"[*] Identified target PID: {pid}. Engaging kill sequence...")
            
            # Execute taskkill
            kill_command = f'taskkill /F /PID {pid}'
            kill_output = subprocess.check_output(kill_command, shell=True, text=True)
            print(f"[+] SUCCESS: {kill_output.strip()}")
            return True
            
    except subprocess.CalledProcessError as e:
        print(f"[-] FATAL CRASH INDUCED: Failed to find or kill process. Error code: {e.returncode}")
        return False
    except Exception as e:
        print(f"[-] UNEXPECTED ERROR: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("    CHAOS TEST INITIALIZED: STRIKE PROTOCOL ALPHA")
    print("=" * 50)
    time.sleep(1) # Dramatic pause
    
    # Target port from manifest: CFO_Agent = 5070
    target_port = 5070 
    
    success = kill_port_process(target_port)
    
    if success:
        print("\n[!] Chaos Strike Complete. Watchdog trigger sequence should follow.")
    else:
        print("\n[!] Chaos Strike Failed.")
        
    print("=" * 50)
