import os
from pathlib import Path

search_terms = ["/api/cio/seed", "/api/warroom/seed", "cio/seed", "warroom/seed"]
root_dir = Path(r"c:\Dev\Antigravity_AI_Agents\Meta_App_Factory")

found = []
for p in root_dir.rglob("*.py"):
    if ".Gemini_state" in p.parts or ".agents" in p.parts or ".system_core" in p.parts:
        continue
    try:
        content = p.read_text(encoding="utf-8", errors="ignore")
        for term in search_terms:
            if term in content:
                found.append((p, term))
    except Exception as e:
        pass

print("=== Search Results ===")
for p, term in found:
    print(f"Found '{term}' in {p}")
