# specific factory configuration for this sub-app
FACTORY_CONFIG = {
    "module_name": "Claude_N8N_Automation_Bridge",
    "version": "1.0.0",
    "type": "integration_module",
    "base_path": "Meta_App_Factory/Claude_N8N_Automation_Bridge",
    "components": [
        "supervisor.py",
        "n8n_workflow_schema.json"
    ],
    "dependencies": {
        "utils": ["claude_relay.py", "debugger.py"],
        "services": ["CLAUDE_CODE_SERVICE", "DEBUG_SERVICE_SENTRY"]
    },
    "env_vars": [
        "SENTRY_DSN",
        "SENTRY_AUTH_TOKEN"
    ]
}

def get_config():
    return FACTORY_CONFIG
