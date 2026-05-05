import re

with open('index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_slots = '''            <!-- App Card {i} -->
            <a href="#" class="app-card unassigned" id="app-slot-{i}">
                <div class="card-icon-wrapper">
                    <i class="fa-solid fa-plus"></i>
                </div>
                <div class="card-content">
                    <h2>Available Slot</h2>
                    <p>Ready to be assigned to a new application or script.</p>
                </div>
                <div class="card-footer">
                    <span class="status standby">Unassigned</span>
                    <i class="fa-solid fa-arrow-right launch-icon"></i>
                </div>
            </a>\n\n'''

replacement = ""
for i in range(2, 10):
    replacement += new_slots.format(i=i)
    
replacement = replacement.rstrip() + '\n\n'

with open('index.html', 'w', encoding='utf-8') as f:
    for i, line in enumerate(lines):
        if 49 <= i <= 168: # lines 50 to 169 (0-indexed)
            continue
        if i == 169:
            f.write(replacement)
            f.write(line)
        else:
            f.write(line)

print('Success')
