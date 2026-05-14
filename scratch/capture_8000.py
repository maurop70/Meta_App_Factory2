import os
import subprocess
import time
import requests

# Kill 8000 if running
os.system('python -c "import os, re; lines=os.popen(\'netstat -ano | findstr :8000\').read().splitlines(); pids=set(re.split(r\'\\s+\', l.strip())[-1] for l in lines if \':8000 \' in l); [os.system(f\'taskkill /f /PID {p}\') for p in pids if p != \'0\']"')

p = subprocess.Popen(['python', 'api.py'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

time.sleep(5)
try:
    requests.get('http://localhost:8000/api/operator/manifest')
    requests.get('http://localhost:8000/api/qa/stream')
    requests.get('http://localhost:8000/api/system/stats')
    requests.get('http://localhost:8000/api/apps/running')
except:
    pass
time.sleep(2)
p.terminate()
out, _ = p.communicate()

# Just print the tracebacks
traceback_lines = []
in_tb = False
for line in out.split('\n'):
    if 'Traceback' in line or 'Error:' in line or 'Exception' in line:
        in_tb = True
    if in_tb:
        traceback_lines.append(line)
        if line.startswith('INFO:') or line.startswith('2026-') or line.startswith('['):
            in_tb = False

print('\n'.join(traceback_lines))
