import sys
import os
import json

# Add skills to path
SKILLS_DIR = r"C:\Users\mpetr\.gemini\antigravity\skills"
if SKILLS_DIR not in sys.path: sys.path.append(SKILLS_DIR)

try:
    from n8n_architect.architect import N8NArchitect
    arch = N8NArchitect()
    
    print("--- Fetching Workflows ---")
    workflows = arch.list_workflows()
    
    specialists = ["CFO", "CMO", "HR", "Product", "Sales", "Architect", "Analyst"]
    found = {}
    
    for wf in workflows:
        name = wf.get("name", "")
        print(f"Workflow: {name} (ID: {wf.get('id')}, Active: {wf.get('active')})")
        
        # Check if this workflow IS a specialist agent
        for role in specialists:
            if role.lower() in name.lower():
                found[role] = wf
                
        # Also check nodes inside? The architect list_workflows might not return nodes.
        # We might need to get_workflow(id)
        
    print("\n--- Detailed Inspection ---")
    # If we found dedicated workflows, great. 
    # If not, let's look at the 'Elite Council' workflow for multiple webhooks?
    
    # We'll just dump what we found for now.
    print(json.dumps(found, indent=2, default=str))

except Exception as e:
    print(f"Error: {e}")
