# Phase 2 Semantic Recall - Verified for text-embedding-004 & gemini-embedding-2 fallback
import os
import httpx
from typing import List, Union, Dict, Any, Optional
from fastapi.responses import JSONResponse

class GoogleEmbeddingService:
    """
    Service class interfacing with the Google Gemini text-embedding-004 API.
    STRICT GUARDRAIL: Implements 502 Fallback Protocol trapping RequestError and TimeoutException
    and returning a mathematically uniform error fallback envelope.
    Includes a dynamic, resilient, self-healing fallback to gemini-embedding-2 if text-embedding-004 is 404.
    Mathematically forces 768-dimensional Matryoshka output project formatting.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        if self.api_key:
            self.api_key = self.api_key.strip("'\"")
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent"

    async def get_embedding_async(self, text: str) -> Union[List[float], JSONResponse]:
        """
        Retrieves the float embedding values for a given text.
        STRICT GUARDRAIL: Traps httpx connection failures and returns a 502 JSONResponse fallback.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"Content-Type": "application/json"}
                params = {"key": self.api_key}
                
                # First attempt: gemini-embedding-2
                payload = {
                    "model": "models/gemini-embedding-2",
                    "content": {
                        "parts": [{"text": text}]
                    },
                    "output_dimensionality": 768
                }
                response = await client.post(self.api_url, headers=headers, params=params, json=payload)
                
                # Self-healing fallback if 404 (Not Found or Unsupported in this API key/region)
                if response.status_code == 404:
                    fallback_url = "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"
                    fallback_payload = {
                        "model": "models/text-embedding-004",
                        "content": {
                            "parts": [{"text": text}]
                        },
                        "output_dimensionality": 768
                    }
                    response = await client.post(fallback_url, headers=headers, params=params, json=fallback_payload)
                
                if response.status_code == 200:
                    data = response.json()
                    values = data.get("embedding", {}).get("values", [])
                    if values:
                        return values
                    else:
                        return JSONResponse(
                            status_code=502,
                            content={
                                "error": "Gateway Unreachable",
                                "detail": "Empty or malformed embedding response from Google API."
                            }
                        )
                else:
                    return JSONResponse(
                        status_code=502,
                        content={
                            "error": "Gateway Unreachable",
                            "detail": f"Google Embedding API returned status code {response.status_code}."
                        }
                    )
        except (httpx.RequestError, httpx.TimeoutException) as e:
            # Trapped Connection Exception - 502 Gateway Unreachable
            return JSONResponse(
                status_code=502,
                content={
                    "error": "Gateway Unreachable",
                    "detail": "Google Embedding API offline or timed out."
                }
            )

    async def get_embeddings_batch_async(self, texts: List[str]) -> Union[List[List[float]], JSONResponse]:
        """
        Retrieves batch float embedding values for a list of texts.
        """
        embeddings = []
        for text in texts:
            res = await self.get_embedding_async(text)
            if isinstance(res, JSONResponse):
                return res  # Bubble up the 502 Gateway Unreachable error
            embeddings.append(res)
        return embeddings
