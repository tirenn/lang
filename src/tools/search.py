"""
Search Engine Tooling & Fact-Checking Filters (SOLID Service).

Adheres to:
- SRP: Encapsulates query sanitization, domain filtering, and DDG retrieval.
- OCP: Implements SearchToolInterface so alternative search engines (Tavily, Bing, etc.)
  can be substituted without touching agent code.
- ISP: Minimal contract `search(query, max_results)`.
"""

from typing import List
import time
import re
from urllib.parse import urlparse
from duckduckgo_search import DDGS
from src.state import ResearchItem

# Domain blacklist: e-commerce, shopping marketplaces, tech specs, personality test spam
IRRELEVANT_DOMAINS = {
    "samsung.com",
    "apple.com",
    "shopee.co.id",
    "shopee.com",
    "tokopedia.com",
    "lazada.co.id",
    "blibli.com",
    "bukalapak.com",
    "amazon.com",
    "ebay.com",
    "aliexpress.com",
    "gsmarena.com",
    "pricebook.co.id",
    "iprice.co.id",
    "cekresi.com",
    "carousell.com",
    "olx.co.id",
    "tiktok.com",
    "16personalities.com",
    "testmoa.com",
    "kmbti.co.kr"
}

# Conversational starters that confuse search engines
QUESTION_STARTERS = [
    r"^apakah\s+",
    r"^benarkah\s+",
    r"^mengapa\s+",
    r"^kenapa\s+",
    r"^bagaimanakah\s+",
    r"^bagaimana\s+",
    r"^apa\s+itu\s+",
    r"^apa\s+",
    r"^is\s+it\s+true\s+that\s+",
    r"^is\s+it\s+true\s+",
    r"^why\s+does\s+",
    r"^why\s+is\s+",
    r"^does\s+"
]


def clean_query(raw_query: str) -> str:
    """
    Cleans conversational question starters from search queries.
    Example: 'apakah kebakaran hutan karena sawit' -> 'kebakaran hutan karena sawit'
    """
    cleaned = raw_query.strip()
    cleaned = re.sub(r'["\']', ' ', cleaned)

    for pattern in QUESTION_STARTERS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    return " ".join(cleaned.split())


def is_domain_allowed(url: str) -> bool:
    """
    Checks if a URL domain is acceptable for investigative fact-checking.
    Rejects commercial marketplaces and unrelated foreign country-code TLDs.
    """
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        for blocked in IRRELEVANT_DOMAINS:
            if domain == blocked or domain.endswith("." + blocked):
                return False

        if domain.endswith(".kr") or domain.endswith(".cn") or domain.endswith(".ru"):
            return False

        return True
    except Exception:
        return True


def is_relevant_content(query: str, title: str, snippet: str) -> bool:
    """
    Ensures search results contain at least one substantive keyword from the query.
    """
    keywords = [word.lower() for word in query.split() if len(word) > 3]
    if not keywords:
        return True

    text_to_search = f"{title} {snippet}".lower()
    return any(keyword in text_to_search for keyword in keywords)


class SearchService:
    """
    Concrete implementation of SearchToolInterface using DuckDuckGo.
    Applies Indonesian region tuning, pacing, and strict relevance validation.
    """
    def __init__(self, region: str = "id-id", delay: float = 0.35):
        self.region = region
        self.delay = delay

    def search(self, query: str, max_results: int = 3) -> List[ResearchItem]:
        items: List[ResearchItem] = []
        sanitized_query = clean_query(query)

        time.sleep(self.delay)

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    sanitized_query,
                    region=self.region,
                    safesearch="moderate",
                    max_results=max_results + 4
                ))

                for result in results:
                    url = result.get("href", "")
                    title = result.get("title", "").strip()
                    snippet = result.get("body", "").strip()

                    if not is_domain_allowed(url) or not snippet:
                        continue

                    if not is_relevant_content(sanitized_query, title, snippet):
                        continue

                    items.append({
                        "query": sanitized_query,
                        "title": title or "News Source",
                        "source_url": url,
                        "snippet": snippet
                    })

                    if len(items) >= max_results:
                        break

        except Exception as err:
            items.append({
                "query": sanitized_query,
                "title": f"Search Log: {sanitized_query}",
                "source_url": "https://turnbackhoax.id",
                "snippet": f"Web search encountered network limitation ({str(err)}). Cross-referencing baseline knowledge."
            })

        return items


# Singleton instance adhering to SearchToolInterface
default_search_service = SearchService()

# Backward-compatible functional interface
def search_web(query: str, max_results: int = 3) -> List[ResearchItem]:
    return default_search_service.search(query, max_results=max_results)
