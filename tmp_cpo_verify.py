import os, json, requests
from dotenv import load_dotenv
load_dotenv('.env')

prompt_cpo = """You are the acting Chief Product Officer (CPO) for Project Aether. The CTO has just proposed an Active-Active Redis architecture. We are in a 'competitor_blitz' scenario against a $10M funded rival. Generate a rapid MoSCoW matrix prioritizing features that create an immediate commercial moat and minimize UX friction for cross-chain swaps. Ignore deep tech; focus on Commerciability."""

res = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={os.environ["GEMINI_API_KEY"]}', json={'contents': [{'role': 'user', 'parts': [{'text': prompt_cpo}]}]})
cpo_text = res.json()['candidates'][0]['content']['parts'][0]['text']
with open('sys_proxy_output.txt', 'w', encoding='utf-8') as f:
    f.write('=== CPO MUST-HAVES ===\n')
    f.write(cpo_text)

prompt_critic = f"""You are the Chief Critic and quality arbiter in a boardroom war room. You are PHASE 3. You ONLY evaluate the COMPLETED Business Plan produced by Phase 1 and Phase 2. Respond in VALID JSON ONLY (no markdown fences).
Required JSON schema:
{{
  "agreement_level": 6.5,
  "verdict": "AGREE or OBJECT or ABSTAIN",
  "cost_challenge": "your specific challenge",
  "revenue_challenge": "your specific challenge",
  "objections": ["objection 1"],
  "evidence_demanded": "what data you need",
  "analysis": "your 3-5 sentence critical assessment"
}}
Review the CPOs MoSCoW matrix: {cpo_text}
Finalize the Gate Score and write the Vision Document."""

res2 = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={os.environ["GEMINI_API_KEY"]}', json={'contents': [{'role': 'user', 'parts': [{'text': prompt_critic}]}]})
with open('sys_proxy_output.txt', 'a', encoding='utf-8') as f:
    f.write('\n\n=== CRITIC SCORE ===\n')
    f.write(res2.json()['candidates'][0]['content']['parts'][0]['text'])
