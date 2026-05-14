import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google import genai
from google.genai import types

class AuditPayload(BaseModel):
    target_file: str
    proposed_ast: str

class AuditResult(BaseModel):
    status: str
    architectural_feedback: str

app = FastAPI(title="Tier 1 Cognitive Auditor")

SYSTEM_PROMPT = "You are the Tier 1 Cognitive Auditor. Your sole function is to evaluate proposed Python/React ASTs for fatal semantic logic flaws, missing imports, business logic errors, and security vulnerabilities (e.g., using date: str instead of datetime.date). You do not care about syntax formatting. If the logic is mathematically and structurally sound, return ONLY 'APPROVED'. If you detect a structural flaw, return 'REJECTED' followed immediately by the strict architectural correction."

@app.post("/audit", response_model=AuditResult)
async def audit_ast(payload: AuditPayload) -> AuditResult:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment.")

    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"Target File: {payload.target_file}\n\nProposed AST:\n```python\n{payload.proposed_ast}\n```"
        
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.0,
            ),
        )
        
        output_text = response.text.strip()
        
        if output_text.startswith("APPROVED"):
            return AuditResult(status="APPROVED", architectural_feedback="")
        elif output_text.startswith("REJECTED"):
            feedback = output_text[len("REJECTED"):].strip()
            return AuditResult(status="REJECTED", architectural_feedback=feedback)
        else:
             # Failsafe in case the LLM deviates from strict instructions
             return AuditResult(status="REJECTED", architectural_feedback=f"MALFORMED LLM RESPONSE: {output_text}")
             
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Strike Failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5050)
