"""
State Definition for Multi-Agent Fact-Checking Workflow.

This module defines the shared state passed between nodes in the LangGraph workflow:
    START -> Planner -> Researcher -> Fact-Checker -> (Conditional Loop) -> Writer -> END
"""

from typing import TypedDict, List, Optional
from typing_extensions import Annotated


class ResearchItem(TypedDict):
    """Represents a single verified source or evidence item collected by the researcher."""
    query: str
    source_url: str
    title: str
    snippet: str


def add_research_items(existing: List[ResearchItem], new: List[ResearchItem]) -> List[ResearchItem]:
    """
    LangGraph state reducer: accumulates new research evidence into existing findings
    across multiple search iterations without overwriting past findings.
    """
    return (existing or []) + (new or [])


class AgentState(TypedDict):
    """
    Shared workflow state passed across all multi-agent nodes.
    
    Fields:
        task: The original user claim, headline, or rumor to verify.
        plan: List of 3-4 targeted search queries formulated by the Planner.
        research_data: Accumulated list of verified search findings (appended via reducer).
        critique_feedback: Evaluation and missing angle critique from the Fact-Checker.
        critique_passed: True if evidence is sufficient to render a final verdict.
        revision_count: Current count of research iterations.
        max_revisions: Maximum allowed revision loops (prevents infinite search loops).
        planner_model: Optional LLM model override for the Planner agent.
        researcher_model: Optional LLM model override for the Researcher agent.
        fact_checker_model: Optional LLM model override for the Fact-Checker agent.
        writer_model: Optional LLM model override for the Writer agent.
        verdict: Fact-checking verdict (TRUE, FALSE / HOAX, PARTLY TRUE, etc.).
        confidence_score: Quantitative confidence score (0.0 to 1.0).
        final_report: The complete investigative fact-checking article in Markdown.
    """
    # 1. Input Claim
    task: str

    # 2. Deconstruction & Search Queries
    plan: List[str]

    # 3. Evidence Collection (Accumulated via Reducer)
    research_data: Annotated[List[ResearchItem], add_research_items]

    # 4. Verification Board Evaluation
    critique_feedback: Optional[str]
    critique_passed: bool

    # 5. Iteration & Loop Guards
    revision_count: int
    max_revisions: int

    # 6. Model Assignment Overrides
    planner_model: Optional[str]
    researcher_model: Optional[str]
    fact_checker_model: Optional[str]
    writer_model: Optional[str]

    # 7. Official Verdict & Confidence
    verdict: Optional[str]
    confidence_score: Optional[float]

    # 8. Final Published Article
    final_report: Optional[str]
