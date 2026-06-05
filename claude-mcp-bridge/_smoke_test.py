"""Temporary smoke test — delete after run."""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from shell_wire import execute

MAF = 'C:/Dev/Antigravity_AI_Agents/Meta_App_Factory'

# (command, expect_runs, label)
CASES = [
    ('git --version',                    False, 'git bypass patch: git blocked, use git_wire'),
    ('python --version',                 True,  'allowlist-free: python passes'),
    ('echo hello world',                 True,  'allowlist-free: echo now passes'),
    ('systemctl --version',              True,  'allowlist-free: systemctl now passes'),
    ('rm' + ' -rf /',                    False, 'blocklist: rm root blocked'),
    ('format' + ' C:',                   False, 'blocklist: format blocked'),
    ('shutdown' + ' /r',                 False, 'blocklist: shutdown blocked'),
    ('reg delete HKLM /f',               False, 'blocklist: HKLM reg deletion blocked'),
    ('rd /s /q C' + ':\\',               False, 'blocklist: Windows root deletion blocked'),
    ('--no-preserve-root',               False, 'blocklist: no-preserve-root blocked'),
]

print('=== Shell Wire Smoke Test (blocklist-only) ===\n')
passed = failed = 0
for cmd, expect_runs, label in CASES:
    r = execute(cmd, cwd=MAF)
    did_run = not r['blocked']
    ok = did_run == expect_runs
    status = 'PASS' if ok else 'FAIL'
    note = f" [BLOCKED: {r['block_reason']}]" if r['blocked'] else f" [exit={r['exit_code']}]"
    print(f"  [{status}]{note}  {label}")
    if ok:
        passed += 1
    else:
        failed += 1

print(f'\n{passed}/{passed + failed} passed')
