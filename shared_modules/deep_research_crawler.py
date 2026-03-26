"""
deep_research_crawler.py — Layer 2: Deep Research Crawler
==========================================================
Shared module for all Antigravity agents.

Performs targeted web research using aiohttp to fetch and extract
structured data from public sources. Feeds pre-fetched intelligence
into Gemini prompts to ground AI responses in real facts.

Usage:
    from deep_research_crawler import DeepResearchCrawler
    crawler = DeepResearchCrawler()
    intel = await crawler.research("frozen chocolate covered fruit market")
"""

import re
import json
import time
import asyncio
import logging
from typing import Optional
from html.parser import HTMLParser

import aiohttp

logger = logging.getLogger("DeepResearch")


class _TextExtractor(HTMLParser):
    """Extract visible text from HTML, stripping tags."""
    def __init__(self):
        super().__init__()
        self._text = []
        self._skip_tags = {"script", "style", "noscript", "meta", "link", "head"}
        self._in_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._in_skip += 1

    def handle_endtag(self, tag):
        if tag in self._skip_tags and self._in_skip > 0:
            self._in_skip -= 1

    def handle_data(self, data):
        if self._in_skip == 0:
            text = data.strip()
            if text:
                self._text.append(text)

    def get_text(self):
        return " ".join(self._text)


def html_to_text(html: str, max_chars: int = 8000) -> str:
    """Convert HTML to plain text, truncated to max_chars."""
    extractor = _TextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        pass
    text = extractor.get_text()
    # Clean excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_chars]


