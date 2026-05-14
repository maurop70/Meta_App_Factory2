import os

filepath = r'c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\factory_ui\src\App.jsx'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# We already added the import, no need to add it again.
# Let's verify if the import is there.
has_import = any("import BuilderChat from './components/BuilderChat';" in line for line in lines)
if not has_import:
    for i, line in enumerate(lines):
        if "import Atomizer from './components/Atomizer.jsx'" in line:
            lines.insert(i + 1, "import BuilderChat from './components/BuilderChat';\n")
            break

# 2. Delete inline BuilderChat function
start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if line.startswith('// ── BUILDER CHAT'):
        start_idx = i
        break
for i in range(start_idx, len(lines)):
    if lines[i].startswith('// ── REFINE APP — PROGRESS BAR'):
        end_idx = i - 1
        break

if start_idx != -1 and end_idx != -1:
    del lines[start_idx:end_idx]

# 3. Replace <BuilderChat ... />
start_tag = -1
end_tag = -1
for i, line in enumerate(lines):
    if '<BuilderChat' in line:
        start_tag = i
        break
for i in range(start_tag, len(lines)):
    if '/>' in line and i >= start_tag:
        end_tag = i
        break

if start_tag != -1 and end_tag != -1:
    lines[start_tag:end_tag+1] = ["            <BuilderChat />\n"]

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done editing App.jsx correctly')
