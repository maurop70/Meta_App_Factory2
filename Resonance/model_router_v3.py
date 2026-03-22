import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# The Model Router ensures Fast Chat uses Gemini, while Deep Calculations use o3/Claude

class IntelligentModelRouter:
    def __init__(self):
        self.fast_model = "gemini-2.5-flash"
        self.deep_model = "o3-mini" # or claude-3-7-sonnet
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    def determine_optimal_model(self, task_type: str, instruction: str) -> str:
        """
        Dynamically analyzes the payload and routes to the cheapest, fastest, or smartest model.
        """
        heavy_tasks = ["Deconstruction", "Mathematical Logic", "Alpha Architect", "Deep Homework Analysis"]
        
        if any(task in task_type for task in heavy_tasks):
            print(f"[ROUTER] Complex task detected: {task_type}. Routing to Deep Reasoning Model ({self.deep_model})")
            return self.deep_model
        
        print(f"[ROUTER] Standard conversational task. Routing to Fast Inference Model ({self.fast_model})")
        return self.fast_model
        
    def execute(self, task_type: str, instruction: str, context: dict):
        model = self.determine_optimal_model(task_type, instruction)
        # Mock execution environment for Phase 1 Scaffolding
        return {
            "status": "success",
            "routed_via": model,
            "data": f"Executed '{task_type}' natively on {model}"
        }

if __name__ == "__main__":
    router = IntelligentModelRouter()
    print(router.execute("Deconstruction", "Solve a partial differential equation", {}))
    print(router.execute("Chat", "Tell Leo hello!", {}))
