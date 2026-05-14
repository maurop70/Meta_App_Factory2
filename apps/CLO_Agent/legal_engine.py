import os
import json
import yaml
import aiofiles
import asyncio

class LegalEngine:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config = {}

    @classmethod
    async def create(cls, config_path="config.json"):
        instance = cls(config_path)
        instance.config = await instance._load_config()
        return instance

    async def _load_config(self):
        if not os.path.exists(self.config_path):
            return {"template_dir": "templates", "output_dir": "output"}
        async with aiofiles.open(self.config_path, 'r') as f:
            content = await f.read()
            if self.config_path.endswith('.json'):
                return json.loads(content)
            elif self.config_path.endswith(('.yaml', '.yml')):
                return yaml.safe_load(content)
            else:
                raise ValueError(f"Unsupported config type")

    async def save_config(self):
        async with aiofiles.open(self.config_path, 'w') as f:
            if self.config_path.endswith('.json'):
                await f.write(json.dumps(self.config, indent=4))
            elif self.config_path.endswith(('.yaml', '.yml')):
                await f.write(yaml.safe_dump(self.config))

    async def get_template(self, template_name: str) -> str:
        template_path = os.path.join(self.config['template_dir'], f"{template_name}.txt")
        async with aiofiles.open(template_path, 'r') as f:
            return await f.read()

    async def generate_document(self, template_name: str, data: dict, output_filename: str) -> str:
        template_content = await self.get_template(template_name)
        document_content = template_content.format(**data)
        output_dir = self.config['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)
        async with aiofiles.open(output_path, 'w') as f:
            await f.write(document_content)
        return output_path

    async def log_event(self, event_message: str):
        output_dir = self.config['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        log_file_path = os.path.join(output_dir, "engine_log.txt")
        async with aiofiles.open(log_file_path, 'a') as f:
            await f.write(f"{event_message}\n")
