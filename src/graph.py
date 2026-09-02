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
    Conditional routing logic:
    - If fact check passed, proceed to writer.
    - If reached max allowed revisions, proceed to writer anyway to avoid infinite loops.
    - Otherwise, loop back to planner with critique feedback to gather missing angles.
    """
    passed = state.get("critique_passed", False)
    revisions = state.get("revision_count", 0)
    max_revisions = state.get("max_revisions", 2)
    
    if passed or revisions >= max_revisions:
        return "writer"
    return "planner"

def build_research_graph(checkpointer: bool = True, human_in_the_loop: bool = False):
    """
    Assembles the multi-agent state graph with cyclic self-correction.
    """
    workflow = StateGraph(AgentState)
    
    # 1. Add Nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("fact_checker", fact_checker_node)
    workflow.add_node("writer", writer_node)
    
    # 2. Add Fixed Edges
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "researcher")
    workflow.add_edge("researcher", "fact_checker")
    
    # 3. Add Conditional Edge for Self-Correction Loop
    workflow.add_conditional_edges(
        "fact_checker",
        route_after_fact_check,
        {
            "writer": "writer",
            "planner": "planner"
        }
    )
    workflow.add_edge("writer", END)
    
    # Optional checkpointing & human review interruption
    memory = MemorySaver() if checkpointer else None
    interrupts = ["writer"] if human_in_the_loop else []
    
    app = workflow.compile(
        checkpointer=memory,
        interrupt_before=interrupts
    )
    return app
