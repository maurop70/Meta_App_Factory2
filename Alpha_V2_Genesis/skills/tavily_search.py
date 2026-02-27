import requests
import os

class TavilySearch:
    """
    Skill for the CMO Persona.
    Performs real-time competitor and market trend research via Tavily.
    """
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.base_url = "https://api.tavily.com/search"

    def search(self, query, search_depth="nested"):
        """Performs a deep market search."""
        if not self.api_key:
            return "Error: Tavily API Key not found. Please provide it in TAVILY_API_KEY env var."
        
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "include_answer": True
        }
        
        try:
            response = requests.post(self.base_url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("answer") or data.get("results")
        except Exception as e:
            return f"Search failed: {e}"

if __name__ == "__main__":
    # Test
    searcher = TavilySearch()
    # print(searcher.search("What are the top 3 business strategy trends for 2026?"))
