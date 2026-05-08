import re

with open("maintenance_backend.py", "r", encoding="utf-8") as f:
    content = f.read()

# Pattern explanation:
# Match @app.get("/api/ and replace with @app.get("/
# The \1 captures `@app.get("` part
new_content = re.sub(r'(@app\.(get|post|put|patch|delete)\(\")\/api\/', r'\1/', content)

with open("maintenance_backend.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Stripped all /api/ prefixes from FastAPI router decorators.")
