import sys
with open('Alpha_V2_Genesis/server.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if line.strip() == ':' and i+1 < len(lines) and '"""Auto-activates any deactivated Alpha N8N workflows on startup."""' in lines[i+1]:
        skip = True
    if skip and line.startswith('if __name__ == "__main__":'):
        skip = False
    
    if not skip:
        new_lines.append(line)

with open('Alpha_V2_Genesis/server.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Fixed syntax error")
