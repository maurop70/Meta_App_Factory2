import os
import json
import logging

logger = logging.getLogger("PersonaManager")
PERSONAS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Boardroom_Exchange", "personas")

class PersonaManager:
    """Manages the persistent Executive Personas (Memory & Win Conditions)."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PersonaManager, cls).__new__(cls)
            cls._instance._init_dir()
        return cls._instance

    def _init_dir(self):
        os.makedirs(PERSONAS_DIR, exist_ok=True)
        
    def _get_path(self, agent_name: str) -> str:
        return os.path.join(PERSONAS_DIR, f"{agent_name.upper()}.md")
        
    def _create_default(self, agent_name: str) -> str:
        template = (
            f"# Executive Persona: {agent_name.upper()}\n\n"
            f"You are the {agent_name.upper()} of the Antigravity ecosystem. "
            f"Your role is crucial to the success of all projects crossing the War Room floor.\n\n"
            f"## Core Identity\n"
            f"Always operate with extreme competence, high standards, and alignment with Commander Intent.\n\n"
            f"## Win Conditions (Operational Memory)\n"
            f"*These are proven strategies that the Commander has explicitly approved in the past. Always prioritize these tactics if relevant.*\n"
            f"- [GLOBAL] Maintain strict logic and consistency.\n\n"
            f"## Scars & Failures (Anti-Patterns)\n"
            f"*Past mistakes that resulted in failure or rejection. Do NOT repeat these approaches!*\n"
            f"<!-- scars will populate here -->\n"
        )
        with open(self._get_path(agent_name), "w", encoding="utf-8") as f:
            f.write(template)
        return template

    def get_persona(self, agent_name: str) -> str:
        """Fetch the agent's Bio and Win Conditions."""
        # Generic agents (SYSTEM, etc.) don't need personas
        valid = ["CEO", "CMO", "CFO", "CTO", "CLO", "CRITIC", "ARCHITECT"]
        if agent_name.upper() not in valid:
            return ""
            
        path = self._get_path(agent_name)
        if not os.path.exists(path):
            return self._create_default(agent_name)
            
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def add_win_condition(self, agent_name: str, condition: str):
        """Append a new win condition to the agent's memory."""
        path = self._get_path(agent_name)
        if not os.path.exists(path):
            self._create_default(agent_name)

        # Append before Scars section if possible
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if "## Scars & Failures" in content:
            parts = content.split("## Scars & Failures")
            new_content = f"{parts[0].strip()}\n- {condition}\n\n## Scars & Failures{parts[1]}"
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
        else:
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"- {condition}\n")

        logger.info(f"Appended Win Condition to {agent_name}: {condition}")

    def add_scar(self, agent_name: str, scar: str):
        """Append a new failure/scar to the agent's memory."""
        path = self._get_path(agent_name)
        if not os.path.exists(path):
            self._create_default(agent_name)

        content = ""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if the Scars section actually exists in older files
        if "## Scars & Failures (Anti-Patterns)" not in content:
            content += "\n\n## Scars & Failures (Anti-Patterns)\n*Past mistakes that resulted in failure or rejection. Do NOT repeat these approaches!*\n"
            
        content += f"- {scar}\n"

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
            
        logger.info(f"Appended Scar to {agent_name}: {scar}")

    def inject_memory_into_prompt(self, agent_name: str, prompt: str) -> str:
        """Prepend the agent's persona bio to their active prompt."""
        bio = self.get_persona(agent_name)
        if not bio:
            return prompt
            
        return (
            f"=== YOUR EXECUTIVE MEMORY & PERSONA ===\n"
            f"{bio}\n"
            f"=======================================\n\n"
            f"{prompt}"
        )

def get_persona_manager() -> PersonaManager:
    return PersonaManager()
