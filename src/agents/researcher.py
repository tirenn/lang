"""
Researcher Agent: Evidence & Digital Source Investigator (SOLID).

Adheres to:
- SRP: Only responsible for executing search queries and deduplicating findings.
- DIP: Injected with SearchToolInterface rather than directly importing or coupling to DDGS.
- LSP: Substitutable BaseAgent implementation.
"""

from typing import Dict, Any, List, Optional
from src.state import AgentState, ResearchItem
from src.agents.base import BaseAgent, SearchToolInterface
from src.tools.search import default_search_service


class ResearcherAgent(BaseAgent):
    """
    Researcher Agent conforming to BaseAgent interface.
    Accepts any search service conforming to SearchToolInterface (DIP).
    """

    def __init__(self, search_service: Optional[SearchToolInterface] = None):
        self.search_service = search_service or default_search_service

    @property
    def name(self) -> str:
        return "researcher"

    def execute(self, state: AgentState) -> Dict[str, Any]:
        queries = state.get("plan", [])
        new_findings: List[ResearchItem] = []

        # Deduplicate across past iterations
        seen_urls = {
            item.get("source_url", "")
            for item in state.get("research_data", [])
            if item.get("source_url")
        }

        for query in queries:
            results = self.search_service.search(query, max_results=3)
            for item in results:
                url = item.get("source_url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    new_findings.append(item)

        return {"research_data": new_findings}


# Singleton and backward-compatible functional node
default_researcher = ResearcherAgent()

def researcher_node(state: AgentState) -> Dict[str, Any]:
    return default_researcher.execute(state)
