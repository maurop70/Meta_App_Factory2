with open(r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\api.py", "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "/api/v3/map" in line:
        print(f"Line {i+1}: {line.strip()}")
        # print next 40 lines
        for j in range(1, 40):
            print(f"  +{j}: {lines[i+j].rstrip()}")
        break
