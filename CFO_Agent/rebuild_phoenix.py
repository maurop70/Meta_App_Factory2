import sys
import os
sys.path.append('C:/Users/mpetr/My Drive/Antigravity-AI Agents/Meta_App_Factory/CFO_Agent')
from cfo_engine import CFOExecutionController
import json

test_payload = {
    "cmo_spend": {
        "total": 500000,
        "allocated": 300000,
        "categories": {"digital_ads": 200000, "content": 100000, "events": 0}
    },
    "architect_risk": {
        "structural_score": 95,
        "logic_score": 90,
        "security_score": 98,
        "composite_score": 94.4
    },
    "campaign_list": [
        {"name": "Project Phoenix - Core", "budget": 200000, "projected_revenue": 800000},
        {"name": "Project Phoenix - Expansion", "budget": 100000, "projected_revenue": 300000},
    ]
}

cfo = CFOExecutionController()
# trigger scenario engine to run the physical project phoenix anchor script
result = cfo.scenario_simulator_engine(test_payload, 'Project_Phoenix')
print("Successfully generated and anchored Project Phoenix native model!")
