with open(r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\factory_ui\src\App.jsx", "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

print("Lines 60-150 in App.jsx:")
for i in range(59, 150):
    if i < len(lines):
        safe_line = lines[i].encode('ascii', 'ignore').decode('ascii')
        print(f"Line {i+1}: {safe_line.rstrip()}")
