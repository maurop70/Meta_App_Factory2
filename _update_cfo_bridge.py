"""Fix CRITICAL instruction in CTO prompt."""
import re

with open('api.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the CRITICAL line using regex (handles line endings)
old = (
    '"CRITICAL: technical_feasibility_score MUST be 1-10. Scores below 4 trigger a TECHNICAL GATE FAILURE "'
    '\n'
    '        "and block the CFO from building the financial model. For NON-DIGITAL projects, score reflects "'
    '\n'
    '        "our capability to AUTOMATE AND MONITOR the venture. Be rigorous but fair.'
)

new = (
    '"CRITICAL: technical_feasibility_score MUST be 1-10. Scores below 4 trigger a TECHNICAL GATE FAILURE "'
    '\n'
    '        "and block the CFO from building the financial model. For NON-DIGITAL projects, score reflects "'
    '\n'
    '        "our capability to AUTOMATE AND MONITOR the venture. "'
    '\n'
    '        "cfo_ready_metrics.infrastructure_cost_estimate = monthly hosting/tooling/API costs based on tech_stack. "'
    '\n'
    '        "cfo_ready_metrics.development_buffer_weeks = 1.5x implementation_timeline_weeks if feasibility below 7, else same as timeline. "'
    '\n'
    '        "cfo_ready_metrics.tech_debt_risk_premium_pct = percentage to add to CFO budget for V3 compliance hardening. "'
    '\n'
    '        "The Technical Gate is Aether-Native and feeds real-time infrastructure costs to the CFO. Be rigorous but fair.'
)

if old in content:
    content = content.replace(old, new)
    with open('api.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: CRITICAL instruction updated with cfo_ready_metrics rules")
else:
    print("FAIL: Could not find CRITICAL instruction")
    # Debug: find the line
    idx = content.find('CRITICAL: technical_feasibility_score')
    if idx >= 0:
        print(f"Found at index {idx}")
        print(repr(content[idx:idx+400]))
