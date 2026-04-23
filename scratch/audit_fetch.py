import re

path = r'ERP\Maintenance_Work_Order\index.html'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

issues = []
for i, line in enumerate(lines):
    ln = i + 1
    if r'fetch(\\/api/' in line:
        issues.append(f'L{ln} [CORRUPT_OPEN]: {line.rstrip()[:100]}')
    if re.search(r'fetch\(`\$\{API_BASE\}/api/[^`]*`\)\s*,', line):
        issues.append(f'L{ln} [SPLIT_FETCH]: {line.rstrip()[:100]}')
    if re.search(r'fetch\(`\$\{API_BASE\}/api/[^`]*`\)\)', line):
        issues.append(f'L{ln} [DOUBLE_PAREN]: {line.rstrip()[:100]}')
    if re.search(r"fetch\(['\`]/api/", line):
        issues.append(f'L{ln} [RELATIVE_PATH]: {line.rstrip()[:100]}')

if issues:
    print(f'ISSUES FOUND: {len(issues)}')
    for x in issues:
        print(' ', x)
else:
    print('AUDIT PASSED: Zero fetch syntax violations detected.')
