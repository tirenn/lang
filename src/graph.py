"""
LangGraph Workflow Assembly for Autonomous Fact-Checking.

Workflow Architecture:
    [START]
       │
       ▼
   [Planner]       (Deconstructs claim into 3-4 fact-checking keyword queries)
       │
       ▼
  [Researcher]     (Searches web, eliminates spam, deduplicates sources)
       │
       ▼
 [Fact-Checker]    (Evaluates evidence under IFCN standards; renders verdict)
       │
       ├─── Sufficient evidence OR reached max iterations? ──► [Writer] ──► [END]
       │
       └─── Insufficient evidence? (Loops back with critique) ──► [Planner]
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.state import AgentState
from src.agents.planner import planner_node
from src.agents.researcher import researcher_node
from src.agents.fact_checker import fact_checker_node
from src.agents.writer import writer_node


def route_after_fact_check(state: AgentState) -> Literal["writer", "planner"]:
    """
    Evaluates whether the verification is complete or requires another search iteration:
    1. If fact check passed: Proceed directly to writer.
    2. If max revision count reached: Proceed to writer to avoid infinite loops.
    3. If evidence is lacking and revisions remain: Loop back to planner with critique feedback.
    """
    passed = state.get("critique_passed", False)
    revisions = state.get("revision_count", 0)
    max_revisions = state.get("max_revisions", 2)

    if passed or revisions >= max_revisions:
        return "writer"
    return "planner"


def build_research_graph(checkpointer: bool = True, human_in_the_loop: bool = False):
    """
    Constructs and compiles the multi-agent StateGraph.
    
    Args:
        checkpointer: Enables MemorySaver checkpointer for state persistence across steps.
        human_in_the_loop: If True, halts execution before Writer node for human approval.
        
    Returns:
        Compiled LangGraph application.
    """
    workflow = StateGraph(AgentState)

    # 1. Register Multi-Agent Nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("fact_checker", fact_checker_node)
    workflow.add_node("writer", writer_node)

    # 2. Add Deterministic Sequence Edges
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "researcher")
    workflow.add_edge("researcher", "fact_checker")

    # 3. Add Conditional Self-Correction Loop Edge
    workflow.add_conditional_edges(
        "fact_checker",
        route_after_fact_check,
        {
            "writer": "writer",
            "planner": "planner"
        }
    )
    workflow.add_edge("writer", END)

    # 4. Optional Checkpointer & Interrupt Configuration
    memory = MemorySaver() if checkpointer else None
    interrupts = ["writer"] if human_in_the_loop else []

    return workflow.compile(
        checkpointer=memory,
        interrupt_before=interrupts
    )
