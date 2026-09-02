# System Architecture Specification

## Autonomous Multi-Agent Research and Fact-Checking Engine

An enterprise-grade autonomous intelligence synthesis system built with LangChain, LangGraph, LangSmith, and OpenRouter. The engine coordinates specialized autonomous agents within a stateful, cyclical graph featuring dynamic self-correction, live web grounding, and real-time Server-Sent Events (SSE) streaming.

---

## 1. High-Level Architecture Diagram

`mermaid
flowchart TD
    subgraph ClientLayer [Client and Interface Layer]
        UI["Web UI (src/static/index.html)"]
        CLI["CLI Terminal (main.py)"]
    end

    subgraph ServerLayer [Server and Streaming Engine]
        FastAPI["FastAPI Server (src/server.py)"]
        SSE["Server-Sent Events (SSE) Streamer"]
        FastAPI --> SSE
    end

    subgraph GraphLayer [LangGraph Stateful Orchestration (src/graph.py)]
        START([User Query]) --> Planner["1. Planner Agent (src/agents/planner.py)"]
        Planner --> Researcher["2. Researcher Agent (src/agents/researcher.py)"]
        Researcher --> FactChecker["3. Fact-Checker and Critic (src/agents/fact_checker.py)"]
        
        FactChecker -->|Passed = False and Revisions < Max| Planner
        FactChecker -->|Passed = True OR Revisions >= Max| Writer["4. Executive Writer Agent (src/agents/writer.py)"]
        Writer --> END([Final Markdown Report])
    end

    subgraph ExternalServices [External Integrations]
        SearchTool["DuckDuckGo Live Search (ddgs)"]
        OpenRouter["OpenRouter API (3-Model Fallback Cascade)"]
        LangSmith["LangSmith Observability and Tracing"]
    end

    ClientLayer <--> ServerLayer
    ServerLayer <--> GraphLayer
    Researcher <--> SearchTool
    Planner & FactChecker & Writer <--> OpenRouter
    GraphLayer -.-> LangSmith
`

---

## 2. Core Architectural Principles

1. **Cyclic Self-Correction Over Linear Chains**: Unlike traditional sequential pipelines (A -> B -> C), LangGraph enables cyclical feedback loops. If the Fact-Checker identifies evidence gaps or hallucinations, it rejects the findings and routes back to the Planner with targeted critique.
2. **Typed Single Source of Truth**: All inter-agent data flows through a strictly typed AgentState schema with immutable reducers.
3. **Layered Resilience (Anti-Fragility)**:
   - **Model Layer**: 3-model OpenRouter cascade automatically routes past 429 rate-limits.
   - **Search Layer**: Graceful exception catching ensures execution continues even if network connections timeout.
   - **Graph Layer**: Hard limit (max_revisions) prevents infinite recursion.
4. **Zero-Overengineering (Ponytail Philosophy)**: Built without redundant class hierarchies, unnecessary dependency bloat, or brittle wrappers.

---

## 3. Shared State Schema (src/state.py)

The graph state operates as an append-safe accumulator passed between nodes:

`python
class ResearchItem(TypedDict):
    query: str       # The search sub-query executed
    source_url: str  # URL of the source article
    title: str       # Article headline
    snippet: str     # Extracted factual excerpt

def add_research_items(existing: List[ResearchItem], new: List[ResearchItem]) -> List[ResearchItem]:
    return (existing or []) + (new or [])

class AgentState(TypedDict):
    task: str                                                  # Original user query
    plan: List[str]                                            # Formulated search queries
    research_data: Annotated[List[ResearchItem], add_research_items]  # Accumulated evidence
    critique_feedback: Optional[str]                          # Feedback for revision loops
    critique_passed: bool                                      # Fact-check verdict
    revision_count: int                                        # Current loop iteration
    max_revisions: int                                         # Guard threshold (default: 2)
    final_report: Optional[str]                                # Output intelligence report
`

---

## 4. Node Breakdown and Execution Pipeline

| Node | File Location | Responsibility | Input State | Output State |
| :--- | :--- | :--- | :--- | :--- |
| **planner** | src/agents/planner.py | Decomposes broad topic into 3-5 targeted search sub-queries. Takes prior critique notes into account during revision cycles. | 	ask, critique_feedback | plan |
| **researcher** | src/agents/researcher.py | Executes live DuckDuckGo web searches for each planned query. | plan | 
esearch_data (accumulated via reducer) |
| **fact_checker** | src/agents/fact_checker.py | Validates evidence against the original research goal for factual accuracy, consistency, and completeness. | 	ask, 
esearch_data, 
evision_count | critique_passed, critique_feedback, 
evision_count |
| **writer** | src/agents/writer.py | Synthesizes verified findings into an executive-ready Markdown intelligence report complete with source citations. | 	ask, 
esearch_data, critique_feedback | inal_report |

