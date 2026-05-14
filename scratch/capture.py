import os
import subprocess
import time
import requests

# Kill 5000
os.system('python -c "import os, re; lines=os.popen(\'netstat -ano | findstr :5000\').read().splitlines(); pids=set(re.split(r\'\s+\', l.strip())[-1] for l in lines if \':5000 \' in l); [os.system(f\'taskkill /f /PID {p}\') for p in pids if p != \'0\']"')

p = subprocess.Popen(['python', '-m', 'uvicorn', 'api:app', '--port', '5000'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

time.sleep(6)
try:
    requests.get('http://localhost:5000/api/operator/manifest')
    requests.get('http://localhost:5000/api/qa/stream')
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
