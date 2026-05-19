with open("api.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "dispatch_to_csuite" in line or "war_room_orchestrator" in line:
        print(f"Line {i+1}: {line.strip()}")
