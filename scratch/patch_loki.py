import re

file_path = 'Alpha_V2_Genesis/skills/loki/loki.py'
with open(file_path, 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Remove fetch_external_commentary entirely
code = re.sub(r'    def fetch_external_commentary\(self\):.*?(?=    # ══════════════════════════════════════════════════════════════════\n    # Priority 6)', '', code, flags=re.DOTALL)

# 2. Rename the fallback method
code = code.replace('def _gemini_direct_fallback(self, snapshot: dict) -> dict:', 'def _generate_native_intelligence(self, snapshot: dict) -> dict:')

# 3. Fix the internal requests within _generate_native_intelligence
code = code.replace('Priority 6: Calling Gemini 2.0 Flash directly (N8N bypass)...', 'Generating Native Intelligence via Gemini 2.5 Flash...')

old_req = """            _v3_status = healed_post(url, payload)

            resp = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()"""

new_req = """            import requests
            resp = requests.post(url, json=payload)"""
code = code.replace(old_req, new_req)

# 4. Fix where the method was called in run_strategy
code = code.replace('n8n_result = self.fetch_external_commentary()', 'n8n_result = self._generate_native_intelligence(snapshot)')

# 5. I/O Standardization for intelligence_source
code = code.replace('"intelligence_source": "NATIVE" if sent_result.get(\'cache_status\') == \'FRESH\' else "CACHED",', '"intelligence_source": "NATIVE",')

# 6. Change n8n_pusher import and call
# Wait, let's remove n8n_pusher import entirely.
code = code.replace('from skills.n8n_pusher import push_decision\n', '')
code = re.sub(r'        # 5\. Push to n8n.*?try:.*?push_decision\(final_decision\).*?except Exception as e:.*?logger\.error\(f"Failed to push decision to N8N: \{e\}"\)\n', '', code, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(code)

print("Patch applied to loki.py")
