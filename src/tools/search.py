from typing import List, Dict, Any
from duckduckgo_search import DDGS
from src.state import ResearchItem

def search_web(query: str, max_results: int = 3) -> List[ResearchItem]:
    """
    Performs web search using DuckDuckGo and formats the results into structured ResearchItems.
    """
    items: List[ResearchItem] = []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            for res in results:
                items.append({
                    "query": query,
                    "title": res.get("title", "No Title"),
                    "source_url": res.get("href", ""),
                    "snippet": res.get("body", "")
                })
    except Exception as e:
        # Graceful fallback in case of connection or rate limit issues
        items.append({
            "query": query,
            "title": f"Search fallback for: {query}",
            "source_url": "https://duckduckgo.com",
            "snippet": f"Unable to fetch live web results due to: {str(e)}. Proceeding with base knowledge."
        })
    return items
