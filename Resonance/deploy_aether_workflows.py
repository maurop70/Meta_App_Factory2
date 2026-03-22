import sys, json, os
from dotenv import load_dotenv

sys.path.insert(0, r"C:\Users\mpetr\My Drive\Antigravity-AI Agents\Meta_App_Factory\Alpha_V2_Genesis")
load_dotenv(r"C:\Users\mpetr\My Drive\Antigravity-AI Agents\Meta_App_Factory\Resonance\.env")

from skills.n8n_architect.architect import N8NArchitect

a = N8NArchitect()

def build_socratic_bridge():
    wf = {
        "name": "Resonance: Socratic Bridge (Alpha Architect)",
        "active": True,
        "nodes": [
            {
                "parameters": {"path": "resonance-socratic-bridge", "responseMode": "lastNode", "options": {}},
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [0, 0]
            },
            {
                "parameters": {
                    "modelName": "models/gemini-2.5-flash",
                    "options": {}
                },
                "name": "Gemini_Deconstructor",
                "type": "@n8n/n8n-nodes-langchain.lmChatGoogleGemini",
                "typeVersion": 1,
                "position": [200, 0],
                "credentials": {
                    "googlePalmApi": {
                        "id": "X2DEkR3xrzOLRJXc",
                        "name": "Google Gemini(PaLM) Api account 4"
                    }
                }
            },
            {
                "parameters": {
                    "prompt": "Deconstruct the provided homework into Atomic Principles. Formulate a Bridge Question. Do not solve. Format as a Logic Map.",
                    "messages": {
                        "messageValues": [
                            {"message": "={{$json.body.homework}}"}
                        ]
                    }
                },
                "name": "Reasoning_Chain",
                "type": "@n8n/n8n-nodes-langchain.chainLlm",
                "typeVersion": 1,
                "position": [400, 0]
            }
        ],
        "connections": {
            "Webhook": {
                "main": [
                    [{"node": "Reasoning_Chain", "type": "main", "index": 0}]
                ]
            },
            "Gemini_Deconstructor": {
                "ai_languageModel": [
                    [{"node": "Reasoning_Chain", "type": "ai_languageModel", "index": 0}]
                ]
            }
        }
    }
    return wf

def build_aether_memory():
    wf = {
        "name": "Aether: Memory Synthesis & Breakthroughs",
        "active": True,
        "nodes": [
            {
                "parameters": {"path": "aether-memory-synthesis", "responseMode": "onReceived", "options": {}},
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [0, 0]
            },
            {
                "parameters": {
                    "modelName": "models/gemini-2.5-flash",
                    "options": {}
                },
                "name": "Gemini_Synthesizer",
                "type": "@n8n/n8n-nodes-langchain.lmChatGoogleGemini",
                "typeVersion": 1,
                "position": [200, 0],
                "credentials": {
                    "googlePalmApi": {
                        "id": "X2DEkR3xrzOLRJXc",
                        "name": "Google Gemini(PaLM) Api account 4"
                    }
                }
            },
            {
                "parameters": {
                    "prompt": "Evaluate the session. Find Cognitive Breakthroughs. Output plain text starting with [SYSTEM_V3_AETHER_BREAKTHROUGH].",
                    "messages": {
                        "messageValues": [
                            {"message": "={{$json.body.session_log}}"}
                        ]
                    }
                },
                "name": "Extract_Breakthroughs",
                "type": "@n8n/n8n-nodes-langchain.chainLlm",
                "typeVersion": 1,
                "position": [400, 0]
            },
            {
                "parameters": {
                    "command": "python -c \"import sys; with open('C:\\\\Users\\\\mpetr\\\\My Drive\\\\Antigravity-AI Agents\\\\MASTER_INDEX.md', 'a', encoding='utf-8') as f: f.write('\\n' + sys.argv[1]);\" \"{{$json.text}}\""
                },
                "name": "Log_to_MASTER_INDEX",
                "type": "n8n-nodes-base.executeCommand",
                "typeVersion": 1,
                "position": [600, 0]
            }
        ],
        "connections": {
            "Webhook": {
                "main": [
                    [{"node": "Extract_Breakthroughs", "type": "main", "index": 0}]
                ]
            },
            "Gemini_Synthesizer": {
                "ai_languageModel": [
                    [{"node": "Extract_Breakthroughs", "type": "ai_languageModel", "index": 0}]
                ]
            },
            "Extract_Breakthroughs": {
                "main": [
                    [{"node": "Log_to_MASTER_INDEX", "type": "main", "index": 0}]
                ]
            }
        }
    }
    return wf

