from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from src.state import AgentState
from src.config import get_agent_llm

WRITER_PROMPT = """You are an Executive Technical Writer and Intelligence Analyst.
Synthesize the verified research findings into an exhaustive, high-quality, professional markdown report.

User Topic:
{task}

Verified Evidence & Sources:
{evidence}

Fact-Checking Notes:
{critique_feedback}

Report Requirements:
1. # Title: Professional, descriptive title.
2. ## Executive Summary: High-level synthesis with key takeaways.
3. ## Deep Dive / Key Findings: Detailed thematic sections with subheadings, bullet points, and data where available.
4. ## Challenges, Risks & Counter-Perspectives: Objective critical analysis.
5. ## Future Outlook & Strategic Implications: Where is this trend/technology heading?
6. ## Sources & Citations: Numbered list with Markdown links to source URLs.

Ensure strict grounding in the provided evidence. Do NOT hallucinate unverified facts.
"""

def writer_node(state: AgentState) -> Dict[str, Any]:
    """Node: Synthesizes final verified report in Markdown."""
    llm = get_agent_llm("writer", temperature=0.3)
    
    evidence_blocks = []
    for item in state.get("research_data", []):
        evidence_blocks.append(f"- Source: {item['title']} ({item['source_url']})\n  Excerpt: {item['snippet']}")
    
    evidence_text = "\n\n".join(evidence_blocks) if evidence_blocks else "No evidence available."
    
    prompt = ChatPromptTemplate.from_template(WRITER_PROMPT)
    chain = prompt | llm
    
    response = chain.invoke({
        "task": state["task"],
        "evidence": evidence_text,
        "critique_feedback": state.get("critique_feedback", "Verified complete.")
    })
    
    return {"final_report": response.content}