class DeepResearchCrawler:
    """
    Multi-source web research engine. Fetches real data from
    public sources and returns structured intelligence.
    """

    # Common headers to avoid blocks
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/json,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    # Research source templates — {query} will be replaced
    SOURCES = {
        "google_news": {
            "url": "https://news.google.com/search?q={query}&hl=en-US&gl=US&ceid=US:en",
            "type": "news",
            "description": "Google News results",
        },
        "wikipedia": {
            "url": "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&format=json&srlimit=5",
            "type": "api_json",
            "description": "Wikipedia article summaries",
        },
        "reddit_search": {
            "url": "https://www.reddit.com/search.json?q={query}&sort=relevance&limit=5",
            "type": "api_json",
            "description": "Reddit discussions",
        },
    }

    def __init__(self, timeout: int = 15, max_sources: int = 10):
        self.timeout = timeout
        self.max_sources = max_sources

    async def _fetch_url(self, session: aiohttp.ClientSession,
                          url: str, source_type: str = "html") -> dict:
        """Fetch a single URL and extract content."""
        try:
            async with session.get(
                url, headers=self.HEADERS,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                allow_redirects=True,
                ssl=False,
            ) as r:
                if r.status != 200:
                    return {"url": url, "status": r.status, "content": "", "error": f"HTTP {r.status}"}

                content_type = r.headers.get("content-type", "")
                raw = await r.text(errors="replace")

                if "json" in content_type or source_type == "api_json":
                    try:
                        data = json.loads(raw)
                        return {"url": url, "status": 200, "content": json.dumps(data, indent=0)[:8000], "type": "json"}
                    except json.JSONDecodeError:
                        pass

                text = html_to_text(raw)
                return {"url": url, "status": 200, "content": text, "type": "text"}

        except asyncio.TimeoutError:
            return {"url": url, "status": 0, "content": "", "error": "Timeout"}
        except Exception as e:
            return {"url": url, "status": 0, "content": "", "error": str(e)[:100]}

    async def search_wikipedia(self, query: str, session: aiohttp.ClientSession) -> list[dict]:
        """Search Wikipedia and get article summaries."""
        results = []
        try:
            search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&format=json&srlimit=3"
            async with session.get(search_url, headers=self.HEADERS,
                                    timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    for item in data.get("query", {}).get("search", []):
                        title = item.get("title", "")
                        snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
                        results.append({
                            "source": "Wikipedia",
                            "title": title,
                            "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                            "snippet": snippet,
                        })
        except Exception as e:
            logger.warning(f"Wikipedia search failed: {e}")
        return results

    async def search_reddit(self, query: str, session: aiohttp.ClientSession) -> list[dict]:
        """Search Reddit for relevant discussions."""
        results = []
        try:
            search_url = f"https://www.reddit.com/search.json?q={query}&sort=relevance&limit=5&t=year"
            headers = {**self.HEADERS, "User-Agent": "PhantomResearch/1.0"}
            async with session.get(search_url, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    for post in data.get("data", {}).get("children", []):
                        d = post.get("data", {})
                        results.append({
                            "source": "Reddit",
                            "title": d.get("title", ""),
                            "url": f"https://reddit.com{d.get('permalink', '')}",
                            "snippet": d.get("selftext", "")[:300],
                            "score": d.get("score", 0),
                            "subreddit": d.get("subreddit", ""),
                        })
        except Exception as e:
            logger.warning(f"Reddit search failed: {e}")
        return results

    async def fetch_custom_urls(self, urls: list[str],
                                 session: aiohttp.ClientSession) -> list[dict]:
        """Fetch and extract content from specific URLs."""
        tasks = [self._fetch_url(session, url) for url in urls[:self.max_sources]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict) and r.get("content")]

    async def research(self, query: str, custom_urls: list[str] = None) -> dict:
        """
        Run a full multi-source research pipeline.
        Returns structured intelligence ready for injection into AI prompts.
        """
        start = time.time()
        logger.info(f"Deep Research: '{query[:60]}...'")

        all_findings = []
        source_count = 0

        async with aiohttp.ClientSession() as session:
            # Run all sources in parallel
            tasks = [
                self.search_wikipedia(query, session),
                self.search_reddit(query, session),
            ]

            if custom_urls:
                tasks.append(self.fetch_custom_urls(custom_urls, session))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process Wikipedia results
            if isinstance(results[0], list):
                all_findings.extend(results[0])
                source_count += len(results[0])

            # Process Reddit results
            if isinstance(results[1], list):
                all_findings.extend(results[1])
                source_count += len(results[1])

            # Process custom URLs
            if custom_urls and len(results) > 2 and isinstance(results[2], list):
                for r in results[2]:
                    all_findings.append({
                        "source": "Custom URL",
                        "url": r.get("url", ""),
                        "snippet": r.get("content", "")[:500],
                    })
                    source_count += 1

        elapsed = time.time() - start

        # Compile findings into a prompt-injectable intelligence brief
        brief = self._compile_brief(query, all_findings)

        logger.info(f"Deep Research complete: {source_count} sources, {elapsed:.1f}s")

        return {
            "query": query,
            "source_count": source_count,
            "duration_seconds": round(elapsed, 1),
            "findings": all_findings,
            "intelligence_brief": brief,
        }

    def _compile_brief(self, query: str, findings: list[dict]) -> str:
        """Compile all findings into a text brief for prompt injection."""
        if not findings:
            return f"No external research data found for: {query}"

        sections = []
        sections.append(f"=== DEEP RESEARCH INTELLIGENCE BRIEF ===")
        sections.append(f"Query: {query}")
        sections.append(f"Sources analyzed: {len(findings)}")
        sections.append("")

        for i, f in enumerate(findings[:15], 1):
            source = f.get("source", "Unknown")
            title = f.get("title", "")
            snippet = f.get("snippet", "")[:400]
            url = f.get("url", "")
            sections.append(f"[{i}] ({source}) {title}")
            if snippet:
                sections.append(f"    {snippet}")
            if url:
                sections.append(f"    URL: {url}")
            sections.append("")

        sections.append("=== END INTELLIGENCE BRIEF ===")
        return "\n".join(sections)


# ═══════════════════════════════════════════════════════════
#  CONVENIENCE FUNCTION
# ═══════════════════════════════════════════════════════════

async def deep_research(query: str, custom_urls: list[str] = None) -> dict:
    """One-call convenience function for deep research."""
    crawler = DeepResearchCrawler()
    return await crawler.research(query, custom_urls)
