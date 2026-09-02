from typing import Dict, Any, List
from src.state import AgentState, ResearchItem
from src.tools.search import search_web

def researcher_node(state: AgentState) -> Dict[str, Any]:
    """Node: Executes search queries in the plan and accumulates findings."""
    queries = state.get("plan", [])
    new_findings: List[ResearchItem] = []
    
    for query in queries:
        results = search_web(query, max_results=3)
        new_findings.extend(results)
        
    return {"research_data": new_findings}
