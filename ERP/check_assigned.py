import sys
with open('C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/maintenance_backend.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if '@app.get("/api/mwo/assigned")' in line:
        for j in range(i, min(i+30, len(lines))):
            sys.stdout.write(lines[j])
        break
