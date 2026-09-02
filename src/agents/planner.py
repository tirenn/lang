from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.state import AgentState
from src.config import get_agent_llm

class PlanOutput(BaseModel):
    queries: List[str] = Field(
        description="A list of 3 to 5 targeted search queries that cover all key facets of the topic."
    )

parser = JsonOutputParser(pydantic_object=PlanOutput)

PLANNER_PROMPT = """You are a Lead Research Strategist.
Your goal is to break down a complex research topic into targeted, high-signal search queries.

User Topic: {task}
{critique_context}

Guidelines:
1. Create 3 to 5 distinct search queries covering background, latest updates, critical perspectives, and key facts.
2. Make queries specific and search-engine friendly (in English or Indonesian depending on the topic).

{format_instructions}
"""

def planner_node(state: AgentState) -> Dict[str, Any]:
    """Node: Breaks down the task into search queries."""
    llm = get_agent_llm("planner")
    
    critique_context = ""
    if state.get("critique_feedback"):
        critique_context = f"\nPrevious reviewer critique to address:\n{state['critique_feedback']}\nEnsure queries address these missing angles."
    
    prompt = ChatPromptTemplate.from_template(
        template=PLANNER_PROMPT,
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    chain = prompt | llm | parser
    
    try:
        response = chain.invoke({
            "task": state["task"],
            "critique_context": critique_context
        })
        queries = response.get("queries", [state["task"]])
    except Exception:
        queries = [state["task"], f"{state['task']} 2026", f"{state['task']} analysis"]
        
    return {"plan": queries}