---

## 5. Routing Logic and State Machine

`mermaid
stateDiagram-v2
    [*] --> Planner: START
    Planner --> Researcher: Sub-queries generated
    Researcher --> FactChecker: Web evidence gathered
    
    state FactCheckerDecision <<choice>>
    FactChecker --> FactCheckerDecision: Evaluate findings
    
    FactCheckerDecision --> Planner: Quality Inadequate (passed=false AND count < max)
    FactCheckerDecision --> Writer: Quality Verified OR Max Revisions Reached
    
    Writer --> [*]: END (Report Generated)
`

The conditional routing function (src/graph.py):
`python
def route_after_fact_check(state: AgentState) -> Literal["writer", "planner"]:
    if state["critique_passed"] or state["revision_count"] >= state["max_revisions"]:
        return "writer"
    return "planner"  # Loop back with critique feedback
`

---

## 6. Model Provider and Fallback Engineering (src/config.py)

To eliminate upstream rate-limiting (429 Too Many Requests) on public free-tier models, the engine utilizes OpenRouter Multi-Model Provider Routing (models: [primary, fallback_1, fallback_2]):

`mermaid
flowchart LR
    Request[Agent Prompt Request] --> Primary["Primary: minimax/minimax-m2.7:free"]
    Primary -->|If 429 / Throttled| Backup1["Fallback 1: google/gemma-4-31b-it:free"]
    Backup1 -->|If 429 / Throttled| Backup2["Fallback 2: nvidia/nemotron-3.5-lightning:free"]
    Backup2 --> Response[Successful Response]
`

### Dedicated Per-Agent Role Assignment (.env):
Each specialized agent can be individually assigned optimal model architectures:
- PLANNER_MODEL: Fast query decomposition.
- RESEARCHER_MODEL: High-speed processing.
- FACT_CHECKER_MODEL: Deep reasoning and strict logical consistency.
- WRITER_MODEL: Long-context structured prose synthesis.

---

## 7. Observability and Automated Evaluation (src/evaluate.py)

### Zero-Config Tracing
When LANGCHAIN_TRACING_V2=true is enabled in .env, LangSmith automatically hooks into every graph execution:
- Node-by-Node Latency Breakdown
- Token Consumption and Cost per Agent
- State Traversal Waterfall and Loop Visualization

### Automated LLM-as-a-Judge Evaluation Suite
The engine includes an automated benchmark runner that tests research accuracy against curated ground-truth datasets:

`ash
# Run automated benchmark evaluation
python -m src.evaluate
# or
make eval
`

Evaluation metrics scored on LangSmith:
1. **Groundedness and Faithfulness**: Verifies zero ungrounded hallucinations.
2. **Coverage and Completeness**: Ensures all core facets of the prompt are addressed.
3. **Citation Integrity**: Verifies proper markdown footnote links.

---

## 8. Directory and File Mapping

`
├── Dockerfile              # Production Python 3.11-slim container
├── docker-compose.yml      # Container orchestration (port 8090, volume mount)
├── Makefile                # Standardized developer CLI commands
├── .env.example            # Environment template
├── .gitignore              # Git ignore configuration
├── requirements.txt        # Pinned core dependencies
├── README.md               # Portfolio presentation and quickstart
├── ARCHITECTURE.md         # Full technical system architecture (this document)
├── main.py                 # Interactive Rich-formatted CLI runner
└── src/
    ├── __init__.py         # Package initialization
    ├── state.py            # TypedDict AgentState schema and reducers
    ├── config.py           # LLM connectors and multi-model fallback cascade
    ├── graph.py            # LangGraph StateGraph builder and conditional routing
    ├── server.py           # FastAPI server with Server-Sent Events (SSE)
    ├── evaluate.py         # LangSmith automated benchmark evaluation suite
    ├── tools/
    │   ├── __init__.py
    │   └── search.py       # DuckDuckGo live search integration
    ├── agents/
    │   ├── __init__.py
    │   ├── planner.py      # Strategic query decomposition agent
    │   ├── researcher.py   # Search gathering execution agent
    │   ├── fact_checker.py # Factual verification and critique agent
    │   └── writer.py       # Executive intelligence report writer
    └── static/
        └── index.html      # High-craft, dark-mode real-time web UI
`
