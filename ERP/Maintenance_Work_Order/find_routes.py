with open("maintenance_backend.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'app.get("/inventory' in line or 'app.post("/inventory' in line:
        print(f"Line {i+1}: {line.strip()}")
