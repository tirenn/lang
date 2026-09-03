from typing import Dict, Any, List
from src.state import AgentState, ResearchItem
from src.tools.search import search_web

def researcher_node(state: AgentState) -> Dict[str, Any]:
    """Node: Executes filtered search queries and gathers verified source evidence."""
    queries = state.get("plan", [])
    new_findings: List[ResearchItem] = []
    
    seen_urls = set()
    for existing in state.get("research_data", []):
        seen_urls.add(existing.get("source_url", ""))

    for query in queries:
        results = search_web(query, max_results=3)
        for item in results:
            url = item.get("source_url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                new_findings.append(item)
                
    return {"research_data": new_findings}
