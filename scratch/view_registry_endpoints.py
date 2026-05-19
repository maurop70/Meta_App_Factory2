with open(r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\api.py", "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "/api/registry" in line or "/api/agents/status" in line:
        print(f"Line {i+1}: {line.strip()}")
        # print next 30 lines
        for j in range(1, 30):
            if i + j < len(lines):
                safe_line = lines[i+j].encode('ascii', 'ignore').decode('ascii')
                print(f"  +{j}: {safe_line.rstrip()}")
        print("-" * 50)
