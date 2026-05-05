import sys

filepath = 'C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/maintenance_backend.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the start of the catch-all route
catch_all_start = -1
for i, line in enumerate(lines):
    if '@app.get("/{full_path:path}")' in line:
        catch_all_start = i
        break

if catch_all_start == -1:
    print('Catch-all not found')
    sys.exit(1)

# Include the comment above it if present
if lines[catch_all_start-1].startswith('#'):
    catch_all_start -= 1
if lines[catch_all_start-1].startswith('#'):
    catch_all_start -= 1

# Find the end of the catch-all route function
catch_all_end = catch_all_start + 2
while catch_all_end < len(lines):
    # A new route or something that isn't indented
    if lines[catch_all_end].startswith('@app') or (lines[catch_all_end].strip() != '' and not lines[catch_all_end].startswith(' ')):
        break
    catch_all_end += 1

print('Catch-all block is lines', catch_all_start, 'to', catch_all_end)

# Extract the block
catch_all_block = lines[catch_all_start:catch_all_end]

# Remove it from the original list
del lines[catch_all_start:catch_all_end]

lines.append('\n')
lines.extend(catch_all_block)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed route order!')
