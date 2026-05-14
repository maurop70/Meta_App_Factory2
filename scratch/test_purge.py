import sys
import os

sys.path.append('c:\\Dev\\Antigravity_AI_Agents\\Meta_App_Factory')
os.chdir('c:\\Dev\\Antigravity_AI_Agents\\Meta_App_Factory')

import api
print("Testing api.py get_registry()...")
print(api.get_registry())

import operator_agent
print("Testing operator_agent.py get_manifest()...")
print(operator_agent.get_manifest())
