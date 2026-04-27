import os
import psutil

for proc in psutil.process_iter(['pid', 'name']):
    try:
        for conns in proc.connections(kind='inet'):
            if conns.laddr.port in [5173, 8000]:
                print(f"Killing PID {proc.info['pid']} on port {conns.laddr.port}")
                os.kill(proc.info['pid'], 9)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
