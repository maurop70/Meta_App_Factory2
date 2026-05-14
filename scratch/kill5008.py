import os
import re
lines=os.popen('netstat -ano | findstr :5008').read().splitlines()
pids=set(re.split(r'\s+', l.strip())[-1] for l in lines if ':5008 ' in l)
[os.system(f'taskkill /f /PID {p}') for p in pids if p != '0']
