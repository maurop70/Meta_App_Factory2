# Firecrawl Skill

## Purpose
Firecrawl extracts clean, LLM-ready markdown from any public URL.
Use for CIO market research, CMO competitor analysis, and any web
intelligence gathering task.

## API Details
- Endpoint: https://api.firecrawl.dev/v1/scrape
- Auth: Bearer token from FIRECRAWL_API_KEY in .env
- Method: POST
- Free tier: 500 credits/month (1 credit per page scrape)

## Request Format
```python
headers = {
    "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
    "Content-Type": "application/json"
}
payload = {
    "url": target_url,
    "formats": ["markdown"],
    "onlyMainContent": True
}
response = await httpx.AsyncClient().post(
    "https://api.firecrawl.dev/v1/scrape",
    headers=headers,
    json=payload,
    timeout=30.0
)
```

## Response Format
```json
{
  "success": true,
  "data": {
    "markdown": "# Page Title\n\nExtracted content...",
    "metadata": {
      "title": "Page Title",
      "description": "Meta description",
      "url": "https://..."
    }
  }
}
```

## Cascade Strategy
Always implement in this order:
1. Firecrawl API (primary)
2. DuckDuckGo search via duckduckgo-search package (secondary)
3. Direct httpx GET raw text (tertiary)
4. Return structured error (final fallback)

## Rate Limit Handling
- Free tier: 500 credits/month
- On 429 response: immediately fall through to DuckDuckGo
- On any non-200: fall through to DuckDuckGo
- Log all fallbacks with [CRAWLER FALLBACK] prefix

## DuckDuckGo Fallback
```python
from duckduckgo_search import DDGS
with DDGS() as ddgs:
    results = list(ddgs.text(query, max_results=5))
return "\n\n".join([
    f"## {r['title']}\n{r['body']}\nSource: {r['href']}"
    for r in results
])
```

## Install Requirements
```bash
pip install firecrawl-py duckduckgo-search --break-system-packages
```

## Error Codes
- 401: Invalid API key — check FIRECRAWL_API_KEY in .env
- 402: Credits exhausted — fall through to DuckDuckGo
- 429: Rate limited — fall through to DuckDuckGo
- 500: Firecrawl server error — fall through to DuckDuckGo
