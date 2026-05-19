import os

app_jsx_path = r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\factory_ui\src\App.jsx"

with open(app_jsx_path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "systemmap" in line.lower() or "system_map" in line.lower() or "system map" in line.lower():
        safe_line = line.encode('ascii', 'ignore').decode('ascii')
        print(f"Line {i+1}: {safe_line.strip()[:100]}")
        # Print next 35 lines
        for j in range(1, 35):
            if i + j < len(lines):
                safe_line = lines[i+j].encode('ascii', 'ignore').decode('ascii')
                print(f"  +{j}: {safe_line.rstrip()[:120]}")
        print("-" * 50)