def build_aether_streak():
    wf = {
        "name": "Aether: Streak Monitor & Gamification",
        "active": True,
        "nodes": [
            {
                "parameters": {
                    "rule": {
                        "interval": [
                            {"field": "cronExpression", "expression": "0 0 * * *"}
                        ]
                    }
                },
                "name": "Daily_Cron",
                "type": "n8n-nodes-base.cron",
                "typeVersion": 1,
                "position": [0, 0]
            },
            {
                "parameters": {
                    "command": "python -c \"import json; f=open('C:\\\\Users\\\\mpetr\\\\My Drive\\\\Antigravity-AI Agents\\\\Meta_App_Factory\\\\Resonance\\\\parent_config.json'); print(json.load(f).get('progress_log', [])); f.close()\""
                },
                "name": "Read_Insight_Engine",
                "type": "n8n-nodes-base.executeCommand",
                "typeVersion": 1,
                "position": [200, 0]
            },
             {
                "parameters": {
                    "modelName": "models/gemini-2.5-flash",
                    "options": {}
                },
                "name": "Gemini_Synthesizer",
                "type": "@n8n/n8n-nodes-langchain.lmChatGoogleGemini",
                "typeVersion": 1,
                "position": [400, 150],
                "credentials": {
                    "googlePalmApi": {
                        "id": "X2DEkR3xrzOLRJXc",
                        "name": "Google Gemini(PaLM) Api account 4"
                    }
                }
            },
            {
                "parameters": {
                    "prompt": "Read the JSON log. If the user was active for 3 straight days in focus-room, output a Personal Development Insight connecting their academic success to a known goal (e.g. tennis).",
                    "messages": {
                        "messageValues": [
                            {"message": "={{$json.stdout}}"}
                        ]
                    }
                },
                "name": "Analyze_Streaks",
                "type": "@n8n/n8n-nodes-langchain.chainLlm",
                "typeVersion": 1,
                "position": [400, 0]
            },
            {
                "parameters": {
                    "chatId": "notifications",
                    "text": "={{$json.text}}",
                    "additionalFields": {}
                },
                "name": "Send_Notification",
                "type": "n8n-nodes-base.slack",
                "typeVersion": 1,
                "position": [600, 0]
            }
        ],
        "connections": {
            "Daily_Cron": {
                "main": [
                    [{"node": "Read_Insight_Engine", "type": "main", "index": 0}]
                ]
            },
            "Read_Insight_Engine": {
                "main": [
                    [{"node": "Analyze_Streaks", "type": "main", "index": 0}]
                ]
            },
            "Gemini_Synthesizer": {
                "ai_languageModel": [
                    [{"node": "Analyze_Streaks", "type": "ai_languageModel", "index": 0}]
                ]
            },
            "Analyze_Streaks": {
                "main": [
                    [{"node": "Send_Notification", "type": "main", "index": 0}]
                ]
            }
        }
    }
    return wf

try:
    print("Deploying Socratic Bridge...")
    r1 = a.create_workflow(build_socratic_bridge())
    print("Socratic Bridge deployed! ID:", r1.get('id', 'Unknown'))
    if 'id' in r1: a.activate_workflow(r1['id'])

    print("Deploying Aether Memory Synthesis...")
    r2 = a.create_workflow(build_aether_memory())
    print("Aether Memory deployed! ID:", r2.get('id', 'Unknown'))
    if 'id' in r2: a.activate_workflow(r2['id'])

    print("Deploying Aether Streak Monitor...")
    r3 = a.create_workflow(build_aether_streak())
    print("Aether Streak Monitor deployed! ID:", r3.get('id', 'Unknown'))
    if 'id' in r3: a.activate_workflow(r3['id'])

    print("All architecture components deployed natively!")
except Exception as e:
    print("Deployment Error:", str(e))
