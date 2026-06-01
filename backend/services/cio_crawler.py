import httpx
import os
import logging
from typing import Union, Dict, Any

logger = logging.getLogger("CIOCrawlerService")

class CIOCrawlerService:
    """
    Crawler service to extract markdown from target URLs.
    Implements 502 Gateway Unreachable fallback on network or timeout failures.
    Supports localhost routing fallback for local and E2E testing environments.
    """
    def __init__(self):
        self.api_key = os.getenv("FIRECRAWL_API_KEY", "")
        self.api_url = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev/v1/scrape")

    async def scrape(self, target_url: str) -> Union[str, Dict[str, Any]]:
        """
        Scrapes a target URL and returns raw text/markdown or the 502 Error envelope.
        """
        # Determine if target is local to prevent cloud proxy loop failure
        is_local = any(host in target_url for host in ["127.0.0.1", "localhost", "localhost:", "127.0.0.1:"])
        
        if is_local:
            logger.info(f"Local target URL detected: {target_url}. Commencing direct HTTPX extraction.")
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(target_url)
                    if resp.status_code == 200:
                        return f"Local source content:\n\n{resp.text}"
                    else:
                        logger.error(f"Local HTTPX fetch failed with status {resp.status_code}")
                        return {
                            "error": "Gateway Unreachable",
                            "detail": "CIO Crawler API offline or timed out."
                        }
            except (httpx.RequestError, httpx.TimeoutException) as e:
                logger.error(f"Local HTTPX fetch exception: {e}")
                return {
                    "error": "Gateway Unreachable",
                    "detail": "CIO Crawler API offline or timed out."
                }

        # Public URL: Route through Firecrawl API
        logger.info(f"Public target URL detected. Route via Firecrawl: {self.api_url}")
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        payload = {
            "url": target_url,
            "formats": ["markdown"]
        }
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    markdown = ""
                    if "data" in data and isinstance(data["data"], dict):
                        markdown = data["data"].get("markdown", "") or data["data"].get("content", "")
                    elif isinstance(data, dict):
                        markdown = data.get("markdown", "") or data.get("content", "")
                    
                    if markdown:
                        return markdown
                    else:
                        # Direct HTTPX extraction as fallback
                        direct_resp = await client.get(target_url)
                        return direct_resp.text
                else:
                    logger.warning(f"Firecrawl returned {response.status_code}. Falling back to direct HTTPX fetch.")
                    direct_resp = await client.get(target_url)
                    if direct_resp.status_code == 200:
                        return direct_resp.text
                    else:
                        return {
                            "error": "Gateway Unreachable",
                            "detail": "CIO Crawler API offline or timed out."
                        }
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.error(f"Firecrawl/HTTPX request failure: {e}")
            return {
                "error": "Gateway Unreachable",
                "detail": "CIO Crawler API offline or timed out."
            }
