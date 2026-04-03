import sqlite3
import json

db_path = r"c:\Users\mpetr\My Drive\Antigravity-AI Agents\Meta_App_Factory\CMO_Agent\backend\marketing_memory.db"
db = sqlite3.connect(db_path)

res = {
    "image_url": "/generated/brand_brand_board_5d40de07.png",
    "description": "Here's a brand board for 'Antigravity Workspace' designed with a minimalist and premium aesthetic, reflecting the brand's personality and positioning.",
    "mockup_type": "brand_board",
    "brand_name": "Antigravity Workspace",
    "session_active": True
}

db.execute(
    "INSERT INTO analyses (module, project_name, input_summary, result_json, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
    ("brand_visual", "AntigravityWorkspace_Q3", "brand_board", json.dumps(res))
)
db.commit()
print("Successfully inserted visual into marketing_memory.db")
