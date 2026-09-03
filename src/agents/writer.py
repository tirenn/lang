from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from src.state import AgentState
from src.config import get_agent_llm

WRITER_PROMPT = """You are a Senior Investigative Fact-Checking Journalist and Managing Editor.
Synthesize the verified evidence into an objective, rigorous, publication-ready fact-checking report adhering to IFCN standards.

Claim Under Investigation:
{task}

Verification Board Verdict:
{verdict} (Confidence Level: {confidence_pct}%)

Verification Board Analysis:
{critique_feedback}

Documented Evidence & Sources:
{evidence}

Mandatory Report Structure:
1. # [FACT CHECK] <Clear, Objective Headline Addressing the Claim>
2. ## 🛡️ Verification Verdict: **[{verdict}]** (Confidence: {confidence_pct}%)
3. ## 📌 Circulating Claim & Background
   Detail the exact claim or rumor circulating across social media or public forums.
4. ## 🔍 Fact Investigation & Verified Evidence
   - Chronological breakdown and cross-verification using official government/agency data (e.g. KLHK, BMKG, BPOM, Kemenkes, Kominfo, Police, independent research).
   - Address key causal factors (human intent, natural phenomena, policy, negligence, or fabrication).
   - Do NOT draw conclusions beyond what the cited sources document.
5. ## ⚖️ Executive Conclusion
   A concise summary paragraph explaining why this verdict was assigned so the public is not misled.
6. ## 🔗 Verified Sources & Citations
   Numbered list of active Markdown links [Source Title](URL).

Language & Style: Write in clear, professional English. Be objective, impartial, and strictly grounded in the cited evidence. No conversational AI fluff.
"""

def writer_node(state: AgentState) -> Dict[str, Any]:
    """Node: Synthesizes final investigative fact-check article in Markdown."""
    llm = get_agent_llm("writer", temperature=0.2, model_override=state.get("writer_model"))
    
    evidence_blocks = []
    for item in state.get("research_data", []):
        evidence_blocks.append(f"- Source: {item['title']} ({item['source_url']})\n  Excerpt: {item['snippet']}")
    
    evidence_text = "\n\n".join(evidence_blocks) if evidence_blocks else "No specific evidence gathered."
    
    verdict = state.get("verdict", "PARTLY TRUE")
    confidence = state.get("confidence_score", 0.85)
    confidence_pct = int(confidence * 100)
    
    prompt = ChatPromptTemplate.from_template(WRITER_PROMPT)
    chain = prompt | llm
    
    response = chain.invoke({
        "task": state["task"],
        "verdict": verdict,
        "confidence_pct": confidence_pct,
        "critique_feedback": state.get("critique_feedback", "Verification complete."),
        "evidence": evidence_text
    })
    
    return {"final_report": response.content}
