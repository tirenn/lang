from typing import TypedDict, List, Dict, Any, Optional
import operator
from typing_extensions import Annotated

class ResearchItem(TypedDict):
    query: str
    source_url: str
    title: str
    snippet: str

def add_research_items(existing: List[ResearchItem], new: List[ResearchItem]) -> List[ResearchItem]:
    """Reducer to append new research data to existing data."""
    return (existing or []) + (new or [])

class AgentState(TypedDict):
    # User's input goal / topic
    task: str
    
    # Generated research sub-queries
    plan: List[str]
    
    # Accumulated research results across iterations
    research_data: Annotated[List[ResearchItem], add_research_items]
    
    # Fact-checking & critique evaluation
    critique_feedback: Optional[str]
    critique_passed: bool
    
    # Guard against infinite agent loops
    revision_count: int
    max_revisions: int
    
    # Final output
    final_report: Optional[str]
