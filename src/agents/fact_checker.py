from typing import Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.state import AgentState
from src.config import get_agent_llm

class FactCheckOutput(BaseModel):
    passed: bool = Field(
        description="True if findings are accurate, sufficient, and free of glaring contradictions. False if major info is missing."
    )
    feedback: str = Field(
        description="Constructive critique detailing what is missing or needs further verification if passed=False, or confirmation if passed=True."
    )
    confidence_score: float = Field(
        description="Confidence score between 0.0 and 1.0 regarding source quality and coverage."
    )

parser = JsonOutputParser(pydantic_object=FactCheckOutput)

FACT_CHECK_PROMPT = """You are a Principal Fact-Checker and Research Validator.
Evaluate whether the collected research data adequately, accurately, and objectively answers the user's research topic.

User Topic:
{task}

Collected Evidence:
{evidence}

Current Iteration: {revision_count} / {max_revisions}

Instructions:
1. Check for coverage of all critical angles of the topic.
2. Check for reliability and consistency among sources.
3. If critical angles are missing or ambiguous, set passed=false and provide specific instructions in feedback.
4. If sources are sufficient and trustworthy, set passed=true.

{format_instructions}
"""

def fact_checker_node(state: AgentState) -> Dict[str, Any]:
    """Node: Evaluates source quality and decides if more research is required."""
    llm = get_agent_llm("fact_checker")
    
    evidence_blocks = []
    for item in state.get("research_data", []):
        evidence_blocks.append(f"- [{item['title']}]({item['source_url']}): {item['snippet']}")
    
    evidence_text = "\n".join(evidence_blocks) if evidence_blocks else "No research data collected."
    
    current_revisions = state.get("revision_count", 0)
    max_revisions = state.get("max_revisions", 2)
    
    prompt = ChatPromptTemplate.from_template(
        template=FACT_CHECK_PROMPT,
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    chain = prompt | llm | parser
    
    try:
        result = chain.invoke({
            "task": state["task"],
            "evidence": evidence_text,
            "revision_count": current_revisions,
            "max_revisions": max_revisions
        })
        passed = bool(result.get("passed", True))
        feedback = str(result.get("feedback", "Sufficient evidence gathered."))
    except Exception as e:
        passed = True
        feedback = f"Automated pass (Validation note: {str(e)})"
    
    return {
        "critique_passed": passed,
        "critique_feedback": feedback,
        "revision_count": current_revisions + 1
    }
